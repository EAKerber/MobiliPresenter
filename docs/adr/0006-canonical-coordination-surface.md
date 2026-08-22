# ADR-0006 — Canonical Coordination operator surface

- Status: accepted
- Date: 2026-08-22
- Scope: GitOps / M11-CV1B
- Supersedes: only the operator-entrypoint decision of ADR-0005

## Context

ADR-0005 promoted Coordination Leases and named `python3 tools/lock.py ...` as the supported operator entrypoint. M11 convergence later proved that `lock` is a legacy CLI-name alias while the capability, authority, planner and canonical writer are all Coordination concepts.

CV1A established complete supported-consumer coverage and found no current workflow or role contract requiring `tools/lock.py`; the file itself, its registry binding and compatibility tests remain the blocking consumers.

The previous CLI also planned and applied inside one invocation. Work lifecycle has since established the stronger operational shape `plan -> validate -> expected-plan -> apply -> readback -> receipt`. Coordination now reuses `TransitionPlan 0.1` and `TransitionReceipt 0.1` while preserving the same Coordination authority writer.

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

The canonical CLI requires an explicit transition id for mutation planning. Random transition-id generation remains only in the temporary legacy compatibility path.

## Compatibility

`tools/lock.py` remains temporarily as a thin wrapper that delegates to `tools.coordination_cli`. The semantic alias `coordination.lease:lock` remains legacy and blocking until CV1C re-runs ConvergenceInspection and proves retirement readiness.

No Coordination authority, planner semantics, CAS behavior, trusted-time source or writer ownership changes because of this entrypoint migration.

## Boundaries

This ADR does not:

- retire the `lock` alias;
- retire the `ops` branch namespace alias;
- change `Coordination Guard` policy;
- change break-glass authorization or `tools/coordination_admin.py`;
- add Coordination to `tools/agent.py`;
- admit M12 remote execution.

Those remain separate governed transitions.
