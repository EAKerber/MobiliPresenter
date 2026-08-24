from __future__ import annotations

import copy
import re
from typing import Any

from tools.canonical import stable_hash

TRACE_SCHEMA = "AgentCycleExecutionTrace 0.1"
TRACE_FIELDS = {
    "schemaVersion", "cycleInstanceId", "begin", "actor", "window", "attempts",
    "summary", "traceStatus", "readOnly", "semanticAuthority", "authorizesMutation",
    "traceHash",
}
BEGIN_FIELDS = {"runId", "sourceSha", "contextHash"}
ACTOR_FIELDS = {"role", "workerId", "sessionId"}
WINDOW_FIELDS = {"issueNumber", "beginCommentId", "closeCommentId"}
ATTEMPT_FIELDS = {
    "kind", "requestCommentId", "resultCommentId", "requestHash", "operationId",
    "status", "blockers", "matched",
}
SUMMARY_FIELDS = {"attemptCount", "matchedCount", "passCount", "blockedCount", "unknownCount"}
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
KINDS = {"agent-tool", "remote-canonical"}
ATTEMPT_STATUSES = {"PASS", "PLANNED", "BLOCKED", "UNKNOWN"}
TRACE_STATUSES = {"PASS", "INCOMPLETE"}


def _positive_int(value: Any, code: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise RuntimeError(code)
    return value


def _text(value: Any, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(code)
    return value.strip()


def _begin(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != BEGIN_FIELDS:
        raise RuntimeError("AGENT_TRACE_BEGIN_INVALID")
    _positive_int(value.get("runId"), "AGENT_TRACE_BEGIN_INVALID")
    if not isinstance(value.get("sourceSha"), str) or not SHA_RE.fullmatch(value["sourceSha"]):
        raise RuntimeError("AGENT_TRACE_BEGIN_INVALID")
    if not isinstance(value.get("contextHash"), str) or not HASH_RE.fullmatch(value["contextHash"]):
        raise RuntimeError("AGENT_TRACE_BEGIN_INVALID")
    return copy.deepcopy(value)


def _actor(value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != ACTOR_FIELDS:
        raise RuntimeError("AGENT_TRACE_ACTOR_INVALID")
    return {key: _text(value[key], "AGENT_TRACE_ACTOR_INVALID") for key in sorted(ACTOR_FIELDS)}


def validate_trace(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != TRACE_FIELDS:
        raise RuntimeError("AGENT_TRACE_FIELDS_INVALID")
    if value.get("schemaVersion") != TRACE_SCHEMA:
        raise RuntimeError("AGENT_TRACE_SCHEMA_UNSUPPORTED")
    _text(value.get("cycleInstanceId"), "AGENT_TRACE_CYCLE_INSTANCE_INVALID")
    _begin(value.get("begin"))
    _actor(value.get("actor"))

    window = value.get("window")
    if not isinstance(window, dict) or set(window) != WINDOW_FIELDS:
        raise RuntimeError("AGENT_TRACE_WINDOW_INVALID")
    for field in WINDOW_FIELDS:
        _positive_int(window.get(field), "AGENT_TRACE_WINDOW_INVALID")
    if window["beginCommentId"] >= window["closeCommentId"]:
        raise RuntimeError("AGENT_TRACE_WINDOW_INVALID")

    attempts = value.get("attempts")
    if not isinstance(attempts, list):
        raise RuntimeError("AGENT_TRACE_ATTEMPTS_INVALID")
    request_ids: set[int] = set()
    result_ids: set[int] = set()
    for item in attempts:
        if not isinstance(item, dict) or set(item) != ATTEMPT_FIELDS:
            raise RuntimeError("AGENT_TRACE_ATTEMPT_FIELDS_INVALID")
        if item.get("kind") not in KINDS or item.get("status") not in ATTEMPT_STATUSES:
            raise RuntimeError("AGENT_TRACE_ATTEMPT_VALUE_INVALID")
        request_comment_id = _positive_int(item.get("requestCommentId"), "AGENT_TRACE_ATTEMPT_ID_INVALID")
        if request_comment_id in request_ids:
            raise RuntimeError("AGENT_TRACE_REQUEST_DUPLICATE")
        request_ids.add(request_comment_id)
        result_comment_id = item.get("resultCommentId")
        if result_comment_id is not None:
            result_comment_id = _positive_int(result_comment_id, "AGENT_TRACE_ATTEMPT_ID_INVALID")
            if result_comment_id in result_ids:
                raise RuntimeError("AGENT_TRACE_RESULT_DUPLICATE")
            result_ids.add(result_comment_id)
        if item.get("matched") is not (result_comment_id is not None):
            raise RuntimeError("AGENT_TRACE_ATTEMPT_MATCH_INVALID")
        if not isinstance(item.get("requestHash"), str) or not HASH_RE.fullmatch(item["requestHash"]):
            raise RuntimeError("AGENT_TRACE_REQUEST_HASH_INVALID")
        _text(item.get("operationId"), "AGENT_TRACE_OPERATION_ID_INVALID")
        blockers = item.get("blockers")
        if not isinstance(blockers, list) or blockers != sorted(set(blockers)) or any(not isinstance(blocker, str) or not blocker for blocker in blockers):
            raise RuntimeError("AGENT_TRACE_BLOCKERS_INVALID")

    summary = value.get("summary")
    if not isinstance(summary, dict) or set(summary) != SUMMARY_FIELDS:
        raise RuntimeError("AGENT_TRACE_SUMMARY_INVALID")
    if any(not isinstance(summary.get(field), int) or isinstance(summary.get(field), bool) or summary[field] < 0 for field in SUMMARY_FIELDS):
        raise RuntimeError("AGENT_TRACE_SUMMARY_INVALID")
    expected = {
        "attemptCount": len(attempts),
        "matchedCount": sum(1 for item in attempts if item["matched"]),
        "passCount": sum(1 for item in attempts if item["status"] in {"PASS", "PLANNED"}),
        "blockedCount": sum(1 for item in attempts if item["status"] == "BLOCKED"),
        "unknownCount": sum(1 for item in attempts if item["status"] == "UNKNOWN"),
    }
    if summary != expected:
        raise RuntimeError("AGENT_TRACE_SUMMARY_MISMATCH")
    expected_status = "PASS" if summary["matchedCount"] == summary["attemptCount"] else "INCOMPLETE"
    if value.get("traceStatus") not in TRACE_STATUSES or value["traceStatus"] != expected_status:
        raise RuntimeError("AGENT_TRACE_STATUS_MISMATCH")
    if value.get("readOnly") is not True or value.get("semanticAuthority") is not False or value.get("authorizesMutation") is not False:
        raise RuntimeError("AGENT_TRACE_BOUNDARY_INVALID")
    if not isinstance(value.get("traceHash"), str) or not HASH_RE.fullmatch(value["traceHash"]):
        raise RuntimeError("AGENT_TRACE_HASH_INVALID")
    core = {key: copy.deepcopy(item) for key, item in value.items() if key != "traceHash"}
    if value["traceHash"] != stable_hash(core):
        raise RuntimeError("AGENT_TRACE_HASH_MISMATCH")
    return value
