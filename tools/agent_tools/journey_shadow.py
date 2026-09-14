"""Read-only shadow equivalence for JourneyProjection entry/re-entry.

This module never executes the projected action and creates no lifecycle authority.
It compares a derived candidate with an independently supplied manual observation so
R2 can qualify equivalence before any later paved-path promotion.
"""
from __future__ import annotations

import copy
from typing import Any

from tools.canonical import stable_hash

PROJECTION_SCHEMA = "JourneyShadowProjection 0.1"
COMPARISON_SCHEMA = "JourneyShadowComparison 0.1"
METRICS_SCHEMA = "JourneyShadowMetrics 0.1"

_ACTION_FIELDS = {
    "action",
    "targetCycleInstanceId",
    "guardContract",
    "authorityWriter",
    "semanticAuthority",
    "authorizesMutation",
}
_BEGIN_ACTIONS = {"BEGIN_AGENT_CYCLE", "BEGIN_NEW_CYCLE"}


def _action(
    action: str,
    *,
    target_cycle_instance_id: str | None,
    guard_contract: str,
) -> dict[str, Any]:
    return {
        "action": action,
        "targetCycleInstanceId": target_cycle_instance_id,
        "guardContract": guard_contract,
        "authorityWriter": None,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


def _target_cycle_instance_id(status_payload: dict[str, Any]) -> str | None:
    reentry = status_payload.get("reentry")
    if not isinstance(reentry, dict):
        return None
    target = reentry.get("targetCycle")
    if not isinstance(target, dict):
        return None
    value = target.get("cycleInstanceId")
    return value if isinstance(value, str) and value else None


def project(status_payload: dict[str, Any]) -> dict[str, Any]:
    """Project one non-authoritative entry/re-entry action in shadow only."""
    if not isinstance(status_payload, dict):
        raise RuntimeError("JOURNEY_SHADOW_STATUS_INVALID")
    journey = status_payload.get("journeyProjection")
    if not isinstance(journey, dict):
        raise RuntimeError("JOURNEY_SHADOW_JOURNEY_MISSING")
    if (
        journey.get("readOnly") is not True
        or journey.get("semanticAuthority") is not False
        or journey.get("authorizesMutation") is not False
    ):
        raise RuntimeError("JOURNEY_SHADOW_JOURNEY_BOUNDARY_INVALID")

    next_action = journey.get("nextSafeAction")
    if not isinstance(next_action, str) or not next_action:
        raise RuntimeError("JOURNEY_SHADOW_ACTION_INVALID")
    blockers = journey.get("blockers")
    if not isinstance(blockers, list) or any(not isinstance(item, str) for item in blockers):
        raise RuntimeError("JOURNEY_SHADOW_BLOCKERS_INVALID")

    projected = None
    reasons: list[str] = []
    comparison_required = False
    if blockers:
        comparison_required = True
        reasons = ["JOURNEY_BLOCKED", *blockers]
    elif next_action in _BEGIN_ACTIONS:
        comparison_required = True
        projected = _action(
            "BEGIN_AGENT_CYCLE",
            target_cycle_instance_id=None,
            guard_contract="tools.hosted_agent_cycle",
        )
    elif next_action == "RESUME_EXACT_CYCLE":
        comparison_required = True
        target_cycle_instance_id = _target_cycle_instance_id(status_payload)
        if target_cycle_instance_id is None:
            reasons = ["TARGET_CYCLE_NOT_OBSERVED"]
        else:
            projected = _action(
                "RESUME_EXACT_CYCLE",
                target_cycle_instance_id=target_cycle_instance_id,
                guard_contract="tools.hosted_cycle_reentry",
            )
    elif next_action == "NONE":
        reasons = ["JOURNEY_QUIESCENT"]
    else:
        reasons = [f"JOURNEY_ACTION_NOT_AUTOMATABLE:{next_action}"]

    result = {
        "schemaVersion": PROJECTION_SCHEMA,
        "sourceAction": next_action,
        "projectedAction": projected,
        "executesProjectedAction": False,
        "comparisonRequired": comparison_required,
        "reasonCodes": sorted(set(reasons)),
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**result, "projectionHash": stable_hash(result)}


def _manual_action(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != _ACTION_FIELDS:
        raise RuntimeError("JOURNEY_SHADOW_MANUAL_ACTION_INVALID")
    if (
        not isinstance(value.get("action"), str)
        or not value["action"]
        or (
            value.get("targetCycleInstanceId") is not None
            and (
                not isinstance(value["targetCycleInstanceId"], str)
                or not value["targetCycleInstanceId"]
            )
        )
        or not isinstance(value.get("guardContract"), str)
        or not value["guardContract"]
        or (
            value.get("authorityWriter") is not None
            and (
                not isinstance(value["authorityWriter"], str)
                or not value["authorityWriter"]
            )
        )
        or value.get("semanticAuthority") is not False
        or value.get("authorizesMutation") is not False
    ):
        raise RuntimeError("JOURNEY_SHADOW_MANUAL_ACTION_INVALID")
    return copy.deepcopy(value)


def compare(
    shadow_projection: dict[str, Any],
    manual_observed_action: dict[str, Any] | None,
) -> dict[str, Any]:
    """Compare a projected action with an independent manual observation."""
    if (
        not isinstance(shadow_projection, dict)
        or shadow_projection.get("schemaVersion") != PROJECTION_SCHEMA
        or shadow_projection.get("executesProjectedAction") is not False
        or shadow_projection.get("readOnly") is not True
        or shadow_projection.get("semanticAuthority") is not False
        or shadow_projection.get("authorizesMutation") is not False
    ):
        raise RuntimeError("JOURNEY_SHADOW_PROJECTION_INVALID")
    manual = _manual_action(manual_observed_action)
    projected = shadow_projection.get("projectedAction")

    differences: list[str] = []
    if projected is None:
        status = "NOT_COMPARABLE"
    elif manual is None:
        status = "DIVERGED"
        differences = ["manualObservedAction"]
    else:
        differences = sorted(
            field for field in _ACTION_FIELDS if manual.get(field) != projected.get(field)
        )
        status = "EQUIVALENT" if not differences else "DIVERGED"

    result = {
        "schemaVersion": COMPARISON_SCHEMA,
        "status": status,
        "manualObservedAction": manual,
        "projectedAction": copy.deepcopy(projected),
        "differences": differences,
        "projectionHash": shadow_projection.get("projectionHash"),
        "projectedActionExecuted": False,
        "comparisonRequired": shadow_projection.get("comparisonRequired") is True,
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**result, "comparisonHash": stable_hash(result)}


def summarize(comparisons: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize canary evidence without turning metrics into authority."""
    if not isinstance(comparisons, list) or not comparisons:
        raise RuntimeError("JOURNEY_SHADOW_COMPARISONS_REQUIRED")
    counts = {"EQUIVALENT": 0, "DIVERGED": 0, "NOT_COMPARABLE": 0}
    required_not_comparable = 0
    for comparison in comparisons:
        if (
            not isinstance(comparison, dict)
            or comparison.get("schemaVersion") != COMPARISON_SCHEMA
            or comparison.get("status") not in counts
            or not isinstance(comparison.get("comparisonRequired"), bool)
            or comparison.get("projectedActionExecuted") is not False
        ):
            raise RuntimeError("JOURNEY_SHADOW_COMPARISON_INVALID")
        counts[comparison["status"]] += 1
        if (
            comparison["status"] == "NOT_COMPARABLE"
            and comparison.get("comparisonRequired") is True
        ):
            required_not_comparable += 1
    comparable = counts["EQUIVALENT"] + counts["DIVERGED"]
    gate = (
        "BLOCKED"
        if counts["DIVERGED"]
        else "UNKNOWN"
        if required_not_comparable
        else "PASS"
        if comparable
        else "UNKNOWN"
    )
    result = {
        "schemaVersion": METRICS_SCHEMA,
        "total": len(comparisons),
        "comparable": comparable,
        "equivalent": counts["EQUIVALENT"],
        "diverged": counts["DIVERGED"],
        "notComparable": counts["NOT_COMPARABLE"],
        "requiredNotComparable": required_not_comparable,
        "equivalenceRate": counts["EQUIVALENT"] / comparable if comparable else None,
        "gateDisposition": gate,
        "projectedActionsExecuted": 0,
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**result, "metricsHash": stable_hash(result)}
