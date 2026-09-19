# R6g — blocked write-lease terminal reconciliation

Status: implementation candidate for the live R6 paved-path canary.

## Trigger

The R6 live black-box canary crossed intent turnover into a Work-bound `governed-mutation` Agent Cycle and attempted to acquire ownership of `work/operations/r6-black-box-live-canary`. The Hosted Agent Write Lease request failed before mutation with a strongly-bound `AgentWriteLeaseFailure` whose status was `BLOCKED` and blocker was `HOSTED_AGENT_WRITE_LEASE_PREPARE_FAILED`.

The cycle close guard already received both the strongly-bound lease request and its strongly-bound failure terminal from `hosted_cycle_records`. However, `agent_write_lifecycle_guard.inspect_cycle()` counted only successful lease results as terminals. Consequently a valid fail-closed, non-mutating `BLOCKED` result was misclassified as `AGENT_WRITE_LIFECYCLE_REQUEST_WITHOUT_TERMINAL`, preventing the cycle from closing and being safely refreshed.

## Reclet

R6g changes only close-time reconciliation:

- each strongly-bound write-lease request is matched by its request hash to the latest strongly-bound success or failure terminal;
- a matched `BLOCKED` failure is terminal evidence of a non-mutation and does not by itself make the lifecycle dirty;
- a matched `UNKNOWN` failure remains `UNKNOWN` and blocks clean close;
- a request with no success/failure terminal remains `AGENT_WRITE_LIFECYCLE_REQUEST_WITHOUT_TERMINAL`;
- successful lifecycle bindings retain the existing ACTIVE / RELEASED / EXPIRED reconciliation;
- lease-authority readback still protects against an unexpected active lease, including when the only terminal is `BLOCKED`.

No authority, state machine, provider selector, workflow, marker, schema, or lifecycle is added.

## Qualification

Focused regressions cover:

1. strongly-bound `BLOCKED` failure -> clean `NONE` when Coordination has no active matching lease;
2. strongly-bound `UNKNOWN` failure -> `UNKNOWN`;
3. request with no terminal -> `UNKNOWN`.

R6g is eligible for integration only after exact-head operational CI materializes real jobs and passes.

## Return to R6

After integration, re-run close on the existing failed governed-mutation cycle. If close succeeds, begin a fresh Work-bound governed-mutation cycle from current `main`, reacquire ownership, and resume the positive live traversal at `git.files.mutate`. Do not restart already-proven negative-canary or intent-turnover steps.
