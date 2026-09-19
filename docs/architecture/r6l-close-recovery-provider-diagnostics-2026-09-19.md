# R6l — Hosted close recovery provider and diagnostic seam

Status: implementation candidate discovered by the live R6 black-box close retry after R6k.

## Trigger

The post-R6k retry `r6-live-governed-close-post-r6k-20260919` still returned
`UNKNOWN / UNATTRIBUTED_DURABLE_DELTA`. Its close diagnostic contained the same
four source-head changes already modeled by R6i/R6j/R6k, but
`evidenceCount=0`.

Independent live readback showed that the bound R6 canary Work was unchanged,
the continuation drift did not touch that Work file, Coordination movement only
introduced an unrelated R6j lease, and the main first-parent chain consisted
only of unrelated merged PRs #320–#325. The remaining gap was therefore not a
new non-interference class.

## Discovery

The hosted compatibility-recovery wrapper called
`agent_cycle_close_recovery.recover_closure(...)` without injecting a provider.
The recovery core could silently construct its own `GhApiTransport`, while
`recovery_evidence(...)` converted proof-time `RuntimeError` failures into
`None`. At the hosted boundary this collapsed a concrete provider/proof error
into a generic absence of recovery evidence.

## Contract

R6l keeps the existing close and non-interference semantics unchanged:

- the explicit hosted recovery boundary constructs and injects its concrete
  carrier;
- the recovery core retains legacy fail-closed behavior by default;
- the hosted recovery boundary opts into strict propagation of proof errors;
- a strict proof error is materialized only as
  `AgentCycleCloseRecoveryDiagnostic 0.1`, with `readOnly=true`,
  `semanticAuthority=false`, and `authorizesMutation=false`;
- the externally visible close remains fail-closed under the existing
  `HostedAgentCycleFailure` contract if recovery does not prove PASS;
- no additional authority, lifecycle, lease, replay path, state machine, or
  non-interference allowance is introduced.

## Qualification

After exact-head tests pass, integrate R6l and retry the historical R6 canary
close through the existing handle. If R6k evidence now proves PASS, continue
the R6 promotion gate. If the close still fails, use the emitted diagnostic code
as the only basis for another recut rather than broadening non-interference
speculatively.

## Retirement

The diagnostic artifact is an R8 retirement candidate once close recovery is
stable and observable through the normal paved surface. Explicit provider
selection at the named hosted boundary is expected to remain part of the stable
provider contract.
