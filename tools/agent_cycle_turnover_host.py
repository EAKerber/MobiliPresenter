from __future__ import annotations

import copy
from typing import Any

from tools import (
    agent_cycle,
    agent_cycle_turnover,
    agent_ownership,
    agent_reentry_guidance,
    hosted_agent_cycle,
)
from tools.agent_tools import journey_entry


class AgentCycleTurnoverHostError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _readiness(
    *,
    role: str,
    current_intent: str,
    work_id: str,
    machine: dict[str, Any],
    runtime_inspection: dict[str, Any],
) -> dict[str, Any]:
    profile = agent_cycle.entry_profile(role, current_intent)
    context = agent_cycle.build_context(
        role=role,
        declared_intent=current_intent,
        lifecycle_phase=profile["lifecyclePhase"],
        objects=profile["objects"],
        operations=profile["operations"],
        scopes=profile["scope"],
        machine=machine,
        runtime_inspection=runtime_inspection,
        work_ref={"workId": work_id},
    )
    return copy.deepcopy(context["readiness"])


def continue_work(
    *,
    work_id: str,
    machine: dict[str, Any],
    runtime_inspection: dict[str, Any],
    tool_surfaces: list[str],
    inventory_complete: bool,
    target_intent: str | None = None,
    submit: bool = False,
    transport: Any | None = None,
) -> dict[str, Any]:
    """Continue one Work across an Agent Cycle intent boundary, one step at a time."""
    if transport is None:
        raise AgentCycleTurnoverHostError("BLOCKED_EXECUTION_SURFACE")
    observed = agent_reentry_guidance.observe_turnover_context(
        work_id,
        transport=transport,
    )
    work = observed["work"]
    actor = observed["actor"]
    current_intent = observed["currentIntent"]
    handle = observed["handle"]
    reentry = observed["reentry"]

    if not isinstance(actor, dict) or not isinstance(actor.get("role"), str):
        raise AgentCycleTurnoverHostError("TURNOVER_ACTOR_UNAVAILABLE")
    role = actor["role"]

    readiness = None
    if current_intent is not None:
        readiness = _readiness(
            role=role,
            current_intent=current_intent,
            work_id=work_id,
            machine=machine,
            runtime_inspection=runtime_inspection,
        )

    branch = work.get("branch")
    lifecycle_state = "NONE"
    if handle is not None and isinstance(branch, str) and branch:
        lifecycle = agent_ownership.observe_write_lifecycle_state(
            handle=handle,
            branch=branch,
            transport=transport,
        )
        lifecycle_state = lifecycle["state"]

    projection = agent_cycle_turnover.build_projection(
        work_id=work_id,
        reentry=reentry,
        write_lifecycle_state=lifecycle_state,
        readiness=readiness,
        current_intent=current_intent,
        target_intent=target_intent,
    )
    if not submit:
        return {
            "projection": projection,
            "execution": None,
            "submitted": False,
            "readOnly": True,
            "semanticAuthority": False,
            "authorizesMutation": False,
        }

    request_id = "turnover-" + projection["projectionHash"][:24]

    def release(_: dict[str, Any]) -> dict[str, Any]:
        if handle is None or not isinstance(branch, str) or not branch:
            raise AgentCycleTurnoverHostError("TURNOVER_RELEASE_CONTEXT_UNAVAILABLE")
        return agent_ownership.release_ownership(
            handle=handle,
            branch=branch,
            request_id=request_id + "-release",
            submit=True,
            transport=transport,
        )

    def close(_: dict[str, Any]) -> dict[str, Any]:
        if handle is None:
            raise AgentCycleTurnoverHostError("TURNOVER_CLOSE_HANDLE_UNAVAILABLE")
        return hosted_agent_cycle.compose_handle_close(
            handle=handle,
            request_id=request_id + "-close",
            evidence_comment_ids=None,
            submit=True,
            transport=transport,
        )

    def begin(payload: dict[str, Any]) -> dict[str, Any]:
        target = payload.get("targetIntent")
        if not isinstance(target, str) or not target:
            raise AgentCycleTurnoverHostError("TURNOVER_TARGET_INTENT_UNAVAILABLE")
        return journey_entry.compose_entry(
            role=role,
            declared_intent=target,
            work_id=work_id,
            tool_surfaces=tool_surfaces,
            inventory_complete=inventory_complete,
            submit=True,
            transport=transport,
        )

    execution = agent_cycle_turnover.execute_one(
        projection,
        release_ownership=release,
        close_cycle=close,
        begin_cycle=begin,
    )
    return {
        "projection": projection,
        "execution": execution,
        "submitted": execution["submitted"],
        "readOnly": not execution["submitted"],
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
