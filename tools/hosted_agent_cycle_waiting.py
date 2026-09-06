"""Internal WAITING projection for Hosted Agent Cycle close.

Hosted Agent Cycle remains the only productive begin/close CLI. This helper only
promotes an already materialized and validated close failure when the exact
sealed observation proves the remaining gap is observational. It has no CLI,
semantic authority, replay behavior, Work/Coordination mutation, or writer.
"""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

from tools import agent_cycle_close
from tools import agent_failure
from tools import agent_write_lifecycle_guard
from tools import hosted_agent_cycle
from tools import hosted_agent_cycle_trace
from tools.agent_tools import trace_collect
from tools.canonical import stable_hash

WAITING_SCHEMA = "HostedAgentCycleCloseWaiting 0.1"
CLOSE_DELTA_DIAGNOSTIC_SCHEMA = "HostedAgentCycleCloseDeltaDiagnostic 0.1"
CLOSE_DELTA_DIAGNOSTIC_ERROR_SCHEMA = "HostedAgentCycleCloseDeltaDiagnosticError 0.1"
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
    core = {key: copy.deepcopy(item) for key, item in value.items() if key != "resultHash"}
    if value["resultHash"] != stable_hash(core):
        raise HostedAgentCycleWaitingError("HOSTED_AGENT_WAITING_RESULT_HASH_MISMATCH")
    return value


def build_close_delta_diagnostic(closure: Any) -> dict[str, Any] | None:
    """Project a validated unattributed close delta without reinterpreting it."""
    if not isinstance(closure, dict):
        return None
    if closure.get("schemaVersion") != "AgentCycleClosure 0.1":
        return None
    if closure.get("status") not in {"UNKNOWN", "BLOCKED"}:
        return None
    closure_hash = closure.get("closureHash")
    if not isinstance(closure_hash, str) or not HASH_RE.fullmatch(closure_hash):
        return None
    cycle_id = closure.get("cycleId")
    if not isinstance(cycle_id, str) or not cycle_id:
        return None

    receipt = closure.get("receipt")
    if not isinstance(receipt, dict) or receipt.get("status") not in {"UNKNOWN", "BLOCKED"}:
        return None
    receipt_hash = receipt.get("receiptHash")
    if not isinstance(receipt_hash, str) or not HASH_RE.fullmatch(receipt_hash):
        return None
    blockers = receipt.get("blockers")
    if (
        not isinstance(blockers, list)
        or any(not isinstance(item, str) or not item for item in blockers)
        or "UNATTRIBUTED_DURABLE_DELTA" not in blockers
    ):
        return None

    delta = receipt.get("delta")
    aggregate = receipt.get("aggregateReadback")
    if not isinstance(delta, dict) or not isinstance(aggregate, dict):
        return None
    durable = delta.get("durableChanges")
    covered = aggregate.get("coveredDurableChanges")
    uncovered = aggregate.get("uncoveredDurableChanges")
    evidence_count = aggregate.get("evidenceCount")
    source_heads = aggregate.get("sourceHeads")
    if (
        not isinstance(durable, list)
        or any(not isinstance(item, dict) for item in durable)
        or not isinstance(covered, list)
        or any(not isinstance(item, str) for item in covered)
        or not isinstance(uncovered, list)
        or any(not isinstance(item, str) for item in uncovered)
        or not isinstance(evidence_count, int)
        or isinstance(evidence_count, bool)
        or evidence_count < 0
        or not isinstance(source_heads, dict)
    ):
        return None

    body = {
        "schemaVersion": CLOSE_DELTA_DIAGNOSTIC_SCHEMA,
        "status": closure["status"],
        "cycleId": cycle_id,
        "sourceClosureHash": closure_hash,
        "sourceReceiptHash": receipt_hash,
        "receiptStatus": receipt["status"],
        "blockers": copy.deepcopy(blockers),
        "durableChanges": copy.deepcopy(durable),
        "coveredDurableChanges": copy.deepcopy(covered),
        "uncoveredDurableChanges": copy.deepcopy(uncovered),
        "evidenceCount": evidence_count,
        "sourceHeads": copy.deepcopy(source_heads),
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**body, "diagnosticHash": stable_hash(body)}


def _diagnostic_error(code: str) -> dict[str, Any]:
    body = {
        "schemaVersion": CLOSE_DELTA_DIAGNOSTIC_ERROR_SCHEMA,
        "status": "UNKNOWN",
        "reasonCode": "HOSTED_AGENT_CLOSE_DELTA_DIAGNOSTIC_UNAVAILABLE",
        "detailCode": code,
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**body, "diagnosticHash": stable_hash(body)}


