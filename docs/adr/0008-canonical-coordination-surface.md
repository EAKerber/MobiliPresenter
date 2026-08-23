# ADR-0008 — Canonical Coordination operator surface

- Status: accepted
- Date: 2026-08-22
- Scope: GitOps / M11-CV1B
- Supersedes: only the operator-entrypoint decision of ADR-0005
- Renumbered: 2026-08-22 from a duplicate ADR-0006 identifier; decision content remains the same

## Context

ADR-0005 promoted Coordination Leases and named `python3 tools/lock.py ...` as the supported operator entrypoint. M11 convergence later proved that `lock` was a legacy CLI-name alias while the capability, authority, planner and canonical writer are all Coordination concepts.

CV1A established complete supported-consumer coverage. CV1B then introduced the canonical Coordination operator surface and stronger `plan -> validate -> expected-plan -> apply -> readback -> receipt` shape while preserving the same Coordination authority writer.

## Decision

The canonical operator surface is:

```text
python3 tools/coordination_cli.py ...
```

Mutation commands (`intent`, `acquire`, `renew`, `release`) produce a deterministic `TransitionPlan 0.1` and do not mutate by default. Canonical apply is explicit:

```text
python3 tools/coordination_cli.py apply <plan.json> \
  --expected-plan <planHash> --json
```

Apply reobserves Coordination, verifies the exact authority head and before-state, rebuilds the domain plan, validates trusted remote time and temporal safety, delegates to the existing `GitHubCoordinationAuthority` writer, and emits a verified `TransitionReceipt 0.1` envelope accepted by Agent Cycle Close.

The canonical CLI requires an explicit transition id for mutation planning.

## Compatibility and post-decision status

At the time of the CV1B decision, `tools/lock.py` remained temporarily as a thin compatibility wrapper and `coordination.lease:lock` remained a legacy alias pending CV1C proof.

M11-CV1C subsequently proved complete retirement readiness and removed both the wrapper and semantic alias. That later retirement does not change this ADR's operator decision: `tools/coordination_cli.py` remains the canonical adapter and `coordination-executor` remains the sole writer for `coordination-leases`.

## Boundaries

This ADR does not:

- change Coordination Guard policy;
- change break-glass authorization or `tools/coordination_admin.py`;
- add Coordination mutation to `tools/agent.py`;
- grant provider/carrier semantic authority;
- admit M12 remote execution by itself.

Those remain separate governed transitions.
