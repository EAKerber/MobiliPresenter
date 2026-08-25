from __future__ import annotations

from typing import Any

from tools.agent_tools import contracts

MUTATION_EFFECT = "shared-durable-mutation"

# AT2D deliberately has no mutation proof providers.  AT3 must add providers
# explicitly and wire their proofs before any shared durable mutation may enter
# adapter.execute().  Keeping this registry empty is an executable boundary,
# not a documentation convention.
GUARD_PROOF_PROVIDERS: dict[str, str] = {}


def missing_guard_proof_providers(plan: dict[str, Any]) -> list[str]:
    contracts.validate_plan(plan)
    if plan["effectClass"] != MUTATION_EFFECT:
        return []
    return sorted(guard for guard in plan["guards"] if guard not in GUARD_PROOF_PROVIDERS)


def assert_execution_admitted(plan: dict[str, Any]) -> None:
    """Fail closed before adapter execution when mutation proofing is absent."""
    contracts.validate_plan(plan)
    if plan["effectClass"] != MUTATION_EFFECT:
        return
    missing = missing_guard_proof_providers(plan)
    if missing:
        raise RuntimeError("AGENT_TOOL_GUARD_PROOF_PROVIDER_MISSING:" + ",".join(missing))
    # AgentToolPolicyCatalog 0.1 has no mutation execution mode.  Even after
    # proof providers exist, a later contract must explicitly admit one.
    if plan["mode"] != "mutation-execute":
        raise RuntimeError("AGENT_TOOL_MUTATION_EXECUTION_NOT_ADMITTED")