def _materialize_close_delta_diagnostic(
    command: dict[str, Any],
    *,
    begin_dir: str,
    closure_path: str,
) -> bool:
    """Reobserve canonical close once for diagnosis; never rewrite operational result."""
    root = Path(closure_path).parent
    root.mkdir(parents=True, exist_ok=True)
    attempt_path = root / "closure-attempt.json"
    diagnostic_path = root / "close-delta-diagnostic.json"
    error_path = root / "close-delta-diagnostic.error.json"
    try:
        outer = hosted_agent_cycle.validate_transport_command(command)
        if outer.get("action") != "close":
            raise HostedAgentCycleWaitingError("HOSTED_AGENT_CLOSE_ACTION_REQUIRED")
        context_path = Path(begin_dir) / "context.json"
        context = _json(context_path)

        evidence_root = root / "close-delta-evidence"
        evidence_root.mkdir(parents=True, exist_ok=True)
        evidence_paths: list[str] = []
        evidence_ids = outer.get("evidenceCommentIds")
        if not isinstance(evidence_ids, list):
            raise HostedAgentCycleWaitingError("HOSTED_AGENT_CLOSE_EVIDENCE_IDS_INVALID")
        for index, comment_id in enumerate(evidence_ids):
            if (
                not isinstance(comment_id, int)
                or isinstance(comment_id, bool)
                or comment_id <= 0
            ):
                raise HostedAgentCycleWaitingError("HOSTED_AGENT_CLOSE_EVIDENCE_ID_INVALID")
            normalized = hosted_agent_cycle.normalize_remote_evidence(
                hosted_agent_cycle._remote_result_payload(comment_id)
            )
            path = evidence_root / f"evidence-{index:03d}.json"
            _write_json(path, normalized)
            evidence_paths.append(str(path))

        closure = agent_cycle_close.close_from_files(
            context_path=str(context_path),
            machine_scope="live",
            evidence_paths=evidence_paths,
        )
        evidence = agent_cycle_close.load_evidence(evidence_paths)
        agent_cycle_close.validate_closure(closure, context, evidence=evidence)
        _write_json(attempt_path, closure)

        diagnostic = build_close_delta_diagnostic(closure)
        if diagnostic is None:
            raise HostedAgentCycleWaitingError(
                "HOSTED_AGENT_CLOSE_DELTA_DIAGNOSTIC_MISMATCH"
            )
        _write_json(diagnostic_path, diagnostic)
        if error_path.exists():
            error_path.unlink()
        print(
            "HOSTED_AGENT_CLOSE_DELTA_DIAGNOSTIC "
            + json.dumps(diagnostic, sort_keys=True, ensure_ascii=False)
        )
        return True
    except Exception as exc:
        code = str(exc).split(":", 1)[0] or exc.__class__.__name__
        diagnostic = _diagnostic_error(code)
        _write_json(error_path, diagnostic)
        print(
            "HOSTED_AGENT_CLOSE_DELTA_DIAGNOSTIC "
            + json.dumps(diagnostic, sort_keys=True, ensure_ascii=False)
        )
        return False


def _failure_codes(failure: dict[str, Any]) -> set[str]:
    agent_failure.validate_hosted_cycle_failure(failure)
    return {item["code"] for item in failure["failureCore"]["causes"]}


def _trace_waiting_for(meta: dict[str, Any], manifest: dict[str, Any]) -> list[str]:
    close_comment_id = meta.get("commentId")
    if (
        not isinstance(close_comment_id, int)
        or isinstance(close_comment_id, bool)
        or close_comment_id <= 0
    ):
        return []
    try:
        comments = trace_collect.fetch_issue_comments(
            hosted_agent_cycle.REPOSITORY,
            manifest["source"]["issueNumber"],
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


def promote_close_result(
    *,
    command_path: str,
    meta_path: str,
    begin_dir: str,
    closure_path: str,
    result_path: str,
) -> bool:
    """Rewrite one waitable Hosted close failure as WAITING; otherwise no-op."""
    failure = _json(result_path)
    try:
        agent_failure.validate_hosted_cycle_failure(failure)
    except Exception:
        return False
    command = _json(command_path)
    meta = _json(meta_path)
    manifest = _json(Path(begin_dir) / "manifest.json")
    waiting_for = classify_waiting(
        failure,
        meta=meta,
        manifest=manifest,
        output_path=closure_path,
    )
    if not waiting_for:
        try:
            codes = _failure_codes(failure)
        except Exception:
            codes = set()
        if "UNATTRIBUTED_DURABLE_DELTA" in codes:
            _materialize_close_delta_diagnostic(
                command,
                begin_dir=begin_dir,
                closure_path=closure_path,
            )
        return False
    waiting = build_waiting(command, manifest, failure, waiting_for)
    _write_json(result_path, waiting)
    return True


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
