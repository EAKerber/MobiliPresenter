from __future__ import annotations

from copy import deepcopy
from typing import Any

from tools.agent_tools import projection as agent_tool_projection
from tools.canonical import stable_hash

SCHEMA_VERSION = "AgentCycleReadiness 0.2"
LEGACY_SCHEMA_VERSION = "AgentCycleReadiness 0.1"
STATUSES = {"PASS", "UNKNOWN", "BLOCKED", "NOT_APPLICABLE"}
DIMENSION_FIELDS = {"status", "reasonCodes"}
NEXT_ACTION_FIELDS = {
    "action",
    "toolId",
    "mode",
    "candidateToolIds",
    "candidateIntents",
    "reasonCodes",
    "readOnly",
    "semanticAuthority",
    "authorizesMutation",
}
NEXT_ACTIONS = {
    "RESOLVE_CONTEXT",
    "STOP_BLOCKED",
    "SELECT_INTENT",
    "SELECT_TOOL",
    "RESOLVE_PROVIDER",
    "PLAN_TOOL",
    "EXECUTE_READ_ONLY_TOOL",
    "RESOLVE_MUTATION_AUTHORIZATION",
}
FIELDS_V01 = {
    "schemaVersion",
    "legacyStatus",
    "contextStatus",
    "intentReadiness",
    "toolReadiness",
    "providerResolution",
    "mutationAuthorization",
    "readOnly",
    "semanticAuthority",
    "authorizesMutation",
    "readinessHash",
}
FIELDS = FIELDS_V01 | {"nextSafeAction"}


def _dimension(status: str, reason_codes: list[str] | None = None) -> dict[str, Any]:
    if status not in STATUSES:
        raise RuntimeError("AGENT_CYCLE_READINESS_STATUS_INVALID")
    if not isinstance(reason_codes or [], list) or any(
        not isinstance(item, str) or not item for item in (reason_codes or [])
    ):
        raise RuntimeError("AGENT_CYCLE_READINESS_REASON_INVALID")
    reasons = sorted(set(reason_codes or []))
    return {"status": status, "reasonCodes": reasons}


def _context_dimension(legacy_status: str, blockers: list[str]) -> dict[str, Any]:
    status = {"READY": "PASS", "UNKNOWN": "UNKNOWN", "BLOCKED": "BLOCKED"}.get(
        legacy_status
    )
    if status is None:
        raise RuntimeError("AGENT_CYCLE_READINESS_LEGACY_STATUS_INVALID")
    return _dimension(status, blockers)


def _tool_entries(tools: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        *deepcopy(tools["available"]),
        *deepcopy(tools["plannable"]),
        *deepcopy(tools["conditional"]),
    ]


def _tool_dimension(tools: dict[str, Any]) -> dict[str, Any]:
    if tools["available"] or tools["plannable"]:
        return _dimension("PASS")
    if tools["conditional"]:
        return _dimension(
            "UNKNOWN", [item["reasonCode"] for item in tools["conditional"]]
        )
    return _dimension("BLOCKED", ["NO_TOOL_SURFACE_FOR_INTENT"])


def _provider_dimension(tools: dict[str, Any]) -> dict[str, Any]:
    entries = _tool_entries(tools)
    if not entries:
        return _dimension("UNKNOWN", ["NO_TOOL_SURFACE_FOR_PROVIDER_RESOLUTION"])
    if len(entries) != 1:
        return _dimension("UNKNOWN", ["OPERATION_NOT_SELECTED"])
    entry = entries[0]
    if entry["mode"] == "plan-only":
        return _dimension(
            "NOT_APPLICABLE", ["EXECUTION_PROVIDER_NOT_REQUIRED_FOR_PLAN_ONLY"]
        )
    if "reasonCode" in entry:
        return _dimension("UNKNOWN", [entry["reasonCode"]])
    return _dimension("PASS")


def _authorization_dimension(tools: dict[str, Any]) -> dict[str, Any]:
    mutation_execute = [
        item for item in _tool_entries(tools) if item["mode"] == "mutation-execute"
    ]
    if mutation_execute:
        return _dimension("UNKNOWN", ["OPERATION_AUTHORIZATION_NOT_EVALUATED"])
    return _dimension("NOT_APPLICABLE")


