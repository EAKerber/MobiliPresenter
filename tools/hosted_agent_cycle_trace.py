#!/usr/bin/env python3
"""Read-only trace gate and evidence discovery for Hosted Agent Cycle close."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import hosted_agent_cycle
from tools.agent_tools import trace as trace_contract
from tools.agent_tools import trace_collect


class HostedAgentCycleTraceError(RuntimeError):
    pass


def _load(path: str | Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HostedAgentCycleTraceError("HOSTED_AGENT_TRACE_ARTIFACT_INVALID") from exc
    if not isinstance(value, dict):
        raise HostedAgentCycleTraceError("HOSTED_AGENT_TRACE_ARTIFACT_INVALID")
    return value


def _write(path: str | Path, value: dict[str, Any]) -> None:
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def prepare_close(
    command: dict[str, Any],
    meta: dict[str, Any],
    manifest: dict[str, Any],
    context: dict[str, Any],
    comments: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    command = hosted_agent_cycle.validate_command(command)
    if command["action"] != "close":
        raise HostedAgentCycleTraceError("HOSTED_AGENT_TRACE_CLOSE_REQUIRED")
    hosted_agent_cycle._validate_close_binding(command, manifest, context)
    if meta.get("issueNumber") != manifest["source"]["issueNumber"]:
        raise HostedAgentCycleTraceError("HOSTED_AGENT_TRACE_ISSUE_MISMATCH")
    close_comment_id = meta.get("commentId")
    if not isinstance(close_comment_id, int) or isinstance(close_comment_id, bool) or close_comment_id <= 0:
        raise HostedAgentCycleTraceError("HOSTED_AGENT_TRACE_CLOSE_COMMENT_INVALID")
    try:
        trace_value = trace_collect.build_trace(
            comments,
            manifest,
            close_comment_id=close_comment_id,
        )
    except RuntimeError as exc:
        raise HostedAgentCycleTraceError(str(exc).split(":", 1)[0]) from exc
    trace_contract.validate_trace(trace_value)
    if trace_value["traceStatus"] != "PASS":
        raise HostedAgentCycleTraceError("EXECUTION_TRACE_INCOMPLETE")
    discovered = trace_collect.remote_evidence_comment_ids(trace_value)
    amended = copy.deepcopy(command)
    amended["evidenceCommentIds"] = sorted(set(command["evidenceCommentIds"]) | set(discovered))
    hosted_agent_cycle.validate_command(amended)
    return amended, trace_value


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="hosted-agent-cycle-trace")
    parser.add_argument("--command", required=True)
    parser.add_argument("--meta", required=True)
    parser.add_argument("--begin-dir", required=True)
    parser.add_argument("--command-out", required=True)
    parser.add_argument("--trace-out", required=True)
    args = parser.parse_args(argv)
    try:
        command = _load(args.command)
        meta = _load(args.meta)
        root = Path(args.begin_dir)
        context = _load(root / "context.json")
        manifest = _load(root / "manifest.json")
        comments = trace_collect.fetch_issue_comments(
            hosted_agent_cycle.REPOSITORY,
            manifest["source"]["issueNumber"],
        )
        amended, trace_value = prepare_close(command, meta, manifest, context, comments)
        _write(args.command_out, amended)
        _write(args.trace_out, trace_value)
        print(json.dumps({
            "status": "PASS",
            "traceHash": trace_value["traceHash"],
            "attemptCount": trace_value["summary"]["attemptCount"],
            "evidenceCommentIds": amended["evidenceCommentIds"],
        }, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
