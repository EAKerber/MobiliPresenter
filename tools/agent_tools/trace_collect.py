from __future__ import annotations

import copy
import json
import subprocess
from typing import Any

from tools import remote_canonical_execution
from tools.agent_tools import contracts, mutation_dispatch, trace
from tools.canonical import stable_hash

AGENT_TOOL_REQUEST_MARKER = "MOBILIPRESENTER_AGENT_TOOL_REQUEST_V0_1"
AGENT_TOOL_RESULT_MARKER = "MOBILIPRESENTER_AGENT_TOOL_RESULT_V0_1"
AGENT_TOOL_DISPATCH_MARKER = "MOBILIPRESENTER_AGENT_TOOL_DISPATCH_V0_1"
REMOTE_REQUEST_MARKER = "MOBILIPRESENTER_REMOTE_CANONICAL_REQUEST_V0_1"
REMOTE_RESULT_MARKER = "MOBILIPRESENTER_REMOTE_CANONICAL_RESULT_V0_1"


class AgentTraceCollectionError(RuntimeError):
    pass


def _json_after_marker(body: Any, marker: str) -> Any | None:
    prefix = marker + "\n"
    if not isinstance(body, str) or not body.startswith(prefix):
        return None
    raw = body[len(prefix):].strip()
    if raw.startswith("```json") and raw.endswith("```"):
        raw = raw[len("```json"): -len("```")].strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _canonical_actor(value: Any) -> dict[str, str] | None:
    try:
        return contracts._actor(value)
    except RuntimeError:
        return None


def _canonical_begin(value: Any) -> dict[str, Any] | None:
    try:
        return contracts._begin(value)
    except RuntimeError:
        return None


def _comment_id(value: Any) -> int | None:
    item = value.get("id") if isinstance(value, dict) else None
    return item if isinstance(item, int) and not isinstance(item, bool) and item > 0 else None


def _request_comment_allowed(comment: dict[str, Any]) -> bool:
    return comment.get("author_association") == "OWNER"


def _result_comment_allowed(comment: dict[str, Any]) -> bool:
    user = comment.get("user")
    return isinstance(user, dict) and user.get("login") == "github-actions[bot]"


def cycle_instance_id(manifest: dict[str, Any]) -> str:
    source = manifest["source"]
    body = {
        "begin": {
            "runId": source["runId"],
            "sourceSha": source["sourceSha"],
            "contextHash": manifest["contextHash"],
        },
        "actor": manifest["actor"],
        "issueNumber": source["issueNumber"],
        "beginCommentId": source["commentId"],
    }
    computed = "cycle-instance-" + stable_hash(body)[:24]
    declared = manifest.get("cycleInstanceId")
    if declared is not None:
        if declared != computed:
            raise AgentTraceCollectionError("AGENT_TRACE_CYCLE_INSTANCE_MISMATCH")
        return declared
    return computed


def _window(comments: list[dict[str, Any]], begin_id: int, close_id: int) -> list[dict[str, Any]]:
    positions = {_comment_id(comment): index for index, comment in enumerate(comments)}
    if begin_id not in positions or close_id not in positions:
        raise AgentTraceCollectionError("AGENT_TRACE_WINDOW_COMMENT_MISSING")
    if positions[begin_id] >= positions[close_id]:
        raise AgentTraceCollectionError("AGENT_TRACE_WINDOW_ORDER_INVALID")
    return comments[positions[begin_id] + 1:positions[close_id]]


def _result_status(payload: dict[str, Any]) -> tuple[str, list[str]]:
    status = payload.get("status")
    if status not in {"PASS", "PLANNED", "BLOCKED", "UNKNOWN"}:
        status = "UNKNOWN"
    blockers = payload.get("blockers")
    if not isinstance(blockers, list) or any(not isinstance(item, str) or not item for item in blockers):
        blockers = ["TRACE_RESULT_STATUS_INVALID"] if status == "UNKNOWN" else []
    return status, sorted(set(blockers))


def _agent_tool_requests(
    window: list[dict[str, Any]], begin: dict[str, Any], actor: dict[str, str]
) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    hashes: set[str] = set()
    for comment in window:
        if not _request_comment_allowed(comment):
            continue
        payload = _json_after_marker(comment.get("body"), AGENT_TOOL_REQUEST_MARKER)
        if not isinstance(payload, dict):
            continue
        if _canonical_begin(payload.get("begin")) != begin or _canonical_actor(payload.get("actor")) != actor:
            continue
        digest = stable_hash(payload)
        if digest in hashes:
            raise AgentTraceCollectionError("AGENT_TRACE_REQUEST_HASH_DUPLICATE")
        hashes.add(digest)
        operation = payload.get("requestId")
        if not isinstance(operation, str) or not operation:
            operation = "invalid-agent-tool-" + digest[:16]
        found.append({
            "kind": "agent-tool",
            "requestCommentId": _comment_id(comment),
            "requestHash": digest,
            "operationId": operation,
        })
    return found