def _action(
    action: str,
    *,
    tool_id: str | None = None,
    mode: str | None = None,
    candidate_tool_ids: list[str] | None = None,
    candidate_intents: list[str] | None = None,
    reason_codes: list[str] | None = None,
) -> dict[str, Any]:
    if action not in NEXT_ACTIONS:
        raise RuntimeError("AGENT_CYCLE_NEXT_SAFE_ACTION_INVALID")
    return {
        "action": action,
        "toolId": tool_id,
        "mode": mode,
        "candidateToolIds": sorted(set(candidate_tool_ids or [])),
        "candidateIntents": sorted(set(candidate_intents or [])),
        "reasonCodes": sorted(set(reason_codes or [])),
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


def _candidate_intents(tools: dict[str, Any]) -> list[str]:
    current = tools.get("declaredIntent")
    intents: set[str] = set()
    for item in tools.get("discoverable") or []:
        for intent in item.get("allowedIntents") or []:
            if intent != current:
                intents.add(intent)
    return sorted(intents)


def _next_safe_action(
    legacy_status: str, blocking_unknowns: list[str], tools: dict[str, Any]
) -> dict[str, Any]:
    if legacy_status == "BLOCKED":
        return _action("STOP_BLOCKED", reason_codes=blocking_unknowns)
    if legacy_status == "UNKNOWN":
        return _action("RESOLVE_CONTEXT", reason_codes=blocking_unknowns)

    entries = _tool_entries(tools)
    if not entries:
        intents = _candidate_intents(tools)
        if intents:
            return _action(
                "SELECT_INTENT",
                candidate_intents=intents,
                reason_codes=["NO_TOOL_SURFACE_FOR_INTENT"],
            )
        return _action(
            "STOP_BLOCKED",
            reason_codes=["NO_TOOL_SURFACE_FOR_INTENT"],
        )

    if len(entries) > 1:
        return _action(
            "SELECT_TOOL",
            candidate_tool_ids=[item["toolId"] for item in entries],
            reason_codes=["OPERATION_NOT_SELECTED"],
        )

    entry = entries[0]
    if "reasonCode" in entry:
        return _action(
            "RESOLVE_PROVIDER",
            tool_id=entry["toolId"],
            mode=entry["mode"],
            reason_codes=[entry["reasonCode"]],
        )
    if entry["mode"] == "plan-only":
        return _action("PLAN_TOOL", tool_id=entry["toolId"], mode=entry["mode"])
    if entry["mode"] == "read-only-execute":
        return _action(
            "EXECUTE_READ_ONLY_TOOL", tool_id=entry["toolId"], mode=entry["mode"]
        )
    if entry["mode"] == "mutation-execute":
        return _action(
            "RESOLVE_MUTATION_AUTHORIZATION",
            tool_id=entry["toolId"],
            mode=entry["mode"],
            reason_codes=["OPERATION_AUTHORIZATION_NOT_EVALUATED"],
        )
    raise RuntimeError("AGENT_CYCLE_NEXT_SAFE_ACTION_MODE_INVALID")


def _validate_next_safe_action(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != NEXT_ACTION_FIELDS:
        raise RuntimeError("AGENT_CYCLE_NEXT_SAFE_ACTION_FIELDS_INVALID")
    if value.get("action") not in NEXT_ACTIONS:
        raise RuntimeError("AGENT_CYCLE_NEXT_SAFE_ACTION_INVALID")
    for field in ("candidateToolIds", "candidateIntents", "reasonCodes"):
        items = value.get(field)
        if (
            not isinstance(items, list)
            or any(not isinstance(item, str) or not item for item in items)
            or items != sorted(set(items))
        ):
            raise RuntimeError("AGENT_CYCLE_NEXT_SAFE_ACTION_LIST_INVALID")
    tool_id = value.get("toolId")
    mode = value.get("mode")
    if tool_id is not None and (not isinstance(tool_id, str) or not tool_id):
        raise RuntimeError("AGENT_CYCLE_NEXT_SAFE_ACTION_TOOL_INVALID")
    if mode is not None and mode not in {
        "plan-only", "read-only-execute", "mutation-execute"
    }:
        raise RuntimeError("AGENT_CYCLE_NEXT_SAFE_ACTION_MODE_INVALID")
    if (
        value.get("readOnly") is not True
        or value.get("semanticAuthority") is not False
        or value.get("authorizesMutation") is not False
    ):
        raise RuntimeError("AGENT_CYCLE_NEXT_SAFE_ACTION_BOUNDARY_INVALID")
    return value


def _validate_inputs(
    legacy_status: str, blocking_unknowns: list[str], tools: dict[str, Any]
) -> None:
    agent_tool_projection.validate_projection(tools)
    if (
        not isinstance(blocking_unknowns, list)
        or any(not isinstance(item, str) or not item for item in blocking_unknowns)
        or blocking_unknowns != sorted(set(blocking_unknowns))
    ):
        raise RuntimeError("AGENT_CYCLE_READINESS_BLOCKERS_INVALID")
    _context_dimension(legacy_status, blocking_unknowns)


def build_projection(
    *, legacy_status: str, blocking_unknowns: list[str], tools: dict[str, Any]
) -> dict[str, Any]:
    _validate_inputs(legacy_status, blocking_unknowns, tools)
    result = _build_unvalidated(
        legacy_status=legacy_status,
        blocking_unknowns=blocking_unknowns,
        tools=tools,
        schema_version=SCHEMA_VERSION,
    )
    return validate_projection(
        result,
        legacy_status=legacy_status,
        blocking_unknowns=blocking_unknowns,
        tools=tools,
    )


def validate_projection(
    value: Any,
    *,
    legacy_status: str,
    blocking_unknowns: list[str],
    tools: dict[str, Any],
) -> dict[str, Any]:
    _validate_inputs(legacy_status, blocking_unknowns, tools)
    if not isinstance(value, dict):
        raise RuntimeError("AGENT_CYCLE_READINESS_FIELDS_INVALID")
    version = value.get("schemaVersion")
    expected = (
        FIELDS
        if version == SCHEMA_VERSION
        else FIELDS_V01
        if version == LEGACY_SCHEMA_VERSION
        else None
    )
    if expected is None:
        raise RuntimeError("AGENT_CYCLE_READINESS_SCHEMA_UNSUPPORTED")
    if set(value) != expected:
        raise RuntimeError("AGENT_CYCLE_READINESS_FIELDS_INVALID")
    for field in (
        "contextStatus",
        "intentReadiness",
        "toolReadiness",
        "providerResolution",
        "mutationAuthorization",
    ):
        dimension = value.get(field)
        if not isinstance(dimension, dict) or set(dimension) != DIMENSION_FIELDS:
            raise RuntimeError("AGENT_CYCLE_READINESS_DIMENSION_INVALID")
        _dimension(dimension.get("status"), dimension.get("reasonCodes"))
    if version == SCHEMA_VERSION:
        _validate_next_safe_action(value.get("nextSafeAction"))
    if (
        value.get("readOnly") is not True
        or value.get("semanticAuthority") is not False
        or value.get("authorizesMutation") is not False
    ):
        raise RuntimeError("AGENT_CYCLE_READINESS_BOUNDARY_INVALID")
    core = {key: deepcopy(item) for key, item in value.items() if key != "readinessHash"}
    if value.get("readinessHash") != stable_hash(core):
        raise RuntimeError("AGENT_CYCLE_READINESS_HASH_MISMATCH")
    canonical = _build_unvalidated(
        legacy_status=legacy_status,
        blocking_unknowns=blocking_unknowns,
        tools=tools,
        schema_version=version,
    )
    if value != canonical:
        raise RuntimeError("AGENT_CYCLE_READINESS_PROJECTION_MISMATCH")
    return value


def _build_unvalidated(
    *,
    legacy_status: str,
    blocking_unknowns: list[str],
    tools: dict[str, Any],
    schema_version: str,
) -> dict[str, Any]:
    core = {
        "schemaVersion": schema_version,
        "legacyStatus": legacy_status,
        "contextStatus": _context_dimension(legacy_status, blocking_unknowns),
        "intentReadiness": _dimension("PASS"),
        "toolReadiness": _tool_dimension(tools),
        "providerResolution": _provider_dimension(tools),
        "mutationAuthorization": _authorization_dimension(tools),
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    if schema_version == SCHEMA_VERSION:
        core["nextSafeAction"] = _next_safe_action(
            legacy_status, blocking_unknowns, tools
        )
    return {**core, "readinessHash": stable_hash(core)}
