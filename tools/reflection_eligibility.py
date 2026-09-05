from __future__ import annotations

import copy
from typing import Any

from tools import maintenance_inspect, scheduler_plan, scheduler_snapshot
from tools.canonical import stable_hash
from tools.semantics.actions import OperationalAction

SCHEMA_VERSION = "ReflectionEligibility 0.1"
REPOSITORY = scheduler_snapshot.REPOSITORY
STATUSES = {
    "OPERATIONAL_PRIORITY",
    "LEGITIMATE_WAIT",
    "INSUFFICIENT_OBSERVATION",
    "REFLECTION_ELIGIBLE",
}
NEXT_SAFE_ACTIONS = {
    "OPERATIONAL_PRIORITY": "HONOR_OPERATIONAL_PRIORITY",
    "LEGITIMATE_WAIT": "WAIT_OR_REFLECT",
    "INSUFFICIENT_OBSERVATION": "OBSERVE",
    "REFLECTION_ELIGIBLE": "REFLECT",
}
WAIT_REASON_CODES = {
    "WORK_WAITING",
    "WORK_DEPENDENCY_BLOCKED",
    "WORK_PR_CI_PENDING",
}
HUMAN_PRIORITY_CODES = {
    "CAPABILITY_EMPTY_LIMIT",
}
FIELDS = {
    "schemaVersion",
    "repository",
    "schedulerSnapshotHash",
    "projectMachineInspectionHash",
    "routineInspectionHash",
    "maintenanceInspectionHash",
    "schedulerPlanHash",
    "operationalAction",
    "operationalReasonCode",
    "focus",
    "workId",
    "status",
    "reflectionEligible",
    "nextSafeAction",
    "reasonCodes",
    "decisionScope",
    "readOnly",
    "semanticAuthority",
    "authorizesMutation",
    "inspectionHash",
}


