from __future__ import annotations

import copy
import json
import subprocess
from typing import Any

from tools import agent_cycle_identity, hosted_cycle_records, remote_canonical_execution
from tools.agent_tools import contracts, mutation_dispatch, trace
from tools.canonical import stable_hash

CURRENT_REPOSITORY = hosted_cycle_records.CURRENT_REPOSITORY
AGENT_TOOL_REQUEST_MARKER = hosted_cycle_records.AGENT_TOOL_REQUEST_MARKER
AGENT_TOOL_REQUEST_MARKER_V02 = hosted_cycle_records.AGENT_TOOL_REQUEST_MARKER_V02
AGENT_TOOL_RESULT_MARKER = hosted_cycle_records.AGENT_TOOL_RESULT_MARKER
AGENT_TOOL_DISPATCH_MARKER = hosted_cycle_records.AGENT_TOOL_DISPATCH_MARKER
REMOTE_REQUEST_MARKER = hosted_cycle_records.REMOTE_REQUEST_MARKER
REMOTE_RESULT_MARKER = hosted_cycle_records.REMOTE_RESULT_MARKER


class AgentTraceCollectionError(RuntimeError):
    pass


# Compatibility aliases for internal consumers while record ownership migrates.
_json_after_marker = hosted_cycle_records.json_after_marker
_canonical_actor = hosted_cycle_records.canonical_actor
_canonical_begin = hosted_cycle_records.canonical_begin
_comment_id = hosted_cycle_records.comment_id
_request_comment_allowed = hosted_cycle_records.request_comment_allowed
_result_comment_allowed = hosted_cycle_records.result_comment_allowed


def cycle_instance_id(manifest: dict[str, Any]) -> str:
    try:
        return hosted_cycle_records.cycle_instance_id(manifest)
    except hosted_cycle_records.HostedCycleRecordError as exc:
        if exc.code == "HOSTED_CYCLE_RECORD_INSTANCE_MISMATCH":
            raise AgentTraceCollectionError("AGENT_TRACE_CYCLE_INSTANCE_MISMATCH") from exc
        raise AgentTraceCollectionError("AGENT_TRACE_CYCLE_INSTANCE_INVALID") from exc


def _window(comments: list[dict[str, Any]], begin_id: int, close_id: int) -> list[dict[str, Any]]:
    try:
        return hosted_cycle_records.window(comments, begin_id, close_id)
    except hosted_cycle_records.HostedCycleRecordError as exc:
        code = (
            "AGENT_TRACE_WINDOW_COMMENT_MISSING"
            if exc.code == "HOSTED_CYCLE_RECORD_WINDOW_COMMENT_MISSING"
            else "AGENT_TRACE_WINDOW_ORDER_INVALID"
        )
        raise AgentTraceCollectionError(code) from exc


def _record_view(
    comments: list[dict[str, Any]], manifest: dict[str, Any], *, close_comment_id: int
) -> dict[str, Any]:
    try:
        return hosted_cycle_records.collect(
            comments, manifest, close_comment_id=close_comment_id
        )
    except hosted_cycle_records.HostedCycleRecordError as exc:
        if exc.code == "HOSTED_CYCLE_RECORD_INSTANCE_MISMATCH":
            raise AgentTraceCollectionError("AGENT_TRACE_CYCLE_INSTANCE_MISMATCH") from exc
        if exc.code == "HOSTED_CYCLE_RECORD_WINDOW_COMMENT_MISSING":
            raise AgentTraceCollectionError("AGENT_TRACE_WINDOW_COMMENT_MISSING") from exc
        if exc.code == "HOSTED_CYCLE_RECORD_WINDOW_ORDER_INVALID":
            raise AgentTraceCollectionError("AGENT_TRACE_WINDOW_ORDER_INVALID") from exc
        raise AgentTraceCollectionError(exc.code) from exc


def _result_status(payload: dict[str, Any]) -> tuple[str, list[str]]:
    status = payload.get("status")
    if status not in {"PASS", "PLANNED", "BLOCKED", "UNKNOWN"}:
        status = "UNKNOWN"
    blockers = payload.get("blockers")
    if not isinstance(blockers, list) or any(not isinstance(item, str) or not item for item in blockers):
        blockers = ["TRACE_RESULT_STATUS_INVALID"] if status == "UNKNOWN" else []
    return status, sorted(set(blockers))


