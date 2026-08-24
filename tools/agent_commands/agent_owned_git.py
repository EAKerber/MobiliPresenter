"""Lease-owned execution guard for agent-originated direct Git mutations.

This module is intentionally an internal facade, not a new semantic authority.
It preserves Coordination's existing conflict-based semantics while adding a
stricter policy for Manager/GitOps direct-Git mutations executed through the
hosted Remote Canonical carrier:

* the actor's session must own an active exclusive branch lease;
* file mutations must also be free of foreign file/path lease conflicts;
* ownership is re-observed from the canonical Coordination authority before
  every mutable provider call made by the direct-Git executor;
* the guard never acquires, renews, or releases leases itself.

The final point is deliberate for 0.1: hidden acquire/release mutations would
create durable Coordination deltas that the current Agent Cycle close cannot
account for exhaustively.  A later session facade may automate that choreography
once its transition receipts are part of the cycle trace.
"""
from __future__ import annotations

import copy
from typing import Any, Callable

from tools import coordination
from tools import remote_canonical_execution as bridge
from tools.canonical import stable_hash
from tools.coordination_remote import GhApiTransport, GitHubCoordinationAuthority

PROOF_SCHEMA = "AgentWriteLeaseProof 0.1"
POLICY_ID = "manager-gitops-direct-git-branch-owned"
MUTABLE_METHODS = {"POST", "PATCH", "PUT", "DELETE"}


def _authority_now(value: Any) -> str:
    if not hasattr(value, "isoformat"):
        raise bridge.RemoteCanonicalExecutionError("REMOTE_AGENT_WRITE_AUTHORITY_TIME_INVALID")
    return value.isoformat().replace("+00:00", "Z")


def _required_resources(command: dict[str, Any]) -> tuple[list[str], list[str]]:
    command = bridge.validate_command(command)
    if command["kind"] != "git-direct":
        raise bridge.RemoteCanonicalExecutionError("REMOTE_AGENT_WRITE_ROUTE_UNSUPPORTED")
    target = command["target"]
    owned = [coordination.normalize_resource(f"branch:{target['branch']}")]
    conflict_checked: list[str] = []
    if target["operation"] != "create-branch":
        conflict_checked.append(coordination.normalize_resource(f"file:{target['path']}"))
    return owned, conflict_checked


def _coordination_owner(command: dict[str, Any]) -> dict[str, Any]:
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


def _owned_lease_metadata_matches(
    lease: dict[str, Any],
    *,
    owner: dict[str, Any],
) -> bool:
    observed = coordination.validate_owner(lease["owner"])
    return (
        observed["session"] == owner["session"]
        and observed["role"] == owner["role"]
        and observed["branch"] == owner["branch"]
        and observed["pr"] is None
    )


def require_agent_write_ownership(
    command: dict[str, Any],
    authority: Any,
) -> dict[str, Any]:
    """Prove current same-session branch ownership without mutating Coordination."""

    command = bridge.validate_command(command)
    owner = _coordination_owner(command)
    owned_resources, conflict_resources = _required_resources(command)
    observed = authority.observe()
    state = getattr(observed, "state", None)
    head_sha = getattr(observed, "head_sha", None)
    authority_now = getattr(observed, "authority_now", None)
    if not isinstance(state, dict) or not isinstance(head_sha, str):
        raise bridge.RemoteCanonicalExecutionError("REMOTE_AGENT_WRITE_AUTHORITY_INVALID")
    coordination.validate_state(state)

    matched: list[dict[str, Any]] = []
    for resource in owned_resources:
        allowed, lease = coordination.can_write(state, resource, owner, authority_now)
        if not allowed:
            foreign = (lease or {}).get("owner") if isinstance(lease, dict) else None
            foreign_session = foreign.get("session") if isinstance(foreign, dict) else None
            raise bridge.RemoteCanonicalExecutionError(
                "REMOTE_AGENT_WRITE_LEASE_CONFLICT",
                f"{resource}:{foreign_session or 'unknown-owner'}",
            )
        if lease is None:
            raise bridge.RemoteCanonicalExecutionError(
                "REMOTE_AGENT_WRITE_LEASE_REQUIRED",
                resource,
            )
        if not _owned_lease_metadata_matches(lease, owner=owner):
            raise bridge.RemoteCanonicalExecutionError(
                "REMOTE_AGENT_WRITE_LEASE_OWNER_MISMATCH",
                resource,
            )
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
            key=lambda item: (str(item.get("resource") or ""), str(item.get("leaseId") or "")),
        ),
        "status": "PASS",
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**body, "proofHash": stable_hash(body)}


class LeaseEnforcingTransport:
    """Transport decorator that checks ownership at each mutable provider call."""

    def __init__(
        self,
        transport: Any,
        command: dict[str, Any],
        *,
        authority_factory: Callable[[Any], Any] | None = None,
    ) -> None:
        self.transport = transport
        self.command = bridge.validate_command(command)
        self.authority_factory = authority_factory
        self.proofs: list[dict[str, Any]] = []

    def _authority(self) -> Any:
        if self.authority_factory is not None:
            return self.authority_factory(self.transport)
        return GitHubCoordinationAuthority(transport=self.transport)

    def request(
        self,
        method: str,
        endpoint: str,
        *,
        payload: Any = None,
        include_headers: bool = False,
    ) -> Any:
        if method.upper() in MUTABLE_METHODS:
            self.proofs.append(require_agent_write_ownership(self.command, self._authority()))
        return self.transport.request(
            method,
            endpoint,
            payload=payload,
            include_headers=include_headers,
        )


def execute_agent_owned_git(
    command: dict[str, Any],
    *,
    source: dict[str, Any],
    transport: Any | None = None,
    authority_factory: Callable[[Any], Any] | None = None,
) -> dict[str, Any]:
    """Execute one Manager/GitOps direct-Git command under the lease-owned guard.

    The returned object remains the canonical RemoteCanonicalExecutionReceipt;
    no wrapper schema is introduced in 0.1, preserving Hosted Agent Cycle close
    compatibility.  Ownership proofs remain reconstructible from the canonical
    Coordination authority and are exposed on LeaseEnforcingTransport for tests
    and future execution-trace integration.
    """

    command = bridge.validate_command(command)
    if command["kind"] != "git-direct":
        raise bridge.RemoteCanonicalExecutionError("REMOTE_AGENT_WRITE_ROUTE_UNSUPPORTED")
    carrier = transport or GhApiTransport()
    guarded = LeaseEnforcingTransport(
        carrier,
        command,
        authority_factory=authority_factory,
    )
    return bridge.execute_command(command, source=source, transport=guarded)
