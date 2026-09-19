# R6e — Hosted begin provider injection

Status: **implementation slice**.

## Observed failure

After R6c and R6d integration, a live Work-bound Hosted Agent Cycle begin for
`r6-black-box-paved-path-canary` reached the canonical V0.4 entry path but
failed with `HOSTED_AGENT_WORK_AUTHORITY_UNKNOWN`.

The failure was not an intent-selection problem. `hosted_agent_cycle._observe_work_ref`
still constructed `GitHubContinuationAuthority` without an injected provider,
while the provider-boundary retirement now requires that authority adapter to
receive an explicit transport.

## Fix

- `_observe_work_ref(..., transport=...)` requires provider injection when a
  Work reference is present and fails closed with `BLOCKED_EXECUTION_SURFACE`
  when absent.
- `begin_from_envelope(..., transport=...)` forwards the host provider into
  Work observation.
- the explicit Hosted Agent Cycle CLI/workflow host constructs
  `GhApiTransport` at the outer host boundary and passes it inward.
- legacy begin commands without a Work reference retain their existing behavior.

This adds no provider manager, provider authority, Journey state, workflow or
fallback inference. It repairs an incomplete host-boundary injection exposed by
the live R6 canary.

## Qualification

Exact-head CI must pass before integration. After integration, rerun the same
Work-bound V0.4 begin through `github-connector-tools`. The expected result is
that Work observation succeeds and the canary advances to the next real paved
boundary rather than failing at provider construction.