def _requests_from_view(view: dict[str, Any]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    hashes: set[str] = set()
    for item in hosted_cycle_records.records_of(
        view, "agent-tool-request", binding=hosted_cycle_records.STRONG
    ):
        request = item["normalized"]
        digest = contracts.request_hash(request)
        if digest in hashes:
            raise AgentTraceCollectionError("AGENT_TRACE_REQUEST_HASH_DUPLICATE")
        hashes.add(digest)
        operation = request.get("requestId")
        if not isinstance(operation, str) or not operation:
            operation = "invalid-agent-tool-" + digest[:16]
        found.append({
            "kind": "agent-tool",
            "requestCommentId": item["commentId"],
            "requestHash": digest,
            "operationId": operation,
        })

    for item in hosted_cycle_records.records_of(
        view, "remote-request", binding=hosted_cycle_records.AMBIENT
    ):
        payload = item["payload"]
        digest = stable_hash(payload)
        operation = payload.get("executionId")
        if not isinstance(operation, str) or not operation:
            operation = "invalid-remote-" + digest[:16]
        found.append({
            "kind": "remote-canonical",
            "requestCommentId": item["commentId"],
            "requestHash": digest,
            "operationId": operation,
        })

    found.sort(key=lambda item: item["requestCommentId"])
    return found


def _dispatches_from_view(view: dict[str, Any]) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for item in hosted_cycle_records.records_of(
        view, "agent-tool-dispatch", binding=hosted_cycle_records.STRONG
    ):
        payload = item["normalized"]
        digest = payload["requestHash"]
        if digest in found:
            raise AgentTraceCollectionError("AGENT_TRACE_DISPATCH_DUPLICATE")
        found[digest] = {
            "commentId": item["commentId"],
            "dispatchHash": payload["dispatchHash"],
        }
    return found


def _result_indexes_from_view(
    view: dict[str, Any]
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], list[int]]:
    agent: dict[str, dict[str, Any]] = {}
    remote: dict[str, dict[str, Any]] = {}
    agent_orphans: list[int] = []

    for item in hosted_cycle_records.records_of(
        view, "agent-tool-result", binding=hosted_cycle_records.STRONG
    ):
        payload = item["payload"]
        digest = payload.get("requestHash")
        if isinstance(digest, str) and len(digest) == 64:
            if digest in agent:
                raise AgentTraceCollectionError("AGENT_TRACE_RESULT_DUPLICATE")
            agent[digest] = {"commentId": item["commentId"], "payload": payload}
        else:
            agent_orphans.append(item["commentId"])

    for item in hosted_cycle_records.records_of(
        view, "remote-result", binding=hosted_cycle_records.AMBIENT
    ):
        payload = item["payload"]
        digest = payload.get("commandHash")
        if isinstance(digest, str) and len(digest) == 64:
            if digest in remote:
                raise AgentTraceCollectionError("AGENT_TRACE_RESULT_DUPLICATE")
            remote[digest] = {"commentId": item["commentId"], "payload": payload}
    return agent, remote, agent_orphans


