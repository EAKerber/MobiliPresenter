# Delivery Boundary 0.1 — Authoring vs Integration

Status: **architectural consolidation; thin hosted integration path, no new durable authority**.

## Decision

Agent Cycle is the lifecycle of an agent's authored work. Repository integration is a distinct delivery operation.

A cycle may discover, plan, acquire a write lease, create or update its work branch and validate a candidate. To terminate cleanly while that candidate remains live for later integration, continuity must be explicit rather than inferred. The existing Work / Continuation authority is sufficient for that continuity: an active WorkItem bound to the exact branch and PR carries the candidate after authoring ends.

The proven composition is:

```text
Agent Cycle / authoring
begin -> plan -> lease -> branch mutation -> candidate validation
                                               |
                           active WorkItem(branch + PR + remaining integration)
                                               |
                                      release -> close PASS
                                               |
                                               v
Delivery / integration
reobserve Work + PR + CI + main -> merge-pr -> merge receipt -> main readback
                                               |
                                               v
                              separate Work advance/done
```

The authoring cycle closes **before integration mutates `main`**. A merge receipt belongs to Delivery; it is not retroactively attached to the closed Agent Cycle.

## Existing primitives

No parallel merge model or Delivery state machine is introduced.

`GitMutationPlan 0.1` already defines `create-pr` and `merge-pr`. `merge-pr` is an `integration-write` operation that binds:

- the exact PR number;
- expected head SHA;
- expected base;
- required green gates;
- merge method;
- merged-PR readback.

Work / Continuation already supplies durable cross-cycle responsibility for the candidate. Agent Cycle does not promote PR or merge plans into its semantic touched-resource set.

## Proven handoff

PR #285 provided the first live proof of the boundary:

1. Agent Cycle authored and validated the candidate branch.
2. WorkItem `delivery-pr-285` was created in the canonical Continuation authority, bound to the candidate branch and PR #285 with `integrate-pr-285` remaining.
3. The Agent Write Lease was released.
4. Agent Cycle closed `PASS` **while the branch still existed**, because close review observed an active Work binding rather than an orphan branch.
5. PR #285 was merged only after the cycle was closed and PR/main/gates were reobserved.
6. The WorkItem was advanced with the observed merge SHA and then transitioned to `DONE` through the canonical Continuation writer.

This proves that a separate `DeliverySession` or durable Delivery authority is not required for the current problem.

## Hosted merge slice

`tools/delivery_merge.py` and `tools/hosted_delivery_merge.py` provide a thin execution host for the existing `merge-pr` primitive. The host introduces no durable state of its own.

A request is closed over:

- exact WorkItem id and expected Continuation authority head;
- exact PR number and head SHA;
- exact expected base (`main`);
- exact current `main` SHA;
- explicit merge method;
- manager/GitOps actor identity.

Before mutation, the host reobserves all of those facts. The WorkItem must be active and bind the same PR/branch; the PR must be open, non-draft and same-repository; `integration_reconcile` must find no semantic-boundary violation and must classify the exact-head CI `green`; and `main` must still equal the expected target SHA. The CI aggregation therefore retains the repository's existing branch-domain rule, including `Agent Ops` for operations branches instead of silently inventing a second gate policy. It then derives `GitMutationPlan.merge_pr` and performs one provider merge with the exact PR head SHA.

Version 0.1 intentionally supports only the canonical default `squash` method. After the provider merge, Delivery independently reads back the merged PR, `main`, and the resulting commit. The squash commit's sole parent must equal the target SHA reobserved immediately before mutation. This postcondition detects a target race instead of silently accepting integration against a different base. If `main` advances again after this merge but before readback, the result may still pass only when Git ancestry proves the observed `main` contains the exact merged SHA.

`pending`, `failed`, `reentry_required`, `unknown`, semantic-boundary violations, head/base drift, Work authority drift, target drift and target-parent drift all fail closed.

The host **does not advance or complete Work**. Work completion remains a separate canonical Continuation transition after the merge receipt is observed.

## Invariants

1. **Session identity is not repository acceptance.** A successful Agent Cycle proves bounded authoring, not acceptance into `main`.
2. **Close does not authorize merge.** Agent Cycle outputs remain read-only projections.
3. **Live candidate continuity is explicit.** A live unbound branch remains `GIT_BRANCH_UNBOUND_AT_CLOSE`; an active Work binding is the recognized carry-forward mechanism.
4. **Integration reobserves current facts.** Delivery binds current Work authority, PR head/base, CI and `main` at execution time.
5. **`merge-pr` stays canonical.** The hosted path composes `GitMutationPlan.merge_pr` and `integration_reconcile`; it does not define competing merge or gate planners.
6. **Transport is not authority.** Issue comments and GitHub Actions carry requests/results; Work, Git, PR and CI observations remain the relevant facts.
7. **Work lifecycle stays separate.** Delivery merge never silently advances or completes a WorkItem.
8. **No hidden main path.** The only integration mutation in this slice is the exact PR merge described by the validated plan and followed by PR/main readback.

## Scope

This slice does not add `DeliverySession`, a Delivery branch, a new semantic authority, a second scheduler, or a hidden direct-main file writer. If future delivery needs durable state beyond the existing Work authority, that need must be demonstrated before adding another lifecycle.

The regression proofs are `tools/tests/test_agent_cycle_delivery_boundary.py` and `tools/tests/test_delivery_merge.py`.
