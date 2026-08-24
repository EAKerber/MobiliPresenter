from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable

from tools import maintenance_inspect, project_machine, routines, runtime_capabilities, scheduler_plan
from tools.agent_tools import policy as agent_tool_policy
from tools.agent_tools import projection as agent_tool_projection
from tools.canonical import stable_hash
from tools.semantics import brief as semantic_brief

SCHEMA_VERSION = "AgentCycleContext 0.2"
LEGACY_SCHEMA_VERSION = "AgentCycleContext 0.1"
LEGACY_CLOSE_VERSION = "AgentCycleCloseFoundation 0.1"
CLOSE_VERSION = "AgentCycleCloseContract 0.1"
STATUSES = {"READY", "UNKNOWN", "BLOCKED"}
SLOT_FIELDS = {"status", "value", "reasonCode"}
CLOSE_EVIDENCE = [
    "baseline",
    "reobserve-after",
    "derive-before-after-delta",
    "delegate-required-mutations-to-canonical-writers",
    "aggregate-readback",
    "emit-agent-cycle-receipt",
]


def entry_profile(role: str, declared_intent: str) -> dict[str, Any]:
    return agent_tool_policy.entry_profile(role, declared_intent)


FIELDS = {
    "schemaVersion", "cycleId", "status", "repository", "semanticContext",
    "projectMachine", "runtimeCapabilities", "routineInspection",
    "maintenanceInspection", "schedulerPlan", "semanticBrief", "agentTools", "baseline",
    "blockingUnknowns", "closeRequirements", "readOnly", "semanticAuthority",
    "authorizesMutation", "contextHash",
}
LEGACY_FIELDS = FIELDS - {"agentTools"}


def _slot_pass(value: dict[str, Any]) -> dict[str, Any]:
    return {"status": "PASS", "value": value, "reasonCode": None}


def _slot_unknown(reason: Exception | str) -> dict[str, Any]:
    code = str(reason).split(":", 1)[0] or "DERIVATION_UNAVAILABLE"
    return {"status": "UNKNOWN", "value": None, "reasonCode": code}


def _validate_slot(slot: Any, *, validator: Callable[[dict[str, Any]], Any] | None = None) -> dict[str, Any]:
    if not isinstance(slot, dict) or set(slot) != SLOT_FIELDS:
        raise RuntimeError("AGENT_CYCLE_ARTIFACT_SLOT_FIELDS_INVALID")
    status = slot.get("status")
    if status not in {"PASS", "UNKNOWN"}:
        raise RuntimeError("AGENT_CYCLE_ARTIFACT_SLOT_STATUS_INVALID")
    if status == "PASS":
        if not isinstance(slot.get("value"), dict) or slot.get("reasonCode") is not None:
            raise RuntimeError("AGENT_CYCLE_ARTIFACT_SLOT_PASS_INVALID")
        if validator is not None:
            validator(slot["value"])
    else:
        if slot.get("value") is not None:
            raise RuntimeError("AGENT_CYCLE_ARTIFACT_SLOT_UNKNOWN_VALUE_INVALID")
        if not isinstance(slot.get("reasonCode"), str) or not slot["reasonCode"]:
            raise RuntimeError("AGENT_CYCLE_ARTIFACT_SLOT_REASON_INVALID")
    return slot


def _aggregate_status(machine, routine_slot, maintenance_slot, scheduler_slot, brief):
    blockers: list[str] = []
    hard = False
    unknown = False
    for name, status in (
        ("PROJECT_MACHINE_TRUST", machine["trust"]["status"]),
        ("PROJECT_MACHINE_COHERENCE", machine["coherence"]["status"]),
    ):
        if status == "FAIL":
            hard = True; blockers.append(f"{name}_FAIL")
        elif status == "UNKNOWN":
            unknown = True; blockers.append(f"{name}_UNKNOWN")
    for name, slot in (
        ("ROUTINE_INSPECTION", routine_slot),
        ("MAINTENANCE_INSPECTION", maintenance_slot),
        ("SCHEDULER_PLAN", scheduler_slot),
    ):
        if slot["status"] == "UNKNOWN":
            unknown = True; blockers.append(f"{name}_UNKNOWN:{slot['reasonCode']}")
        elif name == "ROUTINE_INSPECTION":
            routine_status = slot["value"]["status"]
            if routine_status == "FAIL":
                hard = True; blockers.append("ROUTINE_INSPECTION_FAIL")
            elif routine_status == "UNKNOWN":
                unknown = True; blockers.append("ROUTINE_INSPECTION_RESULT_UNKNOWN")
    projection = brief["capabilityProjection"]
    if projection["missingCoverage"]:
        hard = True
        blockers.extend(f"SEMANTIC_COVERAGE:{item}" for item in projection["missingCoverage"])
    if projection["requiredUnavailable"]:
        unknown = True
        blockers.extend(f"REQUIRED_CAPABILITY_UNAVAILABLE:{item}" for item in projection["requiredUnavailable"])
    return ("BLOCKED" if hard else ("UNKNOWN" if unknown else "READY"), sorted(set(blockers)))


