#!/usr/bin/env python3
"""Hosted carrier for Agent Tool Interface 0.1/AT3C.

The carrier binds an AgentToolRequest to an exact Hosted Agent Cycle begin and
keeps the hosted workflow itself Git-read-only. Read-only tools may execute
locally, plan-only tools remain PLANNED, and Manager/GitOps mutation-execute
tools are converted into a hash-bound AgentToolMutationDispatch after positive
guard proofs. The mutation is never materialized by this carrier.
"""
from __future__ import annotations

import copy
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import hosted_agent_cycle
from tools.agent_tools import admission, contracts, mutation_dispatch, resolver
from tools.canonical import stable_hash

REPOSITORY = "EAKerber/MobiliPresenter"
BUS_TITLE = hosted_agent_cycle.BUS_TITLE
REQUEST_MARKER = "MOBILIPRESENTER_AGENT_TOOL_REQUEST_V0_1"
RESULT_MARKER = "MOBILIPRESENTER_AGENT_TOOL_RESULT_V0_1"
DISPATCH_MARKER = "MOBILIPRESENTER_AGENT_TOOL_DISPATCH_V0_1"
RESULT_SCHEMA = "HostedAgentToolResult 0.1"
FAILURE_SCHEMA = "HostedAgentToolFailure 0.1"
HASH_RE = re.compile(r"^[0-9a-f]{64}$")


class HostedAgentToolError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}" if detail else code)


def _raw_request_hash(value: Any) -> str | None:
    return stable_hash(value) if isinstance(value, dict) else None


