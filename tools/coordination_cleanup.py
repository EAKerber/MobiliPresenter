from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

from tools import coordination


def _authority_time(now: datetime | str) -> str:
    if isinstance(now, str):
        try:
            parsed = datetime.fromisoformat(now.replace("Z", "+00:00"))
        except ValueError as exc:
            raise coordination.CoordinationError("TIME_INVALID", "cleanup authority time is invalid") from exc
    elif isinstance(now, datetime):
        parsed = now
    else:
        raise coordination.CoordinationError("TIME_INVALID", "cleanup authority time is invalid")
    if parsed.tzinfo is None:
        raise coordination.CoordinationError("TIME_INVALID", "cleanup authority time must be timezone-aware")
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def plan_closed_pr_cleanup(
    state: dict[str, Any],
    *,
    pr_number: int,
    branch: str,
    now: datetime | str,
    transition_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Plan safe cleanup for a PR that the caller has already observed as closed.

    The planner deliberately does not query GitHub. It removes only entries whose
    owner identity matches both the observed PR number and the observed head branch.
    Different PRs or branches are never treated as equivalent owners.
    """

    coordination.validate_state(state)
    if not isinstance(pr_number, int) or isinstance(pr_number, bool) or pr_number <= 0:
        raise coordination.CoordinationError("CLEANUP_IDENTITY_INVALID", "pr_number must be positive integer")
    if not isinstance(branch, str) or not branch.strip():
        raise coordination.CoordinationError("CLEANUP_IDENTITY_INVALID", "branch must be non-empty")
    canonical_branch = branch.strip()
    if not isinstance(transition_id, str) or not transition_id.strip():
        raise coordination.CoordinationError("TRANSITION_ID_INVALID", "transition_id must be non-empty")

    candidate = coordination.compact_expired(state, now)
    removed_intents: list[dict[str, Any]] = []
    removed_leases: list[dict[str, Any]] = []

    def matches(owner: dict[str, Any]) -> bool:
        canonical = coordination.validate_owner(owner)
        return canonical["pr"] == pr_number and canonical["branch"] == canonical_branch

    kept_intents = []
    for intent in candidate["intents"]:
        if matches(intent["owner"]):
            removed_intents.append(copy.deepcopy(intent))
        else:
            kept_intents.append(intent)
    candidate["intents"] = kept_intents

    kept_leases = []
    for lease in candidate["leases"]:
        if matches(lease["owner"]):
            removed_leases.append(copy.deepcopy(lease))
        else:
            kept_leases.append(lease)
    candidate["leases"] = kept_leases

    coordination.validate_state(candidate)
    event = {
        "action": "cleanup-closed-pr",
        "transitionId": transition_id.strip(),
        "at": _authority_time(now),
        "pr": pr_number,
        "branch": canonical_branch,
        "removedIntentIds": sorted(item["intentId"] for item in removed_intents),
        "removedLeaseIds": sorted(item["leaseId"] for item in removed_leases),
        "removedSessions": sorted(
            {
                item["owner"]["session"]
                for item in [*removed_intents, *removed_leases]
            }
        ),
    }
    return candidate, event