def _derive_routine(machine):
    try:
        value = routines.build_inspection(machine); routines.validate_inspection(value, machine); return _slot_pass(value)
    except RuntimeError as exc:
        return _slot_unknown(exc)


def _derive_maintenance(machine, routine_slot):
    if routine_slot["status"] != "PASS":
        return _slot_unknown("ROUTINE_INSPECTION_UNAVAILABLE")
    try:
        value = maintenance_inspect.from_inputs(machine, routine_slot["value"]); maintenance_inspect.validate_inspection(value); return _slot_pass(value)
    except RuntimeError as exc:
        return _slot_unknown(exc)


def _derive_scheduler(maintenance_slot):
    if maintenance_slot["status"] != "PASS":
        return _slot_unknown("MAINTENANCE_INSPECTION_UNAVAILABLE")
    try:
        value = scheduler_plan.build_plan(maintenance_slot["value"]); scheduler_plan.validate_plan(value); return _slot_pass(value)
    except RuntimeError as exc:
        return _slot_unknown(exc)


def _close_requirements() -> dict[str, Any]:
    return {
        "schemaVersion": CLOSE_VERSION,
        "required": True,
        "implemented": True,
        "nextSlice": None,
        "requiredEvidence": list(CLOSE_EVIDENCE),
        "reminder": "CLOSE_REQUIRED_AFTER_WORK",
    }


