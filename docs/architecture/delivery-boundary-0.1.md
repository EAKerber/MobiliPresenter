# Delivery Boundary 0.1 — Authoring vs Integration

Status: **architectural consolidation; no new authority or writer**.

## Decision

Agent Cycle is the lifecycle of an agent's authored work. Repository integration is a distinct delivery lifecycle.

A cycle may discover, plan, acquire a write lease, create or update its work branch and validate a candidate. To terminate cleanly while that candidate remains live for later integration, continuity into Delivery must be explicit rather than inferred. A later integration operation may accept the handed-off candidate into `main` only after its own current PR, CI and Git preconditions are observed.

The intended composition is:

```text
Agent Cycle / authoring
begin -> plan -> lease -> branch mutation -> candidate validation
                                               |
                                      explicit delivery handoff
                                               |
                                      release -> close
                                               |
                                               v
Delivery / integration
consume handoff -> observe PR + main + gates -> merge-pr -> merge receipt -> main readback
```

The authoring cycle closes **before an integration operation mutates `main`**, but it may do so cleanly only after the still-live candidate has an explicit recognized continuity disposition. A merge receipt therefore belongs to delivery; it is not retroactively attached to the closed authoring cycle.

## Existing primitives

No parallel merge model is introduced.

`GitMutationPlan 0.1` already defines `create-pr` and `merge-pr`. In particular, `merge-pr` is an `integration-write` operation that binds:

- the exact PR number;
- expected head SHA;
- expected base;
- required green gates;
- merge method;
- merged-PR readback.

Those primitives remain available to a future delivery composition. Agent Cycle does not promote PR or merge plans into its semantic touched-resource set without a dedicated strong runtime producer and an explicit contract change.

## Invariants

1. **Session identity is not repository acceptance.** A successful Agent Cycle proves the bounded authoring lifecycle, not that the candidate should enter `main`.
2. **Close does not authorize merge.** Agent Cycle outputs remain read-only projections and cannot become integration authority.
3. **Live candidate continuity is explicit.** A branch that still exists at close cannot be silently forgotten. Current close review correctly treats an unbound live branch as `GIT_BRANCH_UNBOUND_AT_CLOSE`; a future Delivery composition must provide a recognized handoff/disposition instead of weakening that guard.
4. **Integration reobserves current facts.** Delivery must bind the PR head, base, required gates and relevant `main` state at integration time; it cannot rely on an earlier cycle snapshot as merge authorization.
5. **`merge-pr` stays canonical.** A future delivery layer composes the existing `GitMutationPlan.merge-pr`; it must not define a competing merge planner or hidden direct-main path.
6. **Transport is not authority.** A delivery carrier may transport commands or receipts, but Git/PR/CI facts and the canonical mutation contracts remain authoritative for the operation.
7. **No lifecycle stretching by implication.** Adding a merge-capable transport does not silently make merge part of Agent Cycle. Moving this boundary requires an explicit architectural and contract revision.

## Current scope

This decision does **not** implement Delivery, add a `DeliverySession`, persist new lifecycle state, expose a new merge executor, or make close-before-merge clean for an otherwise unbound branch. The existing close guard remains authoritative.

The immediate regression proof is `tools/tests/test_agent_cycle_delivery_boundary.py`: the canonical planner can describe PR/merge operations, while Agent Cycle deliberately rejects them as authoring resources. Existing close-review coverage continues to prove that a live unbound branch is an outstanding obligation.

## Future delivery composition

A minimal future slice should remain derivable from existing authorities and add only the smallest continuity contract necessary:

```text
explicit candidate handoff
+ current PR observation
+ current required-CI observation
+ current main/base observation
-> GitMutationPlan.merge-pr
-> governed merge execution
-> exact PR merged readback
-> main readback
-> hash-bound delivery result
```

The first design question for that slice is therefore not a new merge planner; it is the **explicit handoff/disposition that lets Agent Cycle discharge responsibility for a still-live candidate without claiming integration success**.

Only if this composition later needs durable cross-session coordination should a separate delivery authority be considered. The default is to avoid creating one.
