from __future__ import annotations

import copy
from typing import Any, Callable

from tools.canonical import stable_hash

SCHEMA = "AgentCycleTurnoverProjection 0.1"
ACTIONS = {
    "NO_TURNOVER",
    "SELECT_INTENT",
    "RELEASE_OWNERSHIP",
    "CLOSE_AGENT_CYCLE",
    "BEGIN_AGENT_CYCLE",
    "BLOCKED",
}
WRITE_LIFECYCLE_STATES = {"NONE", "ACTIVE", "RELEASED", "EXPIRED", "UNKNOWN"}
FIELDS = {
    "schemaVersion",
    "workRef",
    "currentIntent",
    "targetIntent",
    "candidateIntents",
    "writeLifecycleState",
    "action",
    "reasonCodes",
    "readOnly",
    "semanticAuthority",
    "authorizesMutation",
    "projectionHash",
}


class AgentCycleTurnoverError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _text(value: Any, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AgentCycleTurnoverError(code)
    return value.strip()


def _strings(value: Any, code: str) -> list[str]:
    if (
        not isinstance(value, list)
        or any(not isinstance(item, str) or not item for item in value)
    ):
        raise AgentCycleTurnoverError(code)
    return sorted(set(value))


def _next_action(readiness: Any) -> dict[str, Any] | None:
    if readiness is None:
        return None
    if not isinstance(readiness, dict):
        raise AgentCycleTurnoverError("AGENT_CYCLE_TURNOVER_READINESS_INVALID")
    value = readiness.get("nextSafeAction")
    if not isinstance(value, dict):
        raise AgentCycleTurnoverError("AGENT_CYCLE_TURNOVER_READINESS_INVALID")
    return value


def _reentry_action(reentry: Any) -> str:
    if not isinstance(reentry, dict):
        raise AgentCycleTurnoverError("AGENT_CYCLE_TURNOVER_REENTRY_INVALID")
    action = reentry.get("nextSafeAction")
    if not isinstance(action, str) or not action:
        raise AgentCycleTurnoverError("AGENT_CYCLE_TURNOVER_REENTRY_INVALID")
    return action


def _projection(
    *,
    work_id: str,
    current_intent: str | None,
    target_intent: str | None,
    candidate_intents: list[str],
    write_lifecycle_state: str,
    action: str,
    reason_codes: list[str] | None = None,
) -> dict[str, Any]:
    if action not in ACTIONS:
        raise AgentCycleTurnoverError("AGENT_CYCLE_TURNOVER_ACTION_INVALID")
    if write_lifecycle_state not in WRITE_LIFECYCLE_STATES:
        raise AgentCycleTurnoverError("AGENT_CYCLE_TURNOVER_LIFECYCLE_STATE_INVALID")
    core = {
        "schemaVersion": SCHEMA,
        "workRef": {"workId": _text(work_id, "AGENT_CYCLE_TURNOVER_WORK_REQUIRED")},
        "currentIntent": current_intent,
        "targetIntent": target_intent,
        "candidateIntents": sorted(set(candidate_intents)),
        "writeLifecycleState": write_lifecycle_state,
        "action": action,
        "reasonCodes": sorted(set(reason_codes or [])),
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**core, "projectionHash": stable_hash(core)}


def build_projection(
    *,
    work_id: str,
    reentry: dict[str, Any],
    write_lifecycle_state: str,
    readiness: dict[str, Any] | None = None,
    current_intent: str | None = None,
    target_intent: str | None = None,
) -> dict[str, Any]:
    """Derive exactly one safe turnover primitive.

    The projection is intentionally stateless. Callers re-observe Work, Hosted
    Agent Cycle and Coordination before each invocation. A target intent may be
    supplied explicitly after a prior SELECT_INTENT decision so an interruption
    between release, close and begin does not require persistent turnover state.
    """
    work_id = _text(work_id, "AGENT_CYCLE_TURNOVER_WORK_REQUIRED")
    if current_intent is not None:
        current_intent = _text(
            current_intent, "AGENT_CYCLE_TURNOVER_CURRENT_INTENT_INVALID"
        )
    if target_intent is not None:
        target_intent = _text(
            target_intent, "AGENT_CYCLE_TURNOVER_TARGET_INTENT_INVALID"
        )
    if write_lifecycle_state not in WRITE_LIFECYCLE_STATES:
        raise AgentCycleTurnoverError("AGENT_CYCLE_TURNOVER_LIFECYCLE_STATE_INVALID")

    reentry_action = _reentry_action(reentry)
    readiness_action = _next_action(readiness)
    candidates: list[str] = []

    if readiness_action is not None:
        raw_candidates = readiness_action.get("candidateIntents", [])
        candidates = _strings(
            raw_candidates, "AGENT_CYCLE_TURNOVER_CANDIDATE_INTENTS_INVALID"
        )
        if readiness_action.get("action") != "SELECT_INTENT":
            if reentry_action != "BEGIN_NEW_CYCLE" or target_intent is None:
                return _projection(
                    work_id=work_id,
                    current_intent=current_intent,
                    target_intent=target_intent,
                    candidate_intents=candidates,
                    write_lifecycle_state=write_lifecycle_state,
                    action="NO_TURNOVER",
                    reason_codes=["READINESS_DOES_NOT_REQUEST_INTENT_CHANGE"],
                )
    elif reentry_action != "BEGIN_NEW_CYCLE" or target_intent is None:
        return _projection(
            work_id=work_id,
            current_intent=current_intent,
            target_intent=target_intent,
            candidate_intents=[],
            write_lifecycle_state=write_lifecycle_state,
            action="BLOCKED",
            reason_codes=["TURNOVER_READINESS_REQUIRED"],
        )

    if target_intent is None:
        if len(candidates) == 1:
            target_intent = candidates[0]
        else:
            return _projection(
                work_id=work_id,
                current_intent=current_intent,
                target_intent=None,
                candidate_intents=candidates,
                write_lifecycle_state=write_lifecycle_state,
                action="SELECT_INTENT",
                reason_codes=["INTENT_SELECTION_REQUIRED"],
            )
    elif candidates and target_intent not in candidates:
        return _projection(
            work_id=work_id,
            current_intent=current_intent,
            target_intent=target_intent,
            candidate_intents=candidates,
            write_lifecycle_state=write_lifecycle_state,
            action="BLOCKED",
            reason_codes=["TARGET_INTENT_NOT_ADMISSIBLE"],
        )

    if current_intent is not None and target_intent == current_intent:
        return _projection(
            work_id=work_id,
            current_intent=current_intent,
            target_intent=target_intent,
            candidate_intents=candidates,
            write_lifecycle_state=write_lifecycle_state,
            action="BLOCKED",
            reason_codes=["TARGET_INTENT_EQUALS_CURRENT"],
        )

    if reentry_action == "BEGIN_NEW_CYCLE":
        return _projection(
            work_id=work_id,
            current_intent=current_intent,
            target_intent=target_intent,
            candidate_intents=candidates,
            write_lifecycle_state=write_lifecycle_state,
            action="BEGIN_AGENT_CYCLE",
            reason_codes=["PREVIOUS_CYCLE_TERMINAL"],
        )

    if reentry_action != "RESUME_EXACT_CYCLE":
        return _projection(
            work_id=work_id,
            current_intent=current_intent,
            target_intent=target_intent,
            candidate_intents=candidates,
            write_lifecycle_state=write_lifecycle_state,
            action="BLOCKED",
            reason_codes=["CURRENT_CYCLE_NOT_SAFE_FOR_TURNOVER"],
        )

    if write_lifecycle_state in {"ACTIVE", "EXPIRED"}:
        return _projection(
            work_id=work_id,
            current_intent=current_intent,
            target_intent=target_intent,
            candidate_intents=candidates,
            write_lifecycle_state=write_lifecycle_state,
            action="RELEASE_OWNERSHIP",
            reason_codes=[
                "ACTIVE_WRITE_LIFECYCLE"
                if write_lifecycle_state == "ACTIVE"
                else "EXPIRED_WRITE_LIFECYCLE_REQUIRES_RECONCILIATION"
            ],
        )
    if write_lifecycle_state in {"RELEASED", "NONE"}:
        return _projection(
            work_id=work_id,
            current_intent=current_intent,
            target_intent=target_intent,
            candidate_intents=candidates,
            write_lifecycle_state=write_lifecycle_state,
            action="CLOSE_AGENT_CYCLE",
            reason_codes=["WRITE_LIFECYCLE_CLEAN_FOR_CLOSE"],
        )
    return _projection(
        work_id=work_id,
        current_intent=current_intent,
        target_intent=target_intent,
        candidate_intents=candidates,
        write_lifecycle_state=write_lifecycle_state,
        action="BLOCKED",
        reason_codes=["WRITE_LIFECYCLE_UNKNOWN"],
    )


def validate_projection(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != FIELDS:
        raise AgentCycleTurnoverError("AGENT_CYCLE_TURNOVER_PROJECTION_INVALID")
    if value.get("schemaVersion") != SCHEMA or value.get("action") not in ACTIONS:
        raise AgentCycleTurnoverError("AGENT_CYCLE_TURNOVER_PROJECTION_INVALID")
    if value.get("writeLifecycleState") not in WRITE_LIFECYCLE_STATES:
        raise AgentCycleTurnoverError("AGENT_CYCLE_TURNOVER_PROJECTION_INVALID")
    work = value.get("workRef")
    if not isinstance(work, dict) or set(work) != {"workId"}:
        raise AgentCycleTurnoverError("AGENT_CYCLE_TURNOVER_PROJECTION_INVALID")
    _text(work.get("workId"), "AGENT_CYCLE_TURNOVER_PROJECTION_INVALID")
    for field in ("currentIntent", "targetIntent"):
        item = value.get(field)
        if item is not None:
            _text(item, "AGENT_CYCLE_TURNOVER_PROJECTION_INVALID")
    candidates = _strings(
        value.get("candidateIntents"), "AGENT_CYCLE_TURNOVER_PROJECTION_INVALID"
    )
    if candidates != value["candidateIntents"]:
        raise AgentCycleTurnoverError("AGENT_CYCLE_TURNOVER_PROJECTION_INVALID")
    reasons = _strings(
        value.get("reasonCodes"), "AGENT_CYCLE_TURNOVER_PROJECTION_INVALID"
    )
    if reasons != value["reasonCodes"]:
        raise AgentCycleTurnoverError("AGENT_CYCLE_TURNOVER_PROJECTION_INVALID")
    if (
        value.get("readOnly") is not True
        or value.get("semanticAuthority") is not False
        or value.get("authorizesMutation") is not False
    ):
        raise AgentCycleTurnoverError("AGENT_CYCLE_TURNOVER_BOUNDARY_INVALID")
    core = {key: copy.deepcopy(item) for key, item in value.items() if key != "projectionHash"}
    if value.get("projectionHash") != stable_hash(core):
        raise AgentCycleTurnoverError("AGENT_CYCLE_TURNOVER_HASH_MISMATCH")
    return value


def execute_one(
    projection: dict[str, Any],
    *,
    release_ownership: Callable[[dict[str, Any]], Any] | None = None,
    close_cycle: Callable[[dict[str, Any]], Any] | None = None,
    begin_cycle: Callable[[dict[str, Any]], Any] | None = None,
) -> dict[str, Any]:
    """Execute at most one already-existing lifecycle primitive.

    The composer owns no retry loop and no durable state. After a primitive is
    attempted, the caller must re-observe authorities and invoke the composer
    again. This is what makes interruption recovery a normal re-entry path.
    """
    value = validate_projection(projection)
    action = value["action"]
    callbacks = {
        "RELEASE_OWNERSHIP": release_ownership,
        "CLOSE_AGENT_CYCLE": close_cycle,
        "BEGIN_AGENT_CYCLE": begin_cycle,
    }
    callback = callbacks.get(action)
    if callback is None:
        return {
            "action": action,
            "submitted": False,
            "value": None,
            "reasonCodes": copy.deepcopy(value["reasonCodes"]),
            "readOnly": True,
            "semanticAuthority": False,
            "authorizesMutation": False,
        }
    payload = {
        "workRef": copy.deepcopy(value["workRef"]),
        "targetIntent": value["targetIntent"],
        "projectionHash": value["projectionHash"],
    }
    result = callback(payload)
    return {
        "action": action,
        "submitted": True,
        "value": result,
        "reasonCodes": [],
        "readOnly": False,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
