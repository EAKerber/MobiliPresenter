"""Pure ProjectState transition planners built on Transition Protocol 0.1."""
from __future__ import annotations

import copy
from typing import Any, Callable

from tools import transition_protocol as protocol

Validator = Callable[[dict[str, Any]], list[dict[str, str]]]


def checkpoint(
    before: dict[str, Any],
    checkpoint_name: str,
    next_transition: str,
    phase: str | None,
    *,
    validator: Validator,
) -> dict[str, Any]:
    errors = validator(before)
    if errors:
        raise RuntimeError(f"STATE_SCHEMA_INVALID:{errors[0]['detail']}")
    if not isinstance(checkpoint_name, str) or not checkpoint_name.strip():
        raise RuntimeError("CHECKPOINT_NAME_INVALID")
    if not isinstance(next_transition, str) or not next_transition.strip():
        raise RuntimeError("CHECKPOINT_NEXT_TRANSITION_INVALID")
    if phase is not None and (not isinstance(phase, str) or not phase.strip()):
        raise RuntimeError("CHECKPOINT_PHASE_INVALID")

    candidate = copy.deepcopy(before)
    candidate["development"]["checkpoint"] = checkpoint_name.strip()
    candidate["development"]["nextTransition"] = next_transition.strip()
    if phase is not None:
        candidate["development"]["phase"] = phase.strip()

    candidate_errors = validator(candidate)
    if candidate_errors:
        raise RuntimeError(f"CHECKPOINT_STATE_INVALID:{candidate_errors[0]['detail']}")

    intent = {
        "checkpoint": checkpoint_name.strip(),
        "nextTransition": next_transition.strip(),
        "phase": phase.strip() if phase is not None else None,
    }
    return protocol.build_plan(
        domain="project-state",
        action="checkpoint",
        subject={"kind": "project-state", "id": str(before["project"]["id"])},
        authority={"kind": "repository-file", "locator": {"path": "ops/state/project.json"}},
        before=before,
        candidate=candidate,
        intent=intent,
        reversibility="revertible",
    )


def validate_checkpoint_plan(plan: dict[str, Any], *, validator: Validator) -> dict[str, Any]:
    protocol.validate_plan(plan)
    if plan["domain"] != "project-state" or plan["action"] != "checkpoint":
        raise RuntimeError("CHECKPOINT_PLAN_DOMAIN_INVALID")
    if plan["subject"] != {"kind": "project-state", "id": "mobilipresenter"}:
        raise RuntimeError("CHECKPOINT_PLAN_SUBJECT_INVALID")
    if plan["authority"] != {"kind": "repository-file", "locator": {"path": "ops/state/project.json"}}:
        raise RuntimeError("CHECKPOINT_PLAN_AUTHORITY_INVALID")
    intent = plan["intent"]
    if set(intent) != {"checkpoint", "nextTransition", "phase"}:
        raise RuntimeError("CHECKPOINT_PLAN_INTENT_INVALID")
    errors = validator(plan["candidate"])
    if errors:
        raise RuntimeError(f"CHECKPOINT_STATE_INVALID:{errors[0]['detail']}")
    development = plan["candidate"]["development"]
    if development["checkpoint"] != intent["checkpoint"] or development["nextTransition"] != intent["nextTransition"]:
        raise RuntimeError("CHECKPOINT_PLAN_CANDIDATE_INTENT_MISMATCH")
    if intent["phase"] is not None and development["phase"] != intent["phase"]:
        raise RuntimeError("CHECKPOINT_PLAN_CANDIDATE_INTENT_MISMATCH")
    return plan
