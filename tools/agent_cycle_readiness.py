from __future__ import annotations

from copy import deepcopy
from typing import Any

from tools.agent_tools import projection as agent_tool_projection
from tools.canonical import stable_hash

SCHEMA_VERSION = "AgentCycleReadiness 0.1"
STATUSES = {"PASS", "UNKNOWN", "BLOCKED", "NOT_APPLICABLE"}
DIMENSION_FIELDS = {"status", "reasonCodes"}
FIELDS = {
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
    if not isinstance(value, dict) or set(value) != FIELDS:
        raise RuntimeError("AGENT_CYCLE_READINESS_FIELDS_INVALID")
    if value.get("schemaVersion") != SCHEMA_VERSION:
        raise RuntimeError("AGENT_CYCLE_READINESS_SCHEMA_UNSUPPORTED")
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
    )
    if value != canonical:
        raise RuntimeError("AGENT_CYCLE_READINESS_PROJECTION_MISMATCH")
    return value


def _build_unvalidated(
    *, legacy_status: str, blocking_unknowns: list[str], tools: dict[str, Any]
) -> dict[str, Any]:
    core = {
        "schemaVersion": SCHEMA_VERSION,
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
    return {**core, "readinessHash": stable_hash(core)}