def build_context(*, role, declared_intent, lifecycle_phase, objects, operations, scopes, machine, runtime_inspection):
    project_machine.validate_inspection(machine)
    runtime_capabilities.validate_inspection(runtime_inspection)
    semantic_context = semantic_brief.normalize_context(
        role=role, declared_intent=declared_intent, lifecycle_phase=lifecycle_phase,
        objects=objects, operations=operations, scopes=scopes,
    )
    routine_slot = _derive_routine(machine)
    maintenance_slot = _derive_maintenance(machine, routine_slot)
    scheduler_slot = _derive_scheduler(maintenance_slot)
    brief = semantic_brief.build_brief(semantic_context, runtime_inspection)
    tools = agent_tool_projection.build_projection(semantic_context, brief)
    status, blockers = _aggregate_status(machine, routine_slot, maintenance_slot, scheduler_slot, brief)
    baseline = {
        "projectMachineInspectionHash": machine["inspectionHash"],
        "projectStateHash": machine["project"]["stateHash"],
        "runtimeCapabilityInspectionHash": runtime_inspection["inspectionHash"],
        "routineInspectionHash": routine_slot["value"]["inspectionHash"] if routine_slot["status"] == "PASS" else None,
        "maintenanceInspectionHash": maintenance_slot["value"]["inspectionHash"] if maintenance_slot["status"] == "PASS" else None,
        "schedulerPlanHash": scheduler_slot["value"]["planHash"] if scheduler_slot["status"] == "PASS" else None,
        "semanticBriefHash": brief["briefHash"],
        "agentToolProjectionHash": tools["projectionHash"],
        "sourceHeads": deepcopy(machine["sourceHeads"]),
    }
    baseline_hash = stable_hash(baseline); baseline["baselineHash"] = baseline_hash
    body = {
        "schemaVersion": SCHEMA_VERSION,
        "cycleId": f"cycle-{baseline_hash[:20]}",
        "status": status,
        "repository": machine["repository"],
        "semanticContext": semantic_context,
        "projectMachine": machine,
        "runtimeCapabilities": runtime_inspection,
        "routineInspection": routine_slot,
        "maintenanceInspection": maintenance_slot,
        "schedulerPlan": scheduler_slot,
        "semanticBrief": brief,
        "agentTools": tools,
        "baseline": baseline,
        "blockingUnknowns": blockers,
        "closeRequirements": _close_requirements(),
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    result = {**body, "contextHash": stable_hash(body)}
    validate_context(result)
    return result


def _expected_baseline(value: dict[str, Any]) -> dict[str, Any]:
    routine_slot = value["routineInspection"]
    maintenance_slot = value["maintenanceInspection"]
    scheduler_slot = value["schedulerPlan"]
    body = {
        "projectMachineInspectionHash": value["projectMachine"]["inspectionHash"],
        "projectStateHash": value["projectMachine"]["project"]["stateHash"],
        "runtimeCapabilityInspectionHash": value["runtimeCapabilities"]["inspectionHash"],
        "routineInspectionHash": routine_slot["value"]["inspectionHash"] if routine_slot["status"] == "PASS" else None,
        "maintenanceInspectionHash": maintenance_slot["value"]["inspectionHash"] if maintenance_slot["status"] == "PASS" else None,
        "schedulerPlanHash": scheduler_slot["value"]["planHash"] if scheduler_slot["status"] == "PASS" else None,
        "semanticBriefHash": value["semanticBrief"]["briefHash"],
    }
    if value.get("schemaVersion") == SCHEMA_VERSION:
        body["agentToolProjectionHash"] = value["agentTools"]["projectionHash"]
    body["sourceHeads"] = deepcopy(value["projectMachine"]["sourceHeads"])
    return {**body, "baselineHash": stable_hash(body)}


def _validate_close(close: Any) -> None:
    if not isinstance(close, dict):
        raise RuntimeError("AGENT_CYCLE_CLOSE_FOUNDATION_INVALID")
    common = (
        close.get("required") is True
        and close.get("reminder") == "CLOSE_REQUIRED_AFTER_WORK"
        and close.get("requiredEvidence") == CLOSE_EVIDENCE
    )
    if not common:
        raise RuntimeError("AGENT_CYCLE_CLOSE_BOUNDARY_INVALID")
    if close.get("schemaVersion") == LEGACY_CLOSE_VERSION:
        if close.get("implemented") is not False or close.get("nextSlice") != "M10-OS1C":
            raise RuntimeError("AGENT_CYCLE_CLOSE_BOUNDARY_INVALID")
        return
    if close.get("schemaVersion") == CLOSE_VERSION:
        if close.get("implemented") is not True or close.get("nextSlice") is not None:
            raise RuntimeError("AGENT_CYCLE_CLOSE_BOUNDARY_INVALID")
        return
    raise RuntimeError("AGENT_CYCLE_CLOSE_FOUNDATION_INVALID")


def validate_context(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError("AGENT_CYCLE_CONTEXT_FIELDS_INVALID")
    version = value.get("schemaVersion")
    expected_fields = FIELDS if version == SCHEMA_VERSION else LEGACY_FIELDS if version == LEGACY_SCHEMA_VERSION else None
    if expected_fields is None:
        raise RuntimeError("AGENT_CYCLE_CONTEXT_SCHEMA_UNSUPPORTED")
    if set(value) != expected_fields:
        raise RuntimeError("AGENT_CYCLE_CONTEXT_FIELDS_INVALID")
    if value.get("status") not in STATUSES:
        raise RuntimeError("AGENT_CYCLE_CONTEXT_STATUS_INVALID")
    cycle_id = value.get("cycleId")
    if not isinstance(cycle_id, str) or not cycle_id.startswith("cycle-") or len(cycle_id) != 26:
        raise RuntimeError("AGENT_CYCLE_ID_INVALID")
    if value.get("readOnly") is not True or value.get("semanticAuthority") is not False or value.get("authorizesMutation") is not False:
        raise RuntimeError("AGENT_CYCLE_CONTEXT_BOUNDARY_INVALID")
    project_machine.validate_inspection(value.get("projectMachine"))
    runtime_capabilities.validate_inspection(value.get("runtimeCapabilities"))
    _validate_slot(value.get("routineInspection"), validator=lambda item: routines.validate_inspection(item, value["projectMachine"]))
    _validate_slot(value.get("maintenanceInspection"), validator=maintenance_inspect.validate_inspection)
    _validate_slot(value.get("schedulerPlan"), validator=scheduler_plan.validate_plan)
    semantic_brief.validate_brief(value.get("semanticBrief")); semantic_brief.validate_context(value.get("semanticContext"))
    if value["semanticBrief"]["context"] != value["semanticContext"]:
        raise RuntimeError("AGENT_CYCLE_SEMANTIC_CONTEXT_MISMATCH")
    if version == SCHEMA_VERSION:
        agent_tool_projection.validate_projection(value.get("agentTools"))
        if value["agentTools"]["role"] != value["semanticContext"]["role"] or value["agentTools"]["declaredIntent"] != value["semanticContext"]["declaredIntent"]:
            raise RuntimeError("AGENT_CYCLE_AGENT_TOOL_CONTEXT_MISMATCH")
    baseline = value.get("baseline")
    if not isinstance(baseline, dict) or "baselineHash" not in baseline:
        raise RuntimeError("AGENT_CYCLE_BASELINE_INVALID")
    supplied_baseline = baseline.get("baselineHash")
    expected_baseline_hash = stable_hash({key: deepcopy(item) for key, item in baseline.items() if key != "baselineHash"})
    if supplied_baseline != expected_baseline_hash:
        raise RuntimeError("AGENT_CYCLE_BASELINE_HASH_MISMATCH")
    if baseline != _expected_baseline(value):
        raise RuntimeError("AGENT_CYCLE_BASELINE_ARTIFACT_MISMATCH")
    if value["cycleId"] != f"cycle-{supplied_baseline[:20]}":
        raise RuntimeError("AGENT_CYCLE_ID_MISMATCH")
    _validate_close(value.get("closeRequirements"))
    body = {key: deepcopy(item) for key, item in value.items() if key != "contextHash"}
    if value.get("contextHash") != stable_hash(body):
        raise RuntimeError("AGENT_CYCLE_CONTEXT_HASH_MISMATCH")
    return value