def build_trace(
    comments: list[dict[str, Any]],
    manifest: dict[str, Any],
    *,
    close_comment_id: int,
) -> dict[str, Any]:
    source = manifest["source"]
    begin = agent_cycle_identity.begin_from_manifest(manifest)
    actor = copy.deepcopy(agent_cycle_identity.canonical_actor(manifest["actor"]))
    view = _record_view(comments, manifest, close_comment_id=close_comment_id)
    cycle_id = view["cycleInstanceId"]
    requests = _requests_from_view(view)
    agent_results, remote_results, agent_orphans = _result_indexes_from_view(view)
    dispatches = _dispatches_from_view(view)

    attempts: list[dict[str, Any]] = []
    consumed_agent: set[str] = set()
    consumed_remote: set[str] = set()
    consumed_dispatches: set[str] = set()
    for request in requests:
        index = agent_results if request["kind"] == "agent-tool" else remote_results
        match = index.get(request["requestHash"])
        dispatch = dispatches.get(request["requestHash"]) if request["kind"] == "agent-tool" else None
        if request["kind"] == "agent-tool":
            consumed_agent.add(request["requestHash"])
            if dispatch is not None:
                consumed_dispatches.add(request["requestHash"])
        else:
            consumed_remote.add(request["requestHash"])
        if match is None:
            status = "UNKNOWN"
            blockers = [
                "EXECUTION_RESULT_MISSING_AFTER_DISPATCH"
                if dispatch is not None
                else "EXECUTION_RESULT_MISSING"
            ]
            result_comment_id = None
        else:
            status, blockers = _result_status(match["payload"])
            result_comment_id = match["commentId"]
            if dispatch is not None and status == "PLANNED":
                raise AgentTraceCollectionError("AGENT_TRACE_DISPATCH_TERMINAL_INVALID")
        attempts.append({
            **request,
            "resultCommentId": result_comment_id,
            "status": status,
            "blockers": blockers,
            "matched": result_comment_id is not None,
        })

    unmatched_agent_results = sorted(set(agent_results) - consumed_agent)
    unmatched_dispatches = sorted(set(dispatches) - consumed_dispatches)
    if agent_orphans or unmatched_agent_results:
        raise AgentTraceCollectionError("AGENT_TRACE_ORPHAN_AGENT_TOOL_RESULT")
    if unmatched_dispatches:
        raise AgentTraceCollectionError("AGENT_TRACE_ORPHAN_AGENT_TOOL_DISPATCH")

    summary = {
        "attemptCount": len(attempts),
        "matchedCount": sum(1 for item in attempts if item["matched"]),
        "passCount": sum(1 for item in attempts if item["status"] in {"PASS", "PLANNED"}),
        "blockedCount": sum(1 for item in attempts if item["status"] == "BLOCKED"),
        "unknownCount": sum(1 for item in attempts if item["status"] == "UNKNOWN"),
    }
    core = {
        "schemaVersion": trace.TRACE_SCHEMA,
        "cycleInstanceId": cycle_id,
        "begin": begin,
        "actor": actor,
        "window": {
            "issueNumber": source["issueNumber"],
            "beginCommentId": source["commentId"],
            "closeCommentId": view["closeCommentId"],
        },
        "attempts": attempts,
        "summary": summary,
        "traceStatus": "PASS" if summary["matchedCount"] == summary["attemptCount"] else "INCOMPLETE",
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    result = {**core, "traceHash": stable_hash(core)}
    trace.validate_trace(result)
    return result


def remote_evidence_comment_ids(trace_value: dict[str, Any]) -> list[int]:
    trace.validate_trace(trace_value)
    return sorted(
        item["resultCommentId"]
        for item in trace_value["attempts"]
        if item["kind"] == "remote-canonical"
        and item["status"] == "PASS"
        and item["resultCommentId"] is not None
    )


def agent_tool_mutation_evidence_comment_ids(
    comments: list[dict[str, Any]],
    manifest: dict[str, Any],
    *,
    close_comment_id: int,
) -> list[int]:
    """Discover canonical receipt comments for successful dispatched Agent Tool mutations."""
    view = _record_view(comments, manifest, close_comment_id=close_comment_id)
    expected: dict[str, dict[str, Any]] = {}
    for item in hosted_cycle_records.records_of(
        view, "agent-tool-result", binding=hosted_cycle_records.STRONG
    ):
        payload = item["payload"]
        if payload.get("status") != "PASS":
            continue
        inner = payload.get("result")
        if not isinstance(inner, dict):
            continue
        try:
            receipt = mutation_dispatch.remote_receipt_from_execution_result(inner)
        except RuntimeError as exc:
            raise AgentTraceCollectionError("AGENT_TRACE_MUTATION_RECEIPT_INVALID") from exc
        if receipt is None:
            continue
        receipt_hash = receipt["receiptHash"]
        if receipt_hash in expected:
            raise AgentTraceCollectionError("AGENT_TRACE_MUTATION_RECEIPT_DUPLICATE_EXPECTATION")
        expected[receipt_hash] = receipt

    if not expected:
        return []

    found: dict[str, int] = {}
    for item in hosted_cycle_records.records_of(
        view, "remote-result", binding=hosted_cycle_records.STRONG
    ):
        payload = item["normalized"]
        receipt_hash = payload.get("receiptHash")
        if receipt_hash not in expected:
            continue
        try:
            remote_canonical_execution.validate_receipt(payload)
        except RuntimeError as exc:
            raise AgentTraceCollectionError("AGENT_TRACE_MUTATION_RECEIPT_INVALID") from exc
        if payload != expected[receipt_hash]:
            raise AgentTraceCollectionError("AGENT_TRACE_MUTATION_RECEIPT_MISMATCH")
        if receipt_hash in found:
            raise AgentTraceCollectionError("AGENT_TRACE_MUTATION_RECEIPT_COMMENT_DUPLICATE")
        found[receipt_hash] = item["commentId"]

    missing = sorted(set(expected) - set(found))
    if missing:
        raise AgentTraceCollectionError("AGENT_TRACE_MUTATION_RECEIPT_MISSING")
    return sorted(found.values())


def fetch_issue_comments(repository: str, issue_number: int) -> list[dict[str, Any]]:
    proc = subprocess.run(
        [
            "gh", "api", "--paginate", "--slurp",
            f"repos/{repository}/issues/{issue_number}/comments?per_page=100",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise AgentTraceCollectionError("AGENT_TRACE_COMMENTS_UNAVAILABLE")
    try:
        value = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise AgentTraceCollectionError("AGENT_TRACE_COMMENTS_INVALID") from exc
    pages = value if isinstance(value, list) else []
    comments: list[dict[str, Any]] = []
    for page in pages:
        if isinstance(page, list):
            comments.extend(item for item in page if isinstance(item, dict))
        elif isinstance(page, dict):
            comments.append(page)
    if not comments and pages and all(isinstance(item, dict) for item in pages):
        comments = list(pages)
    return comments