def _text_or_none(value: Any, code: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(code)
    return value


def _classification(action: str, reason_code: str) -> tuple[str, list[str]]:
    action = OperationalAction.parse(action).value
    if not isinstance(reason_code, str) or not reason_code:
        raise RuntimeError("REFLECTION_ELIGIBILITY_REASON_CODE_INVALID")

    if action in {
        OperationalAction.RECONCILE.value,
        OperationalAction.HANDOFF.value,
    }:
        return "OPERATIONAL_PRIORITY", [reason_code]

    if action == OperationalAction.CONTINUE.value:
        if reason_code == "NEXT_TRANSITION_AVAILABLE":
            return "REFLECTION_ELIGIBLE", [
                "NEXT_TRANSITION_AVAILABLE",
                "ROADMAP_DIRECTION_NOT_ASSIGNMENT",
            ]
        return "OPERATIONAL_PRIORITY", [reason_code]

    if action == OperationalAction.PAUSE.value:
        if reason_code in WAIT_REASON_CODES:
            return "LEGITIMATE_WAIT", [reason_code]
        return "INSUFFICIENT_OBSERVATION", [reason_code]

    if action == OperationalAction.NEEDS_HUMAN.value:
        if reason_code in HUMAN_PRIORITY_CODES:
            return "OPERATIONAL_PRIORITY", [reason_code]
        return "INSUFFICIENT_OBSERVATION", [reason_code]

    raise RuntimeError("REFLECTION_ELIGIBILITY_ACTION_INVALID")


def build_inspection(
    snapshot: dict[str, Any],
    *,
    source_machine: dict[str, Any],
    routine_inspection: dict[str, Any],
    readback_machine: dict[str, Any],
    expected_heads: dict[str, str] | None = None,
) -> dict[str, Any]:
    scheduler_snapshot.validate_snapshot(
        snapshot,
        source_machine=source_machine,
        routine_inspection=routine_inspection,
        readback_machine=readback_machine,
        expected_heads=expected_heads,
    )
    inspection = snapshot["inspection"]
    plan = snapshot["plan"]
    maintenance_inspect.validate_derivation(
        inspection, source_machine, routine_inspection
    )
    scheduler_plan.validate_derivation(plan, inspection)

    recommendation = inspection["recommendation"]
    if (
        plan["action"] != recommendation["action"]
        or plan["reasonCode"] != recommendation["reasonCode"]
        or plan["focus"] != recommendation["focus"]
    ):
        raise RuntimeError("REFLECTION_ELIGIBILITY_SCHEDULER_BINDING_MISMATCH")

    status, reasons = _classification(plan["action"], plan["reasonCode"])
    focus = _text_or_none(plan.get("focus"), "REFLECTION_ELIGIBILITY_FOCUS_INVALID")
    work_id = _text_or_none(
        recommendation.get("workId"), "REFLECTION_ELIGIBILITY_WORK_ID_INVALID"
    )
    if status == "REFLECTION_ELIGIBLE" and (
        focus != "development"
        or work_id is not None
        or plan["dispatch"].get("channelClass") != "supervisor"
    ):
        raise RuntimeError("REFLECTION_ELIGIBILITY_ROADMAP_DIRECTION_INVALID")

    body = {
        "schemaVersion": SCHEMA_VERSION,
        "repository": REPOSITORY,
        "schedulerSnapshotHash": snapshot["snapshotHash"],
        "projectMachineInspectionHash": snapshot["projectMachineInspectionHash"],
        "routineInspectionHash": snapshot["routineInspectionHash"],
        "maintenanceInspectionHash": inspection["inspectionHash"],
        "schedulerPlanHash": plan["planHash"],
        "operationalAction": plan["action"],
        "operationalReasonCode": plan["reasonCode"],
        "focus": focus,
        "workId": work_id,
        "status": status,
        "reflectionEligible": status in {"LEGITIMATE_WAIT", "REFLECTION_ELIGIBLE"},
        "nextSafeAction": NEXT_SAFE_ACTIONS[status],
        "reasonCodes": sorted(set(reasons)),
        "decisionScope": "reflection-eligibility-only",
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    value = {**body, "inspectionHash": stable_hash(body)}
    validate_inspection(value)
    return value


def validate_inspection(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != FIELDS:
        raise RuntimeError("REFLECTION_ELIGIBILITY_FIELDS_INVALID")
    if value.get("schemaVersion") != SCHEMA_VERSION:
        raise RuntimeError("REFLECTION_ELIGIBILITY_SCHEMA_UNSUPPORTED")
    if value.get("repository") != REPOSITORY:
        raise RuntimeError("REFLECTION_ELIGIBILITY_REPOSITORY_MISMATCH")
    action = OperationalAction.parse(str(value.get("operationalAction") or "")).value
    reason_code = value.get("operationalReasonCode")
    status, reasons = _classification(action, reason_code)
    if value.get("status") != status:
        raise RuntimeError("REFLECTION_ELIGIBILITY_STATUS_MISMATCH")
    if value.get("reflectionEligible") is not (
        status in {"LEGITIMATE_WAIT", "REFLECTION_ELIGIBLE"}
    ):
        raise RuntimeError("REFLECTION_ELIGIBILITY_FLAG_MISMATCH")
    if value.get("nextSafeAction") != NEXT_SAFE_ACTIONS[status]:
        raise RuntimeError("REFLECTION_ELIGIBILITY_NEXT_ACTION_MISMATCH")
    if value.get("reasonCodes") != sorted(set(reasons)):
        raise RuntimeError("REFLECTION_ELIGIBILITY_REASONS_MISMATCH")
    _text_or_none(value.get("focus"), "REFLECTION_ELIGIBILITY_FOCUS_INVALID")
    _text_or_none(value.get("workId"), "REFLECTION_ELIGIBILITY_WORK_ID_INVALID")
    if (
        value.get("decisionScope") != "reflection-eligibility-only"
        or value.get("readOnly") is not True
        or value.get("semanticAuthority") is not False
        or value.get("authorizesMutation") is not False
    ):
        raise RuntimeError("REFLECTION_ELIGIBILITY_BOUNDARY_INVALID")
    for field in (
        "schedulerSnapshotHash",
        "projectMachineInspectionHash",
        "routineInspectionHash",
        "maintenanceInspectionHash",
        "schedulerPlanHash",
    ):
        digest = value.get(field)
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest)
        ):
            raise RuntimeError("REFLECTION_ELIGIBILITY_HASH_INVALID")
    supplied = value.get("inspectionHash")
    body = {
        key: copy.deepcopy(item)
        for key, item in value.items()
        if key != "inspectionHash"
    }
    if not isinstance(supplied, str) or supplied != stable_hash(body):
        raise RuntimeError("REFLECTION_ELIGIBILITY_INSPECTION_HASH_MISMATCH")
    return value


def validate_derivation(
    value: dict[str, Any],
    snapshot: dict[str, Any],
    *,
    source_machine: dict[str, Any],
    routine_inspection: dict[str, Any],
    readback_machine: dict[str, Any],
    expected_heads: dict[str, str] | None = None,
) -> dict[str, Any]:
    validate_inspection(value)
    expected = build_inspection(
        snapshot,
        source_machine=source_machine,
        routine_inspection=routine_inspection,
        readback_machine=readback_machine,
        expected_heads=expected_heads,
    )
    if value != expected:
        raise RuntimeError("REFLECTION_ELIGIBILITY_DERIVATION_MISMATCH")
    return value
