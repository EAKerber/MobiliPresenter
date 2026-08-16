# GitPrunePlan 0.2 — evidence-based branch hygiene

## Goal

Make branch cleanup auditable enough to run continuously without turning naming conventions into destructive authority.

`GitPrunePlan 0.2` remains read-only. It prepares a future automatic apply surface by making every delete candidate explainable from current observable state.

## Strong deletion evidence

A branch may become `delete-candidate` only when it is not protected and at least one current-head proof exists:

- the current branch head is an ancestor of, or identical to, the current control branch head;
- a merged PR exists whose recorded head SHA exactly equals the branch's current SHA;
- a closed unmerged PR has an explicit terminal disposition (`Superseded`, `Rejected`, validation-only, preview-only) and its recorded head SHA exactly equals the branch's current SHA;
- the branch is an exact-SHA duplicate of another branch already proven integrated by one of the rules above.

Branch prefixes such as `engine/`, `agent/`, `ops/`, `tmp/` never constitute deletion evidence.

## Protections

Protection always wins over deletion evidence:

- control branch;
- published branch;
- active development branch;
- `git.preserveBranches`;
- any current open PR head.

`archive/*` and `backup/*` remain historical/rollback anchors. `variant/*` remains `archive-first`.

## Head-drift rule

Historical PR state never applies indefinitely to a moving branch. If a PR was merged/superseded/rejected but the branch has received commits since that PR head, the PR evidence no longer authorizes deletion. The branch must be independently proven absorbed or reviewed again.

## Observation completeness

A plan is `applyEligible=true` only when all of the following are observed:

- complete remote branch inventory;
- complete PR history within the bounded pagination contract;
- ancestry for every observed ref;
- current control SHA.

This means only that the evidence snapshot is complete enough to be input to a future destructive executor. Version 0.2 deliberately has `destructiveApplySupported=false`.

## Future automatic apply boundary

A future delete executor should require, per branch:

1. an accepted `GitPrunePlan 0.2` `planHash`;
2. re-observation of the branch ref immediately before deletion;
3. exact equality with the SHA recorded in the plan;
4. re-observation that the branch is still not protected or an open PR head;
5. deletion of only entries with `action=delete-candidate` and `autoDeleteEligible=true`;
6. independent readback that the ref disappeared;
7. fail-closed behavior on any drift.

No batch should continue past a drifted or ambiguous branch without a new plan.

## CI audit

Agent Ops generates a live `git-prune-plan` artifact on operational PRs. This keeps the classification exercised against the real repository before destructive apply exists and makes branch accumulation visible during normal governance work.