def _partial_begin(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    try:
        return contracts._begin(value)
    except RuntimeError:
        return None


def _partial_actor(value: Any) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None
    try:
        return contracts._actor(value)
    except RuntimeError:
        return None


def _positive_int(value: Any, code: str) -> int:
    if isinstance(value, str) and value.isdigit():
        value = int(value)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise HostedAgentToolError(code)
    return value


def parse_event(value: Any) -> tuple[dict[str, Any], dict[str, int]]:
    if not isinstance(value, dict):
        raise HostedAgentToolError("HOSTED_AGENT_TOOL_EVENT_INVALID")
    issue = value.get("issue")
    comment = value.get("comment")
    repository = value.get("repository")
    if not isinstance(issue, dict) or not isinstance(comment, dict) or not isinstance(repository, dict):
        raise HostedAgentToolError("HOSTED_AGENT_TOOL_EVENT_INVALID")
    if issue.get("pull_request") is not None:
        raise HostedAgentToolError("HOSTED_AGENT_TOOL_PR_COMMENT_FORBIDDEN")
    if issue.get("title") != BUS_TITLE:
        raise HostedAgentToolError("HOSTED_AGENT_TOOL_BUS_MISMATCH")
    if comment.get("author_association") != "OWNER":
        raise HostedAgentToolError("HOSTED_AGENT_TOOL_ACTOR_FORBIDDEN")
    if repository.get("full_name") != REPOSITORY:
        raise HostedAgentToolError("HOSTED_AGENT_TOOL_REPOSITORY_MISMATCH")
    body = comment.get("body")
    prefix = REQUEST_MARKER + "\n"
    if not isinstance(body, str) or not body.startswith(prefix):
        raise HostedAgentToolError("HOSTED_AGENT_TOOL_MARKER_INVALID")
    try:
        request = json.loads(body[len(prefix):].strip())
    except json.JSONDecodeError as exc:
        raise HostedAgentToolError("HOSTED_AGENT_TOOL_JSON_INVALID") from exc
    try:
        contracts.validate_request(request)
    except RuntimeError as exc:
        raise HostedAgentToolError(str(exc).split(":", 1)[0]) from exc
    issue_number = issue.get("number")
    comment_id = comment.get("id")
    if (
        not isinstance(issue_number, int) or isinstance(issue_number, bool) or issue_number <= 0
        or not isinstance(comment_id, int) or isinstance(comment_id, bool) or comment_id <= 0
    ):
        raise HostedAgentToolError("HOSTED_AGENT_TOOL_EVENT_IDENTITY_INVALID")
    return request, {"issueNumber": issue_number, "commentId": comment_id}


def validate_begin_binding(request: dict[str, Any], manifest: dict[str, Any], context: dict[str, Any]) -> None:
    contracts.validate_request(request)
    hosted_agent_cycle.validate_begin_manifest(manifest, context)
    source = manifest["source"]
    begin = request["begin"]
    if (
        begin["runId"] != source["runId"]
        or begin["sourceSha"] != source["sourceSha"]
        or begin["contextHash"] != manifest["contextHash"]
    ):
        raise HostedAgentToolError("HOSTED_AGENT_TOOL_BEGIN_REF_MISMATCH")
    if request["actor"] != manifest["actor"]:
        raise HostedAgentToolError("HOSTED_AGENT_TOOL_CYCLE_IDENTITY_MISMATCH")


def _terminal_payload(
    request: dict[str, Any], plan: dict[str, Any], result: dict[str, Any]
) -> dict[str, Any]:
    core = {
        "schemaVersion": RESULT_SCHEMA,
        "requestId": request["requestId"],
        "requestHash": contracts.request_hash(request),
        "begin": copy.deepcopy(request["begin"]),
        "actor": copy.deepcopy(request["actor"]),
        "toolId": request["toolId"],
        "plan": copy.deepcopy(plan),
        "result": copy.deepcopy(result),
        "status": result["status"],
        "blockers": copy.deepcopy(result["blockers"]),
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**core, "hostedResultHash": stable_hash(core)}


def prepare_request(
    request: dict[str, Any],
    manifest: dict[str, Any],
    context: dict[str, Any],
    *,
    meta: dict[str, Any] | None = None,
    hosted_run_id: int | str | None = None,
    transport: Any | None = None,
    authority_factory: Any | None = None,
) -> dict[str, Any]:
    """Prepare exactly one terminal result or one non-terminal mutation dispatch."""

    validate_begin_binding(request, manifest, context)
    planned = resolver.resolve_request(
        request, context, transport=transport, execute=False
    )
    plan = planned["plan"]
    mode = plan["mode"]

    if mode == "plan-only":
        result = planned["result"]
        if result["status"] != "PLANNED":
            raise HostedAgentToolError("HOSTED_AGENT_TOOL_MUTATION_MODE_VIOLATION")
        return {
            "kind": "terminal",
            "plan": plan,
            "result": _terminal_payload(request, plan, result),
        }

    if mode == "read-only-execute":
        executed = resolver.resolve_request(
            request, context, transport=transport, execute=True
        )
        if executed["plan"]["planHash"] != plan["planHash"]:
            raise HostedAgentToolError("HOSTED_AGENT_TOOL_PLAN_DRIFT")
        result = executed["result"]
        if result["status"] != "PASS":
            raise HostedAgentToolError("HOSTED_AGENT_TOOL_READ_ONLY_EXECUTION_INVALID")
        return {
            "kind": "terminal",
            "plan": plan,
            "result": _terminal_payload(request, plan, result),
        }

    if mode != "mutation-execute":
        raise HostedAgentToolError("HOSTED_AGENT_TOOL_MODE_UNSUPPORTED")
    if request["actor"]["role"] != "manager-gitops":
        raise HostedAgentToolError("HOSTED_AGENT_TOOL_MUTATION_ROLE_FORBIDDEN")
    if not isinstance(meta, dict):
        raise HostedAgentToolError("HOSTED_AGENT_TOOL_DISPATCH_META_REQUIRED")
    issue_number = _positive_int(meta.get("issueNumber"), "HOSTED_AGENT_TOOL_DISPATCH_META_INVALID")
    request_comment_id = _positive_int(meta.get("commentId"), "HOSTED_AGENT_TOOL_DISPATCH_META_INVALID")
    run_id = _positive_int(
        hosted_run_id if hosted_run_id is not None else os.environ.get("GITHUB_RUN_ID"),
        "HOSTED_AGENT_TOOL_RUN_ID_INVALID",
    )
    cycle_instance_id = manifest.get("cycleInstanceId")
    if not isinstance(cycle_instance_id, str):
        raise HostedAgentToolError("HOSTED_AGENT_TOOL_DISPATCH_CYCLE_REQUIRED")

    lifecycle_context = {
        "cycleInstanceId": cycle_instance_id,
        "issueNumber": issue_number,
        "beforeCommentId": request_comment_id,
    }
    proof_set = admission.collect_guard_proofs(
        plan,
        transport=transport,
        authority_factory=authority_factory,
        lifecycle_context=lifecycle_context,
    )
    admission.assert_execution_admitted(plan, proof_set)
    dispatch = mutation_dispatch.build_dispatch(
        plan,
        proof_set,
        cycle_instance_id=cycle_instance_id,
        issue_number=issue_number,
        request_comment_id=request_comment_id,
        hosted_run_id=run_id,
    )
    return {
        "kind": "dispatch",
        "plan": plan,
        "proofSet": proof_set,
        "dispatch": dispatch,
    }


def execute_request(
    request: dict[str, Any],
    manifest: dict[str, Any],
    context: dict[str, Any],
    *,
    transport: Any | None = None,
) -> dict[str, Any]:
    """Compatibility facade for existing terminal-only callers."""
    outcome = prepare_request(
        request, manifest, context, transport=transport
    )
    if outcome["kind"] != "terminal":
        raise HostedAgentToolError("HOSTED_AGENT_TOOL_MUTATION_DISPATCH_REQUIRED")
    return outcome["result"]


def failure_payload(exc: BaseException, request: Any = None) -> dict[str, Any]:
    code = getattr(exc, "code", None)
    if not isinstance(code, str) or not code:
        text = str(exc)
        code = text.split(":", 1)[0] if text else exc.__class__.__name__
    raw_hash = _raw_request_hash(request)
    core = {
        "schemaVersion": FAILURE_SCHEMA,
        "requestId": request.get("requestId") if isinstance(request, dict) else None,
        "requestHash": raw_hash,
        "begin": _partial_begin(request.get("begin")) if isinstance(request, dict) else None,
        "actor": _partial_actor(request.get("actor")) if isinstance(request, dict) else None,
        "toolId": request.get("toolId") if isinstance(request, dict) and isinstance(request.get("toolId"), str) else None,
        "status": "BLOCKED",
        "blockers": [code],
        "detail": str(exc),
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**core, "failureHash": stable_hash(core)}


def _load(path: str | Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HostedAgentToolError("HOSTED_AGENT_TOOL_ARTIFACT_INVALID") from exc
    if not isinstance(value, dict):
        raise HostedAgentToolError("HOSTED_AGENT_TOOL_ARTIFACT_INVALID")
    return value


def _write(path: str | Path, payload: dict[str, Any]) -> None:
    Path(path).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _emit_output(path: str, key: str, value: str) -> None:
    with Path(path).open("a", encoding="utf-8") as handle:
        handle.write(f"{key}={value}\n")


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="hosted-agent-tool")
    sub = parser.add_subparsers(dest="command_name", required=True)

    parse = sub.add_parser("parse-event")
    parse.add_argument("--event", required=True)
    parse.add_argument("--request-out", required=True)
    parse.add_argument("--meta-out", required=True)
    parse.add_argument("--github-output", required=True)

    execute = sub.add_parser("execute")
    execute.add_argument("--request", required=True)
    execute.add_argument("--meta", required=True)
    execute.add_argument("--begin-dir", required=True)
    execute.add_argument("--result", required=True)
    execute.add_argument("--plan", required=True)
    execute.add_argument("--proof-set", required=True)
    execute.add_argument("--dispatch", required=True)

    failure = sub.add_parser("failure")
    failure.add_argument("--error", required=True)
    failure.add_argument("--request")
    failure.add_argument("--result", required=True)

    args = parser.parse_args(argv)
    request: Any = None
    try:
        if args.command_name == "parse-event":
            event = json.loads(Path(args.event).read_text(encoding="utf-8"))
            body = event.get("comment", {}).get("body") if isinstance(event, dict) else None
            if isinstance(body, str) and body.startswith(REQUEST_MARKER + "\n"):
                try:
                    request = json.loads(body[len(REQUEST_MARKER) + 1:].strip())
                except json.JSONDecodeError:
                    request = None
            request, meta = parse_event(event)
            _write(args.request_out, request)
            _write(args.meta_out, meta)
            _emit_output(args.github_output, "begin_run_id", str(request["begin"]["runId"]))
            _emit_output(args.github_output, "begin_source_sha", request["begin"]["sourceSha"])
            return 0

        request = _load(args.request) if getattr(args, "request", None) else None
        if args.command_name == "execute":
            root = Path(args.begin_dir)
            context = _load(root / "context.json")
            manifest = _load(root / "manifest.json")
            meta = _load(args.meta)
            outcome = prepare_request(request, manifest, context, meta=meta)
            _write(args.plan, outcome["plan"])
            if outcome["kind"] == "dispatch":
                _write(args.proof_set, outcome["proofSet"])
                _write(args.dispatch, outcome["dispatch"])
                payload = outcome["dispatch"]
            else:
                _write(args.result, outcome["result"])
                payload = outcome["result"]
        else:
            payload = failure_payload(HostedAgentToolError(args.error), request)
            _write(args.result, payload)
        print(json.dumps(payload, ensure_ascii=False))
        if isinstance(payload, dict) and payload.get("schemaVersion") == mutation_dispatch.DISPATCH_SCHEMA:
            return 0
        return 0 if payload.get("status") in {"PASS", "PLANNED"} else 2
    except Exception as exc:
        payload = failure_payload(exc, request)
        _write(args.result, payload)
        print(json.dumps(payload, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
