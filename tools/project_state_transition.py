"""Pure ProjectState planners built on Transition Protocol 0.1."""
from __future__ import annotations

import copy
from typing import Any, Callable

from tools import transition_protocol as protocol

Validator = Callable[[dict[str, Any]], list[dict[str, str]]]
PROJECT_STATE_SUBJECT = {"kind": "project-state", "id": "mobilipresenter"}
PROJECT_STATE_AUTHORITY = {"kind": "repository-file", "locator": {"path": "ops/state/project.json"}}


def _validated_before(before: dict[str, Any], validator: Validator) -> None:
    errors = validator(before)
    if errors:
        raise RuntimeError(f"STATE_SCHEMA_INVALID:{errors[0]['detail']}")


def checkpoint(before: dict[str, Any], checkpoint_name: str, next_transition: str, phase: str | None, *, validator: Validator) -> dict[str, Any]:
    _validated_before(before, validator)
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
    intent = {"checkpoint": checkpoint_name.strip(), "nextTransition": next_transition.strip(), "phase": phase.strip() if phase is not None else None}
    return protocol.build_plan(domain="project-state", action="checkpoint", subject=PROJECT_STATE_SUBJECT, authority=PROJECT_STATE_AUTHORITY, before=before, candidate=candidate, intent=intent, reversibility="revertible")


def _normalized_removals(remove: list[str]) -> list[str]:
    if not isinstance(remove, list) or not remove:
        raise RuntimeError("PROJECT_STATE_RETENTION_REMOVE_INVALID")
    if any(not isinstance(branch, str) or not branch for branch in remove):
        raise RuntimeError("PROJECT_STATE_RETENTION_REMOVE_INVALID")
    if len(remove) != len(set(remove)):
        raise RuntimeError("PROJECT_STATE_RETENTION_REMOVE_DUPLICATE")
    return sorted(remove)


def shrink_protected_branches(before: dict[str, Any], remove: list[str], *, validator: Validator) -> dict[str, Any]:
    _validated_before(before, validator)
    removals = _normalized_removals(remove)
    current = list(before["git"]["protectedBranches"])
    unknown = [branch for branch in removals if branch not in current]
    if unknown:
        raise RuntimeError(f"PROJECT_STATE_RETENTION_REMOVE_UNKNOWN:{unknown[0]}")
    candidate = copy.deepcopy(before)
    candidate["git"]["protectedBranches"] = [branch for branch in current if branch not in set(removals)]
    candidate_errors = validator(candidate)
    if candidate_errors:
        raise RuntimeError(f"PROJECT_STATE_RETENTION_STATE_INVALID:{candidate_errors[0]['detail']}")
    return protocol.build_plan(
        domain="project-state",
        action="shrink-protected-branches",
        subject=PROJECT_STATE_SUBJECT,
        authority=PROJECT_STATE_AUTHORITY,
        before=before,
        candidate=candidate,
        intent={"remove": removals},
        reversibility="revertible",
    )


def _validate_common(plan: dict[str, Any], *, validator: Validator) -> None:
    protocol.validate_plan(plan)
    if plan["domain"] != "project-state":
        raise RuntimeError("PROJECT_STATE_PLAN_DOMAIN_INVALID")
    if plan["subject"] != PROJECT_STATE_SUBJECT:
        raise RuntimeError("PROJECT_STATE_PLAN_SUBJECT_INVALID")
    if plan["authority"] != PROJECT_STATE_AUTHORITY:
        raise RuntimeError("PROJECT_STATE_PLAN_AUTHORITY_INVALID")
    errors = validator(plan["candidate"])
    if errors:
        raise RuntimeError(f"PROJECT_STATE_PLAN_STATE_INVALID:{errors[0]['detail']}")


def validate_checkpoint_plan(plan: dict[str, Any], *, validator: Validator) -> dict[str, Any]:
    _validate_common(plan, validator=validator)
    if plan["action"] != "checkpoint":
        raise RuntimeError("CHECKPOINT_PLAN_DOMAIN_INVALID")
    intent = plan["intent"]
    if set(intent) != {"checkpoint", "nextTransition", "phase"}:
        raise RuntimeError("CHECKPOINT_PLAN_INTENT_INVALID")
    development = plan["candidate"]["development"]
    if development["checkpoint"] != intent["checkpoint"] or development["nextTransition"] != intent["nextTransition"]:
        raise RuntimeError("CHECKPOINT_PLAN_CANDIDATE_INTENT_MISMATCH")
    if intent["phase"] is not None and development["phase"] != intent["phase"]:
        raise RuntimeError("CHECKPOINT_PLAN_CANDIDATE_INTENT_MISMATCH")
    return plan


def validate_shrink_protected_branches_plan(plan: dict[str, Any], *, validator: Validator) -> dict[str, Any]:
    _validate_common(plan, validator=validator)
    if plan["action"] != "shrink-protected-branches":
        raise RuntimeError("PROJECT_STATE_RETENTION_PLAN_ACTION_INVALID")
    intent = plan["intent"]
    if set(intent) != {"remove"}:
        raise RuntimeError("PROJECT_STATE_RETENTION_PLAN_INTENT_INVALID")
    removals = _normalized_removals(intent["remove"])
    if removals != intent["remove"]:
        raise RuntimeError("PROJECT_STATE_RETENTION_PLAN_INTENT_INVALID")
    candidate = plan["candidate"]["git"]["protectedBranches"]
    if any(branch in candidate for branch in removals):
        raise RuntimeError("PROJECT_STATE_RETENTION_PLAN_CANDIDATE_INTENT_MISMATCH")
    return plan


def rebuild(plan: dict[str, Any], before: dict[str, Any], *, validator: Validator) -> dict[str, Any]:
    action = plan.get("action") if isinstance(plan, dict) else None
    intent = plan.get("intent") if isinstance(plan, dict) else None
    if not isinstance(intent, dict):
        raise RuntimeError("PROJECT_STATE_PLAN_INTENT_INVALID")
    if action == "checkpoint":
        return checkpoint(before, intent.get("checkpoint"), intent.get("nextTransition"), intent.get("phase"), validator=validator)
    if action == "shrink-protected-branches":
        return shrink_protected_branches(before, intent.get("remove"), validator=validator)
    raise RuntimeError("PROJECT_STATE_PLAN_ACTION_UNSUPPORTED")


def validate_project_state_plan(
    plan: dict[str, Any],
    *,
    validator: Validator,
    before: dict[str, Any] | None = None,
    bind_before: bool = False,
) -> dict[str, Any]:
    action = plan.get("action") if isinstance(plan, dict) else None
    if action == "checkpoint":
        validate_checkpoint_plan(plan, validator=validator)
    elif action == "shrink-protected-branches":
        validate_shrink_protected_branches_plan(plan, validator=validator)
    else:
        raise RuntimeError("PROJECT_STATE_PLAN_ACTION_UNSUPPORTED")
    if bind_before:
        if before is None:
            raise RuntimeError("PROJECT_STATE_PLAN_BEFORE_REQUIRED")
        protocol.verify_before_state(plan, before)
        if rebuild(plan, before, validator=validator) != plan:
            raise RuntimeError("PROJECT_STATE_PLAN_DERIVATION_MISMATCH")
    return plan
