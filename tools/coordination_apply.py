from __future__ import annotations

import copy
from typing import Any

from tools import coordination_transition as transition
from tools import transition_protocol as protocol
from tools.coordination_remote import CoordinationRemoteError, GitHubCoordinationAuthority


def apply(
    authority: GitHubCoordinationAuthority,
    planned: dict[str, Any],
    expected_plan: str | None,
) -> dict[str, Any]:
    try:
        transition.validate_plan(
            planned,
            repository=authority.repository,
            authority_branch=authority.authority_branch,
            state_path=authority.state_path,
        )
        protocol.require_expected_plan(planned, expected_plan)
    except RuntimeError as exc:
        raise CoordinationRemoteError(str(exc).split(":", 1)[0]) from exc

    first = authority.observe()
    expected_head = planned["intent"]["expectedAuthorityHead"]
    if first.head_sha != expected_head:
        raise CoordinationRemoteError(
            "COORDINATION_PLAN_STALE",
            f"expected {expected_head}, observed {first.head_sha}",
        )
    try:
        transition.validate_plan(
            planned,
            first.state,
            repository=authority.repository,
            authority_branch=authority.authority_branch,
            state_path=authority.state_path,
            bind_before=True,
            authority_now=first.authority_now,
        )
    except RuntimeError as exc:
        raise CoordinationRemoteError(str(exc).split(":", 1)[0]) from exc

    def planner(state, authority_now):
        try:
            transition.validate_plan(
                planned,
                state,
                repository=authority.repository,
                authority_branch=authority.authority_branch,
                state_path=authority.state_path,
                bind_before=True,
                authority_now=authority_now,
            )
        except RuntimeError as exc:
            raise CoordinationRemoteError(str(exc).split(":", 1)[0]) from exc
        return copy.deepcopy(planned["candidate"]), {
            "action": planned["action"],
            "transitionId": planned["intent"]["transitionId"],
            "plannedAt": planned["intent"]["plannedAt"],
            "planHash": planned["planHash"],
        }

    result = authority.mutate(
        planner,
        message=f"coordination: {planned['action']} {planned['intent']['transitionId']}",
        expected_revision=expected_head,
    )
    try:
        receipt = protocol.build_receipt(
            planned,
            result.state,
            authority_revision=result.after_sha,
        )
        protocol.validate_receipt(receipt, planned)
    except RuntimeError as exc:
        raise CoordinationRemoteError("COORDINATION_RECEIPT_INVALID", str(exc)) from exc
    return receipt
