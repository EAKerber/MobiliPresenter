from __future__ import annotations

import copy
from typing import Any, Callable

from tools.agent_tools import contracts
from tools.agent_tools import guard_proofs
from tools.canonical import stable_hash

MUTATION_EFFECT = "shared-durable-mutation"

# AT3A registers read-only proof providers, but AgentToolPolicyCatalog 0.1 still
# has no mutation execution mode.  Proof availability therefore cannot by
# itself create a write path.
GUARD_PROOF_PROVIDERS: dict[str, Callable[..., dict[str, Any]]] = {
    "coordination-lease-owned": guard_proofs.prove_coordination_lease_owned,
    "git-cas": guard_proofs.prove_git_cas,
}


def missing_guard_proof_providers(plan: dict[str, Any]) -> list[str]:
    contracts.validate_plan(plan)
    if plan["effectClass"] != MUTATION_EFFECT:
        return []
    return sorted(guard for guard in plan["guards"] if guard not in GUARD_PROOF_PROVIDERS)


def collect_guard_proofs(
    plan: dict[str, Any],
    *,
    transport: Any | None = None,
    authority_factory: Callable[[Any], Any] | None = None,
) -> dict[str, Any]:
    contracts.validate_plan(plan)
    if plan["effectClass"] != MUTATION_EFFECT:
        raise RuntimeError("AGENT_TOOL_GUARD_PROOFS_NOT_REQUIRED")
    missing = missing_guard_proof_providers(plan)
    if missing:
        raise RuntimeError("AGENT_TOOL_GUARD_PROOF_PROVIDER_MISSING:" + ",".join(missing))

    proofs: dict[str, Any] = {}
    for guard in plan["guards"]:
        provider = GUARD_PROOF_PROVIDERS[guard]
        if guard == "coordination-lease-owned":
            proof = provider(
                plan,
                transport=transport,
                authority_factory=authority_factory,
            )
        else:
            proof = provider(plan, transport=transport)
        proofs[guard] = proof

    core = {
        "schemaVersion": guard_proofs.PROOF_SET_SCHEMA,
        "requestHash": plan["requestHash"],
        "planHash": plan["planHash"],
        "actor": copy.deepcopy(plan["actor"]),
        "target": copy.deepcopy(plan["target"]),
        "proofs": proofs,
        "status": "PASS",
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    value = {**core, "proofSetHash": stable_hash(core)}
    return guard_proofs.validate_proof_set(value, plan=plan)


def assert_execution_admitted(
    plan: dict[str, Any],
    proof_set: dict[str, Any] | None = None,
) -> None:
    """Fail closed before adapter execution when mutation proofing is absent."""
    contracts.validate_plan(plan)
    if plan["effectClass"] != MUTATION_EFFECT:
        return
    missing = missing_guard_proof_providers(plan)
    if missing:
        raise RuntimeError("AGENT_TOOL_GUARD_PROOF_PROVIDER_MISSING:" + ",".join(missing))
    if proof_set is None:
        raise RuntimeError("AGENT_TOOL_GUARD_PROOFS_REQUIRED")
    guard_proofs.validate_proof_set(proof_set, plan=plan)
    # AT3A deliberately stops here.  A later contract must add a distinct
    # mutation-execute mode and a dispatch route to the existing canonical
    # write-capable host.  Hosted Agent Tool itself remains read-only.
    if plan["mode"] != "mutation-execute":
        raise RuntimeError("AGENT_TOOL_MUTATION_EXECUTION_NOT_ADMITTED")
