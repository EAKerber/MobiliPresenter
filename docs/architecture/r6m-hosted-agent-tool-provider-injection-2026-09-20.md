# R6m — Hosted Agent Tool provider injection

Status: implementation candidate produced from the fresh R6 live black-box canary on 2026-09-20.

## Trigger

The fresh Work-bound R6 canary started from current `main=a2fc5af9407f0dab9924323c6184aab994ed431a`.

The following paved steps succeeded:

- Hosted Agent Cycle V0.4 begin returned `READY`;
- Hosted Agent Write Lease V0.2 acquire returned `PASS` with canonical Coordination readback;
- the target branch was bound to the fresh cycle.

The first `git.files.mutate` Hosted Agent Tool request then returned:

```text
BLOCKED_EXECUTION_SURFACE
```

No Git mutation was performed. Ownership was subsequently released through the canonical write-lease lifecycle, and the interrupted fresh cycle was closed `PASS` using the corresponding Remote Canonical receipts.

## Root cause

Provider-boundary retirement correctly removed hidden provider construction from semantic/core paths.

The named Hosted Agent Tool CLI host remained an incomplete environment edge: its `execute` path called `prepare_request(...)` without a provider. That function now correctly expects provider injection when Git observation and admission proof collection require live GitHub access.

The downstream mutation dispatch host already follows the intended pattern: it constructs `GhApiTransport` explicitly at its named hosted boundary and passes that carrier into core execution.

## Contract

R6m aligns only the first Hosted Agent Tool host stage with the existing provider policy:

- `tools/hosted_agent_tool.py main(execute)` constructs the concrete GitHub carrier;
- the carrier is injected into `prepare_request(..., transport=carrier)`;
- `prepare_request`, resolver, admission, semantic/core functions and direct library callers retain provider-explicit/fail-closed behavior;
- the separate mutation dispatch host remains unchanged;
- no provider selection is added to Journey/paved semantics;
- no executor framework, queue, retry loop, authority, lifecycle, store, protocol version or CLI/raw-HTTP fallback is introduced.

This is a named host-adapter correction, not a relaxation of provider-boundary retirement.

## Recovery authoring note

The canonical Hosted Agent Tool authoring carrier was the surface under repair, so it could not be used to patch itself without reproducing the blocker.

The R6m source/test/documentation commits were therefore authored through the configured GitHub connector only after:

1. creating the R6m Work through the canonical Continuation writer;
2. starting a fresh Work-bound Agent Cycle;
3. acquiring the exact branch write lease through Hosted Agent Write Lease V0.2.

This direct provider write is recovery-scoped to repairing the broken authoring carrier. Normal authoring must return to Hosted Agent Tool after integration.

## Regression target

The R6m regression asserts both sides of the boundary:

- CLI `execute` constructs exactly one `GhApiTransport` and passes it to `prepare_request`;
- `prepare_request` itself does not construct `GhApiTransport`, preserving explicit provider injection below the host edge.

## Qualification

Before integration:

1. run focused Hosted Agent Tool tests;
2. run normal exact-head Agent Ops, Coordination Guard and Supervisor Snapshot qualification;
3. require real jobs and PASS, not zero-job/action-required ambiguity;
4. integrate through governed Delivery;
5. release ownership and close the R6m Agent Cycle;
6. retry the fresh R6 black-box canary from the new `main`.

R6 remains unpromoted until that fresh canary completes the required positive and negative live traversal.

## Retirement

This recut adds no new public surface. The explicit provider construction at the named hosted boundary is expected to remain while that adapter exists.

If a later platform-native semantic executor removes the need for the Hosted Agent Tool carrier, the adapter itself remains eligible for R8 demotion/deletion under the existing migration hardening contract.
