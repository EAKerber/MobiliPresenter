#!/usr/bin/env python3
"""Explicit non-terminal WAITING adapter for Hosted Agent Cycle close.

The canonical Hosted Agent Cycle remains the owner of begin/close semantics.
This adapter delegates one close attempt to that carrier and only promotes a
validated close failure when the exact sealed observation proves that the
remaining gap is observational. It never retries an operation, never mutates
Work or Coordination, and never creates authority.
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import io
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import agent_failure
from tools import agent_write_lifecycle_guard
from tools import hosted_agent_cycle
from tools import hosted_agent_cycle_trace
from tools.agent_tools import trace_collect
from tools.canonical import stable_hash

WAITING_SCHEMA = "HostedAgentCycleCloseWaiting 0.1"
WAITING_FIELDS = {
    "schemaVersion",
    "requestId",
    "commandHash",
    "cycleInstanceId",
    "status",
    "waitingFor",
    "observationRetry",
    "operationReplay",
    "sourceFailureHash",
    "readOnly",
    "semanticAuthority",
    "authorizesMutation",
    "resultHash",
}
WAITING_FOR = {
    "AGENT_TOOL_RESULT",
    "REMOTE_CANONICAL_RESULT",
    "AGENT_WRITE_LEASE_RESULT",
}
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
TRACE_WAITABLE_CAUSES = {
    "EXECUTION_TRACE_INCOMPLETE",
    "HOSTED_AGENT_EXECUTION_TRACE_INCOMPLETE",
}
REMOTE_RECEIPT_WAITABLE_CAUSES = {
    hosted_agent_cycle_trace.MUTATION_RECEIPT_MISSING,
    hosted_agent_cycle_trace.LIFECYCLE_RECEIPT_MISSING,
}
LIFECYCLE_WAITABLE_CAUSES = {
    "AGENT_WRITE_LIFECYCLE_REQUEST_WITHOUT_TERMINAL",
    "AGENT_WRITE_LIFECYCLE_UNKNOWN_AT_CLOSE",
}


class HostedAgentCycleWaitingError(RuntimeError):
    pass


def _json(path: str | Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HostedAgentCycleWaitingError("HOSTED_AGENT_WAITING_ARTIFACT_INVALID") from exc
    if not isinstance(value, dict):
        raise HostedAgentCycleWaitingError("HOSTED_AGENT_WAITING_ARTIFACT_INVALID")
    return value


def _write_json(path: str | Path, value: dict[str, Any]) -> None:
    Path(path).write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def validate_waiting(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != WAITING_FIELDS:
        raise HostedAgentCycleWaitingError("HOSTED_AGENT_WAITING_FIELDS_INVALID")
    if value.get("schemaVersion") != WAITING_SCHEMA or value.get("status") != "WAITING":
        raise HostedAgentCycleWaitingError("HOSTED_AGENT_WAITING_SCHEMA_INVALID")
    if not isinstance(value.get("requestId"), str) or not value["requestId"].strip():
        raise HostedAgentCycleWaitingError("HOSTED_AGENT_WAITING_REQUEST_INVALID")
    for field in ("commandHash", "sourceFailureHash", "resultHash"):
        raw = value.get(field)
        if not isinstance(raw, str) or not HASH_RE.fullmatch(raw):
            raise HostedAgentCycleWaitingError("HOSTED_AGENT_WAITING_HASH_INVALID")
    cycle_instance = value.get("cycleInstanceId")
    if (
        not isinstance(cycle_instance, str)
        or not hosted_agent_cycle.CYCLE_INSTANCE_RE.fullmatch(cycle_instance)
    ):
        raise HostedAgentCycleWaitingError("HOSTED_AGENT_WAITING_CYCLE_INVALID")
    waiting_for = value.get("waitingFor")
    if (
        not isinstance(waiting_for, list)
        or not waiting_for
        or waiting_for != sorted(set(waiting_for))
        or not set(waiting_for).issubset(WAITING_FOR)
    ):
        raise HostedAgentCycleWaitingError("HOSTED_AGENT_WAITING_TARGET_INVALID")
    if (
        value.get("observationRetry") != "SAFE"
        or value.get("operationReplay") != "NOT_APPLICABLE"
        or value.get("readOnly") is not True
        or value.get("semanticAuthority") is not False
        or value.get("authorizesMutation") is not False
    ):
        raise HostedAgentCycleWaitingError("HOSTED_AGENT_WAITING_BOUNDARY_INVALID")
    core = {
        key: copy.deepcopy(item)
        for key, item in value.items()
        if key != "resultHash"
    }
    if value["resultHash"] != stable_hash(core):
        raise HostedAgentCycleWaitingError("HOSTED_AGENT_WAITING_RESULT_HASH_MISMATCH")
    return value


def _failure_codes(failure: dict[str, Any]) -> set[str]:
    agent_failure.validate_hosted_cycle_failure(failure)
    return {item["code"] for item in failure["failureCore"]["causes"]}


def _trace_waiting_for(
    meta: dict[str, Any], manifest: dict[str, Any]
) -> list[str]:
    issue_number = manifest["source"]["issueNumber"]
    close_comment_id = meta.get("commentId")
    if (
        not isinstance(close_comment_id, int)
        or isinstance(close_comment_id, bool)
        or close_comment_id <= 0
    ):
        return []
    try:
        comments = trace_collect.fetch_issue_comments(
            hosted_agent_cycle.REPOSITORY, issue_number
        )
        trace = trace_collect.build_trace(
            comments,
            manifest,
            close_comment_id=close_comment_id,
        )
    except Exception:
        return []
    if trace.get("traceStatus") != "INCOMPLETE":
        return []
    waiting: set[str] = set()
    for attempt in trace.get("attempts", []):
        if attempt.get("matched") is True:
            continue
        if attempt.get("kind") == "agent-tool":
            waiting.add("AGENT_TOOL_RESULT")
        elif attempt.get("kind") == "remote-canonical":
            waiting.add("REMOTE_CANONICAL_RESULT")
        else:
            return []
    return sorted(waiting)


def _lifecycle_waiting_for(output_path: str) -> list[str]:
    report_path = Path(output_path).with_name("agent-write-lifecycle-close.json")
    if not report_path.is_file():
        return []
    try:
        report = agent_write_lifecycle_guard.validate_report(_json(report_path))
    except Exception:
        return []
    blockers = set(report.get("blockers") or [])
    if (
        report.get("state") == "UNKNOWN"
        and blockers
        and blockers.issubset({"AGENT_WRITE_LIFECYCLE_REQUEST_WITHOUT_TERMINAL"})
    ):
        return ["AGENT_WRITE_LEASE_RESULT"]
    return []


def classify_waiting(
    failure: dict[str, Any],
    *,
    meta: dict[str, Any],
    manifest: dict[str, Any],
    output_path: str,
) -> list[str]:
    try:
        codes = _failure_codes(failure)
    except Exception:
        return []
    if not codes:
        return []
    if codes.issubset(TRACE_WAITABLE_CAUSES) and codes & TRACE_WAITABLE_CAUSES:
        return _trace_waiting_for(meta, manifest)
    if codes.issubset(REMOTE_RECEIPT_WAITABLE_CAUSES):
        return ["REMOTE_CANONICAL_RESULT"]
    if codes.issubset(LIFECYCLE_WAITABLE_CAUSES):
        return _lifecycle_waiting_for(output_path)
    return []


def build_waiting(
    command: dict[str, Any],
    manifest: dict[str, Any],
    failure: dict[str, Any],
    waiting_for: list[str],
) -> dict[str, Any]:
    hosted_agent_cycle.validate_transport_command(command)
    hosted_agent_cycle.validate_begin_manifest(manifest)
    agent_failure.validate_hosted_cycle_failure(failure)
    if (
        not waiting_for
        or waiting_for != sorted(set(waiting_for))
        or not set(waiting_for).issubset(WAITING_FOR)
    ):
        raise HostedAgentCycleWaitingError("HOSTED_AGENT_WAITING_TARGET_INVALID")
    core = {
        "schemaVersion": WAITING_SCHEMA,
        "requestId": command["requestId"],
        "commandHash": hosted_agent_cycle.transport_command_hash(command),
        "cycleInstanceId": manifest["cycleInstanceId"],
        "status": "WAITING",
        "waitingFor": copy.deepcopy(waiting_for),
        "observationRetry": "SAFE",
        "operationReplay": "NOT_APPLICABLE",
        "sourceFailureHash": failure["failureHash"],
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return validate_waiting({**core, "resultHash": stable_hash(core)})


def close_once(
    *,
    command_path: str,
    meta_path: str,
    begin_dir: str,
    closure_path: str,
    evidence_dir: str,
    result_path: str,
) -> int:
    command = _json(command_path)
    meta = _json(meta_path)
    manifest = _json(Path(begin_dir) / "manifest.json")
    hosted_agent_cycle.validate_transport_command(command)
    hosted_agent_cycle.validate_begin_manifest(manifest)

    # Scope the existing stabilization primitive to one production observation.
    # Explicit characterization tests may still request multiple observations,
    # but the paved-path adapter never sleeps or polls before returning WAITING.
    previous_attempts = hosted_agent_cycle_trace.TRACE_STABILIZATION_ATTEMPTS
    hosted_agent_cycle_trace.TRACE_STABILIZATION_ATTEMPTS = 1
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            rc = hosted_agent_cycle.main([
                "close",
                "--command", command_path,
                "--meta", meta_path,
                "--begin-dir", begin_dir,
                "--closure", closure_path,
                "--evidence-dir", evidence_dir,
                "--result", result_path,
            ])
    finally:
        hosted_agent_cycle_trace.TRACE_STABILIZATION_ATTEMPTS = previous_attempts

    if rc == 0:
        result = _json(result_path)
        print(json.dumps(result, ensure_ascii=False))
        return 0

    failure = _json(result_path)
    waiting_for = classify_waiting(
        failure,
        meta=meta,
        manifest=manifest,
        output_path=closure_path,
    )
    if not waiting_for:
        print(json.dumps(failure, ensure_ascii=False))
        return rc

    waiting = build_waiting(command, manifest, failure, waiting_for)
    _write_json(result_path, waiting)
    print(json.dumps(waiting, ensure_ascii=False))
    # Non-zero keeps the existing workflow from uploading a terminal close
    # proof. The final carrier gate explicitly validates WAITING as operational.
    return 3


def require_operational_result(path: str) -> None:
    value = _json(path)
    status = value.get("status")
    if status == "WAITING":
        validate_waiting(value)
        return
    if status not in {"READY", "PASS"}:
        raise HostedAgentCycleWaitingError("HOSTED_AGENT_OPERATIONAL_RESULT_INVALID")
    if status == "READY" and value.get("schemaVersion") == "HostedAgentCycleBeginResult 0.5":
        resumability = value.get("resumability")
        if not isinstance(resumability, dict) or resumability.get("state") != "AVAILABLE":
            raise HostedAgentCycleWaitingError("HOSTED_AGENT_BEGIN_RESUMABILITY_INVALID")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hosted-agent-cycle-waiting")
    sub = parser.add_subparsers(dest="command_name", required=True)

    close = sub.add_parser("close")
    close.add_argument("--command", required=True)
    close.add_argument("--meta", required=True)
    close.add_argument("--begin-dir", required=True)
    close.add_argument("--closure", required=True)
    close.add_argument("--evidence-dir", required=True)
    close.add_argument("--result", required=True)

    require = sub.add_parser("require-operational-result")
    require.add_argument("--result", required=True)

    args = parser.parse_args(argv)
    try:
        if args.command_name == "close":
            return close_once(
                command_path=args.command,
                meta_path=args.meta,
                begin_dir=args.begin_dir,
                closure_path=args.closure,
                evidence_dir=args.evidence_dir,
                result_path=args.result,
            )
        require_operational_result(args.result)
        return 0
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
