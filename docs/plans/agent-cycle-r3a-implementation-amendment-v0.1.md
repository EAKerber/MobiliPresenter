# R3A — implementation amendment v0.1

Status: **implementation refinement; no ProjectState transition**

Implementation PR: #177
Planning baseline: `docs/plans/agent-cycle-r3a-touched-resource-projection-v0.1.md`

## Why this amendment exists

The R3A plan proposed adding a JSON Schema and OperationalSemantics registration
for `AgentCycleTouchedResourceSet 0.1` in the same slice that first materializes
the projection.

The first implementation CI proved the repository guard correctly: an
operational schema cannot exist without registry coverage. That forced the more
important design question: whether R3A already has a public semantic consumer
that justifies two executable acceptance surfaces.

It does not.

R3A is deliberately shadow-only:

- the resource set is reconstructed from existing cycle-bound records;
- the Hosted close may persist it as diagnostic proof;
- no mutation is authorized by it;
- no close status is decided by it;
- no Work, Coordination, Git or ProjectState writer consumes it;
- loss of the artifact loses no authority and no mutable state.

Adding structural schema + registry now would therefore create a second
acceptance surface before interoperability needs it, repeating the class of
Python-vs-schema divergence already identified during the R1C audit.

## Implemented refinement

R3A keeps exactly one executable semantic definition:

`tools.agent_cycle_resources.validate_resource_set`

The JSON Schema added during the first implementation pass was removed before
qualification. No registry exception or coverage bypass was added.

This is a reduction, not a weakening of validation: the Python validator remains
closed, hash-bound, deterministic and explicitly non-authoritative.

## R3B admission gate

Schema + OperationalSemantics registration becomes mandatory before the first
semantic runtime consumer is allowed to rely on the resource set.

Concretely, R3B may not make an obligation, disposition or close judgment depend
on `AgentCycleTouchedResourceSet` until all of the following are true:

1. a structural schema is introduced and registered normally;
2. structural acceptance is tested against the Python contract for all closed
   locator kinds and boundary flags;
3. semantic-only rules such as hashes, canonical ordering and deterministic
   reconstruction remain explicitly owned by the Python definition rather than
   being partially duplicated;
4. the resource projection is proven reconstructible from source records;
5. no new mutable resource authority, writer or CAS surface is introduced.

## What did not change

This amendment does not change the R3 decomposition:

```text
R3A  touched-resource projection, shadow
  -> R3B  obligations + disposition
  -> R3C  CycleProgress + dynamic close
```

It also does not move R4 concerns into R3: seal, late results, ordering and
concurrency remain deferred to R4.
