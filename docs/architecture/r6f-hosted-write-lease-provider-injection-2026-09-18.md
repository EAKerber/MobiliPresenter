# R6f — Hosted Agent Write Lease provider injection

Status: implementation candidate for the live R6 paved-path canary.

## Trigger

The R6 black-box canary successfully crossed the R6c intent-turnover boundary from `inspect-and-plan` to a fresh `governed-mutation` Agent Cycle. The next ownership acquisition then failed before mutation with `HOSTED_AGENT_WRITE_LEASE_PREPARE_FAILED`.

The core lifecycle contract was already correct: `tools.agent_write_lifecycle.prepare_dispatch(...)` requires an explicit provider and fails closed with `BLOCKED_EXECUTION_SURFACE` when none is supplied.

The remaining gap was the explicit Hosted Agent Write Lease CLI/environment host. `tools.hosted_agent_write_lease.main()` invoked `prepare(...)` without a transport, so the outer host failed to satisfy the provider-explicit boundary introduced by the R6 provider retirement.

## Reclet

This slice makes only the environment-edge correction:

- the Hosted Agent Write Lease CLI host constructs `GhApiTransport()`;
- that carrier is passed explicitly into `prepare(...)`;
- the lifecycle core remains provider-explicit and fail-closed;
- no provider manager, selector, fallback inference, authority, workflow, state machine, or lifecycle is added.

The focused regression invokes the CLI prepare path and proves that the exact carrier created at the environment edge is forwarded into the existing prepare surface.

## Qualification

R6f is eligible for integration only after exact-head operational CI materializes real jobs and passes. After integration, resume the existing `r6-black-box-paved-path-canary` from ownership acquisition; do not restart the turnover sequence or create a parallel lifecycle.

## Retirement / architectural reading

This is not a new abstraction layer. It closes a missed host binding exposed by the live canary. The durable invariant is that semantic/core lifecycle code never chooses a concrete provider while explicit environment hosts must supply one.
