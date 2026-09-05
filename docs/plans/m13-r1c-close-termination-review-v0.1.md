# M13 R1C — Close Termination Review 0.1

Status: implementation slice.

Baseline: `main@bfc62afab916d66e435b3a48e0393b63b47e005a`.

## Intent

Make close obligations visible at the paved-path boundary without changing
`AgentCycleClosure 0.1`, inventing a cycle authority, or turning the R3B2 shadow
disposition projection into enforcement.

R1C composes already-existing proof surfaces:

```text
begin context + hosted begin manifest
  + canonical close + mutation readback evidence
  + touched-resource set
  + obligation inventory
  + obligation disposition observations
  -> AgentCycleCloseReview 0.1
```

The review answers a narrower question than close itself:

> What is known about the obligations left by this exact cycle, which of them are
> discharged, which are explicitly carried forward, which are known residue, and
> whether clean termination is actually proven?

It remains read-only and non-authoritative.

## Why this is additive instead of a Closure schema change

R3B1 deliberately marks touched-resource coverage as `UNKNOWN` until the
provider/Work Mode bridge can prove stronger coverage. R3B2 deliberately keeps
obligation dispositions out of canonical close policy. Promoting either shadow
surface directly into `AgentCycleClosure 0.1` now would make every normal close
fail for an epistemic limitation rather than a discovered unsafe state.

R1C therefore creates a review projection first. Known residue is still visible;
unknown coverage stays unknown; existing close semantics remain stable.

## Binding chain

A valid review must bind all of the following:

- `AgentCycleContext` to the exact Hosted begin manifest;
- manifest `cycleId`/`contextHash` to the canonical closure;
- manifest `cycleInstanceId` to the touched-resource set;
- resource set to the obligation inventory;
- inventory to the exact disposition set;
- current Context `workRef` to the inventory;
- closure to the exact evidence used to validate its receipt.

A rehashed artifact from another cycle must not be accepted merely because its
shape is valid.

## Obligation outcomes

The review uses four derived outcomes. These are projections over native domain
facts, not new domain states.

### `DISCHARGED`

- Work is `DONE`;
- touched Git branch is absent;
- write lifecycle is `NONE` or `RELEASED`.

### `CARRIED_FORWARD`

- Work remains `READY`, `IN_PROGRESS`, `WAITING`, or `HANDOFF`;
- a touched Git branch remains and is bound to active Work.

This is explicit continuity, not clean termination. `HANDOFF` remains visible as
its native Work fact.

### `OUTSTANDING`

- a Work obligation that existed at begin is missing at close;
- a touched Git branch still exists without an active Work binding;
- write lifecycle is `ACTIVE` or `EXPIRED`;
- canonical close reports uncovered durable mutation readback.

Known outstanding state takes precedence over generic coverage uncertainty.

### `UNKNOWN`

Any obligation whose native observation is `UNKNOWN` stays `UNKNOWN`.

## Overall review status

Precedence is deterministic:

1. `OUTSTANDING_OBLIGATIONS` when a known obligation/readback is outstanding;
2. `INSUFFICIENT_OBSERVATION` when no known outstanding obligation exists but
   coverage, closure, readback, or a disposition remains unknown;
3. `CARRIED_FORWARD` when observation is complete and at least one obligation is
   explicitly durable beyond this cycle;
4. `CLEAN_TERMINATION` only when observation is complete and every known
   obligation is discharged.

`cleanTerminationProven=true` is legal only for `CLEAN_TERMINATION`.

With current R3B1 coverage (`AGENT_CYCLE_PROVIDER_COVERAGE_INCOMPLETE`), a review
must therefore not claim clean termination merely because the bounded inventory
looks empty or discharged.

## Mutation readback

The review does not create a second mutation proof. It projects the existing
`AgentCycleAggregateReadback 0.1` fields:

- whether durable readback was required;
- evidence count;
- covered/uncovered durable changes;
- aggregate readback status/hash.

No readback means no promotion to clean termination when a durable delta exists.

## Public surface

R1C exposes the projection through:

```text
python3 tools/agent.py close-review ...
```

The command is observational. A successfully built review returns normally even
when its semantic status is `INSUFFICIENT_OBSERVATION` or
`OUTSTANDING_OBLIGATIONS`; callers must inspect the review status instead of
confusing process execution with termination proof.

Hosted materialization may add the review as a sibling proof artifact, but a
review projection failure must remain shadow and must not retroactively alter an
otherwise valid `AgentCycleClosure 0.1`.

## Explicit exclusions

R1C does not:

- modify Work, Continuation, Coordination, Git, PRs, leases, or ProjectState;
- infer Work ownership from branch names;
- delete residual branches;
- complete or hand off Work automatically;
- promote current provider coverage;
- change `AgentCycleClosure 0.1` status;
- make `AgentCycleObligationDispositionSet 0.1` enforcement-eligible;
- create `ReflectionEligible`, `OperationalQuiescence`, or experiment admission.

Those M13 decisions remain downstream consumers of facts, not part of this
termination review.

## Qualification gates

- exact cross-artifact binding rejects substituted context/manifest/cycle;
- every inventory obligation has exactly one reviewed outcome;
- Work `DONE` is discharged; active/wait/handoff Work is carried forward;
- handoff remains visible and counted;
- absent Git branch is discharged;
- existing branch with active Work is carried forward;
- existing branch without active Work is outstanding;
- released/no write lifecycle is discharged; active/expired lifecycle is outstanding;
- disposition `UNKNOWN` remains unknown;
- uncovered durable delta is never clean;
- incomplete provider coverage prevents false `CLEAN_TERMINATION`;
- known residue outranks generic coverage uncertainty;
- rehashed authority/enforcement tampering fails validation;
- canonical close behavior remains unchanged;
- full Agent Ops, semantic, Coordination and Supervisor gates remain green.

## Stop / re-plan conditions

Stop rather than widen if qualification requires a new mutable authority,
automatic cleanup, Work inference, changing native domain status vocabularies, or
making incomplete shadow coverage block the canonical close path.
