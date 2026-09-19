# R6h — historical blocked close compatibility recovery

Status: implementation candidate for the live R6 paved-path canary.

## Trigger

The R6 canary produced a governed-mutation Agent Cycle on source SHA `9e1ad21...`. Its write-lease acquisition failed before mutation with a strongly-bound `BLOCKED` terminal. R6g corrected current close-time reconciliation so such a terminal is no longer mistaken for a missing result.

The historical cycle, however, still runs its first close attempt on its original carrier source. That older carrier emits the exact non-lossy pair:

- `AGENT_WRITE_LIFECYCLE_REQUEST_WITHOUT_TERMINAL` from `agent-write-lifecycle-guard`;
- `AGENT_WRITE_LIFECYCLE_UNKNOWN_AT_CLOSE` from `hosted-agent-cycle`.

The existing observational compatibility recovery already restores the current carrier and re-observes the close without replaying the lease operation, but its eligibility allowlist did not admit this exact pre-R6g signature. The result was a safe but permanent `WAITING / AGENT_WRITE_LEASE_RESULT`.

## Reclet

R6h adds only that exact two-cause, non-lossy signature to the existing close compatibility allowlist.

It does not change the canonical close primitive, write-lease lifecycle, waiting vocabulary, Agent Cycle identity, or Coordination authority. It does not replay the historical write-lease request. Recovery remains observational: the historical carrier fails, current carrier is restored, current close semantics re-observe the already-present request/failure evidence, and normal close proceeds only if current authorities support it.

## Fail-closed constraints

Eligibility still requires the existing failure envelope invariants: CLOSE phase, non-authoritative/read-only failure, `operationReplay=NOT_APPLICABLE`, mutation state non-applicable, and exact non-lossy causes. `AGENT_WRITE_LIFECYCLE_UNKNOWN_FAILURE_AT_CLOSE` is deliberately not admitted. Any new or lossy UNKNOWN signature remains outside compatibility recovery.

## Qualification

Regression coverage asserts that the exact pre-R6g pair is present in the bounded workflow eligibility block, that recovery remains routed through `tools.agent_cycle_close_recovery.hosted`, and that UNKNOWN write-lease failure is not added to the allowlist.

After exact-head CI passes and R6h is integrated, retry the existing R6 canary close. A successful observational recovery should close the historical governed cycle without replay, after which the live canary can begin a fresh current-main governed cycle and resume at ownership acquisition.
