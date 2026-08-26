from __future__ import annotations

import copy
from typing import Any, Callable

from tools import agent_write_lifecycle_guard
from tools.agent_tools import contracts
from tools.agent_tools import guard_proofs
from tools.canonical import stable_hash

MUTATION_EFFECT = "shared-durable-mutation"

# Proof providers materialize admission evidence only. Their availability does
# not authorize a write: mutation-execute still requires an intent-scoped plan,
# a positive proof set, dispatch to the canonical host, and execution-time
# guard revalidation before the existing writer is invoked.
GUARD_PROOF_PROVIDERS: dict[str, Callable[..., dict[str, Any]]] = {
    "agent-write-lifecycle-bound": agent_write_lifecycle_guard.prove_active_binding,
    "coordination-lease-owned": guard_proofs.prove_coordination_lease_owned,
    "git-cas": guard_proofs.prove_git_cas,
}


def missing_guard_proof_providers(plan: dict[str, Any]) -> list[str]:
    contracts.validate_plan(plan)
    if plan["effectClass"] != MUTATION_EFFECT:
        return []
    return sorted(guard for guard in plan["guards"] if guard not in GUARD_PROOF_PROVIDERS)


def _lifecycle_context(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"cycleInstanceId", "issueNumber", "beforeCommentId"}:
        raise RuntimeError("AGENT_WRITE_LIFECYCLE_CONTEXT_REQUIRED")
    cycle_id=value.get("cycleInstanceId")
    issue=value.get("issueNumber")
    before=value.get("beforeCommentId")
    if not isinstance(cycle_id,str) or not cycle_id:
        raise RuntimeError("AGENT_WRITE_LIFECYCLE_CONTEXT_INVALID")
    if not isinstance(issue,int) or isinstance(issue,bool) or issue <= 0:
        raise RuntimeError("AGENT_WRITE_LIFECYCLE_CONTEXT_INVALID")
    if before is not None and (not isinstance(before,int) or isinstance(before,bool) or before <= 0):
        raise RuntimeError("AGENT_WRITE_LIFECYCLE_CONTEXT_INVALID")
    return {"cycleInstanceId":cycle_id,"issueNumber":issue,"beforeCommentId":before}


def collect_guard_proofs(
    plan: dict[str, Any],
    *,
    transport: Any | None = None,
    authority_factory: Callable[[Any], Any] | None = None,
    lifecycle_context: dict[str, Any] | None = None,
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
        if guard == "agent-write-lifecycle-bound":
            context=_lifecycle_context(lifecycle_context)
            proof=provider(
                plan,
                cycle_instance_id=context["cycleInstanceId"],
                issue_number=context["issueNumber"],
                before_comment_id=context["beforeCommentId"],
                transport=transport,
            )
        elif guard == "coordination-lease-owned":
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
    # Admission proves only that this plan is eligible to be dispatched. The
    # canonical host must re-observe the guards immediately before mutation.
    if plan["mode"] != "mutation-execute":
        raise RuntimeError("AGENT_TOOL_MUTATION_EXECUTION_NOT_ADMITTED")
