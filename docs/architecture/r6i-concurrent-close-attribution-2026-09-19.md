# R6i — concurrent close attribution

Status: implementation candidate for the live R6 paved-path canary.

## Trigger

After R6h restored the current close carrier, the historical governed Agent Cycle still closed as `UNKNOWN / UNATTRIBUTED_DURABLE_DELTA`. The remaining delta was not a lost mutation from that cycle: while the cycle stayed open, other qualified helper Works advanced `main` and `coordination/continuations`.

Treating every shared-authority head movement as attributable to the open cycle makes long-lived cycles impossible to close safely under legitimate concurrent repository evolution. Ignoring that movement would be worse because it would weaken close attribution.

## Reclet

R6i adds one read-only evidence kind, `AgentCycleNonInterferenceReadback 0.1`, and teaches the existing close recovery to compose it only for the exact shared-authority drift shape already observed.

The evidence is bound to the Agent Cycle and Work and covers only the exact source-head changes it proves. It is admissible only when:

- the bound Work exists in both before/after Project Machine snapshots and is byte-for-byte unchanged;
- the Work branch is not `main`;
- the `coordination/continuations` comparison is linear/ahead and does not touch `ops/continuations/<workId>.json`;
- the `main` movement is a first-parent chain of merged PRs;
- every merged PR belongs to a branch/PR other than the bound Work;
- remote branch heads still equal the after-context heads when the proof is composed.

Any ambiguity, direct main commit, bound-Work touch, non-linear history, stale readback, or changed Work leaves the close `UNKNOWN`.

## Boundary

This is evidence composition, not a new authority or lifecycle. It stores no state, authorizes no mutation, performs no replay, changes no ownership semantics, and leaves the existing Agent Cycle close primitive as the sole classifier. The current compatibility workflow already routes this failure to the recovery carrier; no new workflow or protocol is introduced.

If later R6/R7 experience shows that long-lived cycles do not recur, this evidence composer is an explicit R8 retirement candidate. If independent Works repeatedly encounter legitimate shared-authority drift, it becomes evidence that non-interference attribution is a structural close capability rather than migration scaffolding.
