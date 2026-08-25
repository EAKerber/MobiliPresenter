from __future__ import annotations

import copy
import re
from typing import Any

from tools.canonical import stable_hash

REQUEST_SCHEMA = "AgentToolRequest 0.1"
PLAN_SCHEMA = "AgentToolPlan 0.1"
RESULT_SCHEMA = "AgentToolExecutionResult 0.1"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9.-]*$")
REQUEST_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
REQUEST_FIELDS = {
    "schemaVersion", "requestId", "begin", "actor", "toolId", "target", "input",
    "semanticAuthority", "authorizesMutation",
}
BEGIN_FIELDS = {"runId", "sourceSha", "contextHash"}
ACTOR_FIELDS = {"role", "workerId", "sessionId"}
PLAN_FIELDS = {
    "schemaVersion", "requestHash", "begin", "actor", "toolId", "effectClass", "mode",
    "adapter", "requiredCapabilities", "eligibleToolSurfaces", "targetPolicy", "guards",
    "target", "input", "concrete", "status", "readOnly", "semanticAuthority",
    "authorizesMutation", "planHash",
}
RESULT_FIELDS = {
    "schemaVersion", "requestHash", "planHash", "toolId", "status", "value", "blockers",
    "readOnly", "semanticAuthority", "authorizesMutation", "resultHash",
}
PLAN_EFFECT_CLASSES = {
    "read-only", "shared-durable-mutation", "specialized-maintenance", "transport-side-effect",
}
PLAN_MODES = {"mutation-execute", "plan-only", "read-only-execute"}