def _remote_requests(window: list[dict[str, Any]], actor: dict[str, str]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for comment in window:
        if not _request_comment_allowed(comment):
            continue
        payload = _json_after_marker(comment.get("body"), REMOTE_REQUEST_MARKER)
        if not isinstance(payload, dict) or _canonical_actor(payload.get("actor")) != actor:
            continue
        digest = stable_hash(payload)
        operation = payload.get("executionId")
        if not isinstance(operation, str) or not operation:
            operation = "invalid-remote-" + digest[:16]
        found.append({
            "kind": "remote-canonical",
            "requestCommentId": _comment_id(comment),
            "requestHash": digest,
            "operationId": operation,
        })
    return found


def _agent_tool_dispatches(
    window: list[dict[str, Any]],
    begin: dict[str, Any],
    actor: dict[str, str],
    expected_cycle_instance_id: str,
) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for comment in window:
        if not _result_comment_allowed(comment):
            continue
        payload = _json_after_marker(comment.get("body"), AGENT_TOOL_DISPATCH_MARKER)
        if not isinstance(payload, dict):
            continue
        if _canonical_begin(payload.get("begin")) != begin or _canonical_actor(payload.get("actor")) != actor:
            continue
        try:
            mutation_dispatch.validate_dispatch(payload)
        except RuntimeError as exc:
            raise AgentTraceCollectionError("AGENT_TRACE_DISPATCH_INVALID") from exc
        if payload.get("cycleInstanceId") != expected_cycle_instance_id:
            raise AgentTraceCollectionError("AGENT_TRACE_DISPATCH_CYCLE_MISMATCH")
        digest = payload["requestHash"]
        if digest in found:
            raise AgentTraceCollectionError("AGENT_TRACE_DISPATCH_DUPLICATE")
        found[digest] = {
            "commentId": _comment_id(comment),
            "dispatchHash": payload["dispatchHash"],
        }
    return found


def _result_indexes(
    window: list[dict[str, Any]], begin: dict[str, Any], actor: dict[str, str]
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], list[int]]:
    agent: dict[str, dict[str, Any]] = {}
    remote: dict[str, dict[str, Any]] = {}
    agent_orphans: list[int] = []
    for comment in window:
        if not _result_comment_allowed(comment):
            continue
        comment_id = _comment_id(comment)
        payload = _json_after_marker(comment.get("body"), AGENT_TOOL_RESULT_MARKER)
        if isinstance(payload, dict):
            payload_begin = _canonical_begin(payload.get("begin"))
            payload_actor = _canonical_actor(payload.get("actor"))
            if payload_begin == begin and payload_actor == actor:
                digest = payload.get("requestHash")
                if isinstance(digest, str) and len(digest) == 64:
                    if digest in agent:
                        raise AgentTraceCollectionError("AGENT_TRACE_RESULT_DUPLICATE")
                    agent[digest] = {"commentId": comment_id, "payload": payload}
                else:
                    agent_orphans.append(comment_id)
            continue
        payload = _json_after_marker(comment.get("body"), REMOTE_RESULT_MARKER)
        if isinstance(payload, dict):
            digest = payload.get("commandHash")
            if isinstance(digest, str) and len(digest) == 64:
                if digest in remote:
                    raise AgentTraceCollectionError("AGENT_TRACE_RESULT_DUPLICATE")
                remote[digest] = {"commentId": comment_id, "payload": payload}
    return agent, remote, agent_orphans


def build_trace(
    comments: list[dict[str, Any]],
    manifest: dict[str, Any],
    *,
    close_comment_id: int,
) -> dict[str, Any]:
    source = manifest["source"]
    begin = {
        "runId": source["runId"],
        "sourceSha": source["sourceSha"],
        "contextHash": manifest["contextHash"],
    }
    actor = copy.deepcopy(manifest["actor"])
    cycle_id = cycle_instance_id(manifest)
    window = _window(comments, source["commentId"], close_comment_id)
    requests = _agent_tool_requests(window, begin, actor) + _remote_requests(window, actor)
    requests.sort(key=lambda item: item["requestCommentId"])
    agent_results, remote_results, agent_orphans = _result_indexes(window, begin, actor)
    dispatches = _agent_tool_dispatches(window, begin, actor, cycle_id)

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
    # Remote results cannot be safely assigned to this cycle without a matching
    # same-session request because the legacy result envelope carries no actor.
    # They are therefore ignored unless paired by commandHash.

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
            "closeCommentId": close_comment_id,
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
