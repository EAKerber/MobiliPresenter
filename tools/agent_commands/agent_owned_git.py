"""Lease-owned execution guard for agent-originated direct Git mutations.

The guard re-observes Coordination before every mutable provider call and never
acquires, renews, or releases leases itself.  Positive ownership proofing lives
in the independent ``tools.agent_write_ownership`` module so Remote Canonical
and Agent Tool admission share one implementation without importing each other.
"""
from __future__ import annotations

from typing import Any, Callable

from tools import agent_write_ownership
from tools import remote_canonical_execution as bridge
from tools.coordination_remote import GhApiTransport, GitHubCoordinationAuthority

PROOF_SCHEMA = agent_write_ownership.PROOF_SCHEMA
POLICY_ID = agent_write_ownership.POLICY_ID
MUTABLE_METHODS = {"POST", "PATCH", "PUT", "DELETE"}


def require_agent_write_ownership(
    command: dict[str, Any],
    authority: Any,
) -> dict[str, Any]:
    """Compatibility facade for the shared positive-ownership proof."""
    return agent_write_ownership.prove_agent_write_ownership(command, authority)


class LeaseEnforcingTransport:
    """Transport decorator that re-proves ownership at every mutable call."""

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
            self.proofs.append(
                require_agent_write_ownership(self.command, self._authority())
            )
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
    command = bridge.validate_command(command)
    if command["kind"] != "git-direct":
        raise bridge.RemoteCanonicalExecutionError(
            "REMOTE_AGENT_WRITE_ROUTE_UNSUPPORTED"
        )
    carrier = transport or GhApiTransport()
    guarded = LeaseEnforcingTransport(
        carrier,
        command,
        authority_factory=authority_factory,
    )
    return bridge.execute_command(command, source=source, transport=guarded)