def _text(value: Any, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(code)
    return value.strip()


def _begin(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != BEGIN_FIELDS:
        raise RuntimeError("AGENT_TOOL_BEGIN_INVALID")
    run_id = value.get("runId")
    if not isinstance(run_id, int) or isinstance(run_id, bool) or run_id <= 0:
        raise RuntimeError("AGENT_TOOL_BEGIN_INVALID")
    if not isinstance(value.get("sourceSha"), str) or not SHA_RE.fullmatch(value["sourceSha"]):
        raise RuntimeError("AGENT_TOOL_BEGIN_INVALID")
    if not isinstance(value.get("contextHash"), str) or not HASH_RE.fullmatch(value["contextHash"]):
        raise RuntimeError("AGENT_TOOL_BEGIN_INVALID")
    return copy.deepcopy(value)


def _actor(value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != ACTOR_FIELDS:
        raise RuntimeError("AGENT_TOOL_ACTOR_INVALID")
    return {key: _text(value[key], "AGENT_TOOL_ACTOR_INVALID") for key in sorted(ACTOR_FIELDS)}


def validate_request(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != REQUEST_FIELDS:
        raise RuntimeError("AGENT_TOOL_REQUEST_FIELDS_INVALID")
    if value.get("schemaVersion") != REQUEST_SCHEMA:
        raise RuntimeError("AGENT_TOOL_REQUEST_SCHEMA_UNSUPPORTED")
    request_id = _text(value.get("requestId"), "AGENT_TOOL_REQUEST_ID_INVALID")
    if not REQUEST_ID_RE.fullmatch(request_id):
        raise RuntimeError("AGENT_TOOL_REQUEST_ID_INVALID")
    _begin(value.get("begin"))
    actor = _actor(value.get("actor"))
    if actor != {key: value["actor"][key] for key in sorted(ACTOR_FIELDS)}:
        raise RuntimeError("AGENT_TOOL_ACTOR_NOT_CANONICAL")
    tool_id = _text(value.get("toolId"), "AGENT_TOOL_ID_INVALID")
    if not ID_RE.fullmatch(tool_id):
        raise RuntimeError("AGENT_TOOL_ID_INVALID")
    if not isinstance(value.get("target"), dict) or not isinstance(value.get("input"), dict):
        raise RuntimeError("AGENT_TOOL_REQUEST_PAYLOAD_INVALID")
    if value.get("semanticAuthority") is not False or value.get("authorizesMutation") is not False:
        raise RuntimeError("AGENT_TOOL_REQUEST_MUST_NOT_AUTHORIZE")
    return value


def request_hash(value: dict[str, Any]) -> str:
    return stable_hash(validate_request(value))


def deterministic_request_id(
    *, begin: dict[str, Any], actor: dict[str, Any], tool_id: str, target: dict[str, Any], input_value: dict[str, Any]
) -> str:
    body = {
        "begin": _begin(begin),
        "actor": _actor(actor),
        "toolId": _text(tool_id, "AGENT_TOOL_ID_INVALID"),
        "target": copy.deepcopy(target),
        "input": copy.deepcopy(input_value),
    }
    return "agent-tool-" + stable_hash(body)[:24]


def validate_plan(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != PLAN_FIELDS:
        raise RuntimeError("AGENT_TOOL_PLAN_FIELDS_INVALID")
    if value.get("schemaVersion") != PLAN_SCHEMA:
        raise RuntimeError("AGENT_TOOL_PLAN_SCHEMA_UNSUPPORTED")
    for field in ("requestHash", "planHash"):
        if not isinstance(value.get(field), str) or not HASH_RE.fullmatch(value[field]):
            raise RuntimeError("AGENT_TOOL_PLAN_HASH_INVALID")
    _begin(value.get("begin")); _actor(value.get("actor"))
    if not isinstance(value.get("toolId"), str) or not ID_RE.fullmatch(value["toolId"]):
        raise RuntimeError("AGENT_TOOL_PLAN_ID_INVALID")
    effect_class = value.get("effectClass")
    mode = value.get("mode")
    status = value.get("status")
    if effect_class not in PLAN_EFFECT_CLASSES:
        raise RuntimeError("AGENT_TOOL_PLAN_EFFECT_INVALID")
    if mode not in PLAN_MODES:
        raise RuntimeError("AGENT_TOOL_PLAN_MODE_INVALID")
    if status not in {"PLANNED", "READY"}:
        raise RuntimeError("AGENT_TOOL_PLAN_STATUS_INVALID")
    if mode == "plan-only" and status != "PLANNED":
        raise RuntimeError("AGENT_TOOL_PLAN_MODE_STATUS_MISMATCH")
    if mode in {"read-only-execute", "mutation-execute"} and status != "READY":
        raise RuntimeError("AGENT_TOOL_PLAN_MODE_STATUS_MISMATCH")
    if mode == "mutation-execute" and effect_class != "shared-durable-mutation":
        raise RuntimeError("AGENT_TOOL_PLAN_MUTATION_MODE_INVALID")
    for field in ("requiredCapabilities", "eligibleToolSurfaces", "guards"):
        items = value.get(field)
        if not isinstance(items, list) or any(not isinstance(item, str) or not item for item in items):
            raise RuntimeError("AGENT_TOOL_PLAN_LIST_INVALID")
        if items != sorted(set(items)):
            raise RuntimeError("AGENT_TOOL_PLAN_LIST_INVALID")
    if not isinstance(value.get("target"), dict) or not isinstance(value.get("input"), dict) or not isinstance(value.get("concrete"), dict):
        raise RuntimeError("AGENT_TOOL_PLAN_PAYLOAD_INVALID")
    if value.get("readOnly") is not True or value.get("semanticAuthority") is not False or value.get("authorizesMutation") is not False:
        raise RuntimeError("AGENT_TOOL_PLAN_BOUNDARY_INVALID")
    body = {key: copy.deepcopy(item) for key, item in value.items() if key != "planHash"}
    if value["planHash"] != stable_hash(body):
        raise RuntimeError("AGENT_TOOL_PLAN_HASH_MISMATCH")
    return value


def validate_result(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != RESULT_FIELDS:
        raise RuntimeError("AGENT_TOOL_RESULT_FIELDS_INVALID")
    if value.get("schemaVersion") != RESULT_SCHEMA:
        raise RuntimeError("AGENT_TOOL_RESULT_SCHEMA_UNSUPPORTED")
    for field in ("requestHash", "planHash", "resultHash"):
        if not isinstance(value.get(field), str) or not HASH_RE.fullmatch(value[field]):
            raise RuntimeError("AGENT_TOOL_RESULT_HASH_INVALID")
    if value.get("status") not in {"PASS", "PLANNED", "BLOCKED", "UNKNOWN"}:
        raise RuntimeError("AGENT_TOOL_RESULT_STATUS_INVALID")
    blockers = value.get("blockers")
    if not isinstance(blockers, list) or blockers != sorted(set(blockers)) or any(not isinstance(item, str) or not item for item in blockers):
        raise RuntimeError("AGENT_TOOL_RESULT_BLOCKERS_INVALID")
    if value.get("readOnly") is not True or value.get("semanticAuthority") is not False or value.get("authorizesMutation") is not False:
        raise RuntimeError("AGENT_TOOL_RESULT_BOUNDARY_INVALID")
    body = {key: copy.deepcopy(item) for key, item in value.items() if key != "resultHash"}
    if value["resultHash"] != stable_hash(body):
        raise RuntimeError("AGENT_TOOL_RESULT_HASH_MISMATCH")
    return value
