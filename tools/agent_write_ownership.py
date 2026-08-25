from __future__ import annotations

import copy
from typing import Any

from tools import coordination
from tools import coordination_ownership
from tools import remote_canonical_execution as bridge
from tools.canonical import stable_hash

PROOF_SCHEMA = "AgentWriteLeaseProof 0.1"
POLICY_ID = "manager-gitops-direct-git-branch-owned"


def _authority_now(value: Any) -> str:
    if not hasattr(value, "isoformat"):
        raise bridge.RemoteCanonicalExecutionError("REMOTE_AGENT_WRITE_AUTHORITY_TIME_INVALID")
    return value.isoformat().replace("+00:00", "Z")


def required_resources(command: dict[str, Any]) -> tuple[list[str], list[str]]:
    command = bridge.validate_command(command)
    if command["kind"] != "git-direct":
        raise bridge.RemoteCanonicalExecutionError("REMOTE_AGENT_WRITE_ROUTE_UNSUPPORTED")
    target = command["target"]
    owned = [coordination.normalize_resource(f"branch:{target['branch']}")]
    conflict_checked: list[str] = []
    if target["operation"] != "create-branch":
        conflict_checked.append(coordination.normalize_resource(f"file:{target['path']}"))
    return owned, conflict_checked


def coordination_owner(command: dict[str, Any]) -> dict[str, Any]:
    command = bridge.validate_command(command)
    target = command["target"]
    actor = command["actor"]
    return coordination.validate_owner(
        {
            "role": actor["role"],
            "session": actor["sessionId"],
            "branch": target["branch"],
            "pr": None,
        }
    )


def _translate_positive_ownership_error(
    exc: coordination.CoordinationError,
    resource: str,
) -> bridge.RemoteCanonicalExecutionError:
    if exc.code == "LEASE_REQUIRED":
        return bridge.RemoteCanonicalExecutionError(
            "REMOTE_AGENT_WRITE_LEASE_REQUIRED", resource
        )
    if exc.code == "LEASE_OWNER_MISMATCH":
        return bridge.RemoteCanonicalExecutionError(
            "REMOTE_AGENT_WRITE_LEASE_OWNER_MISMATCH", resource
        )
    if exc.code == "LEASE_CONFLICT":
        return bridge.RemoteCanonicalExecutionError(
            "REMOTE_AGENT_WRITE_LEASE_CONFLICT", resource
        )
    return bridge.RemoteCanonicalExecutionError(exc.code, exc.detail)


def prove_agent_write_ownership(
    command: dict[str, Any],
    authority: Any,
) -> dict[str, Any]:
    """Prove current same-session branch ownership without mutating Coordination."""

    command = bridge.validate_command(command)
    owner = coordination_owner(command)
    owned_resources, conflict_resources = required_resources(command)
    observed = authority.observe()
    state = getattr(observed, "state", None)
    head_sha = getattr(observed, "head_sha", None)
    authority_now = getattr(observed, "authority_now", None)
    if not isinstance(state, dict) or not isinstance(head_sha, str):
        raise bridge.RemoteCanonicalExecutionError("REMOTE_AGENT_WRITE_AUTHORITY_INVALID")
    coordination.validate_state(state)

    matched: list[dict[str, Any]] = []
    for resource in owned_resources:
        try:
            lease = coordination_ownership.require_owned_lease(
                state, resource, owner, authority_now
            )
        except coordination.CoordinationError as exc:
            raise _translate_positive_ownership_error(exc, resource) from exc
        matched.append(copy.deepcopy(lease))

    for resource in conflict_resources:
        allowed, lease = coordination.can_write(state, resource, owner, authority_now)
        if not allowed:
            foreign = (lease or {}).get("owner") if isinstance(lease, dict) else None
            foreign_session = foreign.get("session") if isinstance(foreign, dict) else None
            raise bridge.RemoteCanonicalExecutionError(
                "REMOTE_AGENT_WRITE_LEASE_CONFLICT",
                f"{resource}:{foreign_session or 'unknown-owner'}",
            )
        if lease is not None:
            matched.append(copy.deepcopy(lease))

    body = {
        "schemaVersion": PROOF_SCHEMA,
        "policy": POLICY_ID,
        "actor": copy.deepcopy(command["actor"]),
        "branch": command["target"]["branch"],
        "requiredOwnedResources": owned_resources,
        "conflictCheckedResources": conflict_resources,
        "authorityHead": head_sha,
        "authorityNow": _authority_now(authority_now),
        "matchedLeases": sorted(
            matched,
            key=lambda item: (
                str(item.get("resource") or ""),
                str(item.get("leaseId") or ""),
            ),
        ),
        "status": "PASS",
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**body, "proofHash": stable_hash(body)}
