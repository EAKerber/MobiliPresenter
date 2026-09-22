# E4 — Governed Mutation Counter and kitchen windows

Status: **candidate in-house ergonomic surface**.

## Goal

A caller performing a normal governed multi-file mutation should provide only:

- Work ID;
- branch;
- changes;
- commit message.

The service composes existing authorities and execution semantics. It does not create a new authority.

## Counter vs kitchen

The normal result is intentionally small:

`status + summary + nextSafeAction + windows`.

Detailed Work, cycle, plan, proof, execution and Git evidence is preserved in one workflow artifact and exposed through hash-bound window locators.

This is progressive disclosure, not hidden state.

## Existing semantics reused

The counter reuses:

- canonical Work authority and `observe_turnover_context()`;
- exact `AgentCycleHandle`;
- exact begin context/manifest artifact;
- handle-first Agent Tool request derivation;
- existing Agent Tool policy/resolver;
- existing hosted write-lifecycle proof discovery;
- E3 shared governed mutation host;
- existing Agent-owned Git writer and per-write lease enforcement;
- canonical RemoteCanonicalExecutionReceipt.

Authorities added: **0**.

## Reuse-only authority policy

E4 does not silently:

- begin a new Agent Cycle;
- acquire or renew a write lease;
- change Work;
- retry or rebase a mutation.

If canonical re-entry says `BEGIN_NEW_CYCLE`, the counter returns BLOCKED with that next action.

If lifecycle proof is missing/expired, mutation admission returns BLOCKED and the counter projects the appropriate authority action.

## Exact semantic host

Preparation verifies that the exact cycle `sourceSha` contains the E4 service implementation.

A cycle that predates E4 is not executed using newer semantics. It returns:

`GOVERNED_MUTATION_CYCLE_HOST_PREDATES_SERVICE / BEGIN_NEW_CYCLE`.

The workflow downloads the exact begin artifact and executes the mutation service from the exact cycle semantic host checkout.

## Kitchen windows

Every result contains six fixed windows:

- `work`;
- `cycle`;
- `decision`;
- `authority`;
- `execution`;
- `git`.

Unavailable windows are null.

Available windows point to an artifact member plus its stable hash. `inspect` validates the member hash before returning the evidence.

There is no evidence database, hash index or new persistent store.

## Temporal evidence

Windows show evidence that participated in the execution. They are not fresh observations disguised as historical evidence.

A separate future action may compare historical windows with current authority state, but E4 does not conflate the two.

## Result behavior

PASS:
- compact branch/head/path summary;
- nextSafeAction `CONTINUE`;
- all relevant evidence available through windows.

BLOCKED:
- no implicit authority transition;
- blocker plus safe next action.

UNKNOWN:
- no blind retry;
- nextSafeAction `INSPECT_EXECUTION`;
- execution window is the primary diagnostic surface.

## Transport

The in-house carrier is the existing Remote Canonical Execution Bus through:

`MOBILIPRESENTER_GOVERNED_MUTATION_REQUEST_V0_1`.

The workflow is transport/orchestration only. It does not implement Work, lifecycle, mutation planning or Git writing.

## Semantic registry

E4 is a new binding of the existing `agent.tools.hosted` logical capability on the existing `github-actions-workflows` and `python-module-cli` surfaces.

It is not a new logical capability.

## Promotion

Initial promotion requires exact-head Agent Ops, Coordination Guard and Supervisor Snapshot.

Positive live promotion should occur on the next suitable Work/cycle created from a semantic host containing E4. E4 does not manufacture a new Work or Agent Cycle merely to satisfy a canary.

A negative live request against a terminal/no-reentry Work may be used to prove fail-closed transport without changing authority.

## E4a — terminal Work fast path

The counter observes canonical Work before reading hosted cycle history.

If Work is terminal, mutation is BLOCKED immediately with
`GOVERNED_MUTATION_WORK_TERMINAL / NONE`. Agent Cycle history is not
reconstructed because it cannot change the decision.

For non-terminal Work, re-entry is then observed. If Work changes between the
counter observation and re-entry observation, the preparation is UNKNOWN with
`GOVERNED_MUTATION_WORK_DRIFT`.

This keeps the service counter independent from unnecessary kitchen history
while preserving fail-closed behavior under concurrent Work changes.
