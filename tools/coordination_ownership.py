from __future__ import annotations

import copy
from typing import Any

from tools import coordination


def require_owned_lease(
    state: dict[str, Any],
    resource: str,
    owner: dict[str, Any],
    now: Any,
) -> dict[str, Any]:
    """Return one active conflicting lease owned by exactly ``owner``.

    This is a positive-ownership precondition for opt-in writers.  It does not
    change ``coordination.can_write``: the general Coordination guard remains
    conflict-based and may return ``True, None`` when no lease exists.
    """

    coordination.validate_state(state)
    canonical_resource = coordination.normalize_resource(resource)
    canonical_owner = coordination.validate_owner(owner)
    matches = []
    for lease in coordination.active_leases(state, now):
        if coordination.resources_conflict(canonical_resource, lease["resource"]):
            matches.append(lease)
    if not matches:
        raise coordination.CoordinationError("LEASE_REQUIRED", canonical_resource)

    for lease in matches:
        observed_owner = coordination.validate_owner(lease["owner"])
        if observed_owner == canonical_owner:
            return copy.deepcopy(lease)

    same_session = [
        lease
        for lease in matches
        if coordination.validate_owner(lease["owner"])["session"]
        == canonical_owner["session"]
    ]
    if same_session:
        raise coordination.CoordinationError(
            "LEASE_OWNER_MISMATCH",
            canonical_resource,
        )
    raise coordination.CoordinationError("LEASE_CONFLICT", canonical_resource)
