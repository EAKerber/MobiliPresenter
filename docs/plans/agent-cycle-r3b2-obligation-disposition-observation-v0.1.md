# Agent Cycle R3B2 — Obligation Disposition Observation 0.1

Status: implementation slice.

Baseline: `main@514def4bbbbfd1bc9c8ef0fec582eaadad873a42`.

## Intent

Observe the current domain-native state associated with every obligation emitted by
`AgentCycleObligationInventory 0.1`, without turning those observations into a
cross-domain close policy.

R3B2 remains shadow. It does not mutate Work, Coordination or Git, does not add a
cycle authority, and does not make disposition observations inputs to
`AgentCycleClosure 0.1`.

## Precondition fix — Work binding continuity

`AgentCycleContext 0.4` introduced explicit `workRef`, but the current canonical
close rebuilds `afterContext` without forwarding the begin-time Work reference.
R3B2 first fixes that loss:

- current Context 0.4 close preserves exact `workRef`;
- `build_delta()` rejects current-context Work drop/rebind;
- historical Context versions remain unchanged.

## AgentCycleObligationDispositionSet 0.1

The artifact is bound to:

- `repository`;
- `cycleInstanceId`;
- `resourceSetHash`;
- `inventoryHash`;
- inherited provider `coverage`.

It contains exactly one disposition observation for every obligation in the input
inventory. Missing observations are represented as `UNKNOWN`, never by omission.

Top-level `observationStatus` is epistemic (`PASS | UNKNOWN`). It does not say that
the cycle may close.

`enforcementEligible=false`, `readOnly=true`, `semanticAuthority=false`, and
`authorizesMutation=false` remain invariant.

## Domain-native observations

### Work

One `GitHubContinuationAuthority.observe()` snapshot is reused for all Work and
branch obligations. A Work disposition preserves the native Work status
(`READY | IN_PROGRESS | WAITING | HANDOFF | DONE`) when present. A successful
authority observation where the item is absent is a factual `exists=false` result;
an unavailable/invalid Work authority produces `UNKNOWN`.

### Git branch

A branch disposition records only factual ref state (`exists`, `headSha`) plus
active Work bindings derived from the same Work snapshot. `404` means absent;
provider/transport ambiguity means `UNKNOWN`. R3B2 does not classify branches as
integrated, abandoned, safe-to-delete, or terminal.

### Agent Write Lease lifecycle

R3B2 reuses the exact validated `AgentWriteLeaseCloseReport 0.1` produced by the
existing lifecycle guard. The disposition carries its `state` and `reportHash`;
it does not redefine the lease state machine.

Hosted close observation and current clean-lifecycle enforcement are split so the
same report can feed the shadow disposition artifact and then the existing policy.
No second Coordination read is allowed.

## Hosted integration

The canonical close-proof directory derives sibling shadow paths from the closure
path. R3B2 removes the resource/obligation path environment variables rather than
adding another one.

Target sequence:

```text
trace stabilization
-> materialize R3B1 resources + inventory
-> observe lifecycle once
-> observe Work once
-> observe exact touched Git refs
-> materialize disposition set shadow
-> apply existing clean-lifecycle policy
-> run unchanged canonical close
```

Any R3B2 projection/observation failure is represented in the shadow artifact and
must not change close status or error code.

## Explicit exclusions

R3B2 does not:

- add `PENDING` or `WAITING` to Agent Cycle results;
- define `resolved=true/false` across domains;
- infer Work from branch/PR/worker;
- recreate PR resources;
- update Work automatically;
- introduce a new authority or writer;
- promote incomplete provider coverage;
- feed dispositions into `AgentCycleClosure 0.1`.

## Qualification gates

- Context 0.4 Work reference survives canonical close exactly;
- current-context Work drop/rebind fails closed;
- exactly one disposition per obligation hash;
- deterministic disposition ordering/hash;
- exact binding to cycle/resource/inventory hashes;
- coverage cannot be promoted;
- rehash cannot enable enforcement or authority;
- one Work authority observation serves all Work/branch obligations;
- successful Work lookup with absent item is factual, not UNKNOWN;
- unavailable Work authority is UNKNOWN;
- Git ref 404 is factual absence; ambiguous/provider failure is UNKNOWN;
- branch Work bindings come only from `work_graph.active_execution_bindings()`;
- lifecycle disposition binds exact validated close report;
- no second Coordination observation;
- shadow write/observation failure cannot change canonical close outcome;
- existing ACTIVE/RELEASED/NONE lifecycle close behavior is unchanged;
- full operational CI remains green.

## Stop / re-plan conditions

Stop instead of widening if implementation requires a new mutable state, automatic
domain mutation, Work inference, PR resource resurrection, multiple independent
Work snapshots, a second Coordination read, or changing close policy merely to
accommodate the disposition artifact.
