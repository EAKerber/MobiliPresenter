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


def set_protected_branches(before: dict[str, Any], branches: list[str], *, validator: Validator) -> dict[str, Any]:
    _validated_before(before, validator)
    if not isinstance(branches, list) or any(not isinstance(branch, str) or not branch for branch in branches):
        raise RuntimeError("PROJECT_STATE_PROTECTED_BRANCHES_INVALID")
    if len(branches) != len(set(branches)):
        raise RuntimeError("PROJECT_STATE_PROTECTED_BRANCHES_DUPLICATE")
    candidate = copy.deepcopy(before)
    candidate["git"]["protectedBranches"] = list(branches)
    candidate_errors = validator(candidate)
    if candidate_errors:
        raise RuntimeError(f"PROJECT_STATE_PROTECTED_BRANCHES_STATE_INVALID:{candidate_errors[0]['detail']}")
    intent = {
        "protectedBranches": list(branches),
        "removed": [branch for branch in before["git"]["protectedBranches"] if branch not in branches],
        "added": [branch for branch in branches if branch not in before["git"]["protectedBranches"]],
    }
    return protocol.build_plan(domain="project-state", action="set-protected-branches", subject=PROJECT_STATE_SUBJECT, authority=PROJECT_STATE_AUTHORITY, before=before, candidate=candidate, intent=intent, reversibility="revertible")


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


def validate_protected_branches_plan(plan: dict[str, Any], *, validator: Validator) -> dict[str, Any]:
    _validate_common(plan, validator=validator)
    if plan["action"] != "set-protected-branches":
        raise RuntimeError("PROJECT_STATE_PROTECTED_BRANCHES_PLAN_ACTION_INVALID")
    intent = plan["intent"]
    if set(intent) != {"protectedBranches", "removed", "added"}:
        raise RuntimeError("PROJECT_STATE_PROTECTED_BRANCHES_PLAN_INTENT_INVALID")
    branches = intent["protectedBranches"]
    if not isinstance(branches, list) or len(branches) != len(set(branches)) or any(not isinstance(branch, str) or not branch for branch in branches):
        raise RuntimeError("PROJECT_STATE_PROTECTED_BRANCHES_PLAN_INTENT_INVALID")
    if plan["candidate"]["git"]["protectedBranches"] != branches:
        raise RuntimeError("PROJECT_STATE_PROTECTED_BRANCHES_PLAN_CANDIDATE_INTENT_MISMATCH")
    return plan


def validate_project_state_plan(plan: dict[str, Any], *, validator: Validator) -> dict[str, Any]:
    action = plan.get("action") if isinstance(plan, dict) else None
    if action == "checkpoint":
        return validate_checkpoint_plan(plan, validator=validator)
    if action == "set-protected-branches":
        return validate_protected_branches_plan(plan, validator=validator)
    raise RuntimeError("PROJECT_STATE_PLAN_ACTION_UNSUPPORTED")
