# Post-R8 exact-head CI qualification default — 2026-09-21

Status: **candidate operational-default simplification; no runtime, workflow, authority or persistent state added**.

## Purpose

After R8 and the governed Git-materialization optimization in PR #337, the largest repeated operational cost during integration is CI qualification.

The previous normal pattern was usually:

`PR head -> workflow runs -> run IDs -> jobs per run -> repeated polling -> merge`

GitHub already exposes the same job-level evidence as check-runs bound directly to a commit SHA. This recut makes that projection the normal qualification surface while preserving workflow/run/job inspection as the diagnostic fallback.

The change is procedural, not architectural.

## Evidence

Three recent PR heads were inspected directly through:

`GET /repos/EAKerber/MobiliPresenter/commits/<exact-head>/check-runs`

### Runtime recut — PR #337

Head `de1372e33c6e9ee748a7d0c0f1575efe424b57c7` returned real completed jobs including:

- `verify` — success;
- `ownership` — success;
- `snapshot` — success;
- an additional push-triggered `verify` — success;
- `prune` — skipped and not treated as a qualification gate.

The same head had previously been qualified by enumerating three workflow runs and fetching their jobs independently. The check-run snapshot preserved the evidence without requiring caller-managed run IDs.

### Runtime recut — PR #334

Head `894b764d3268530b600d449ab4f3eee4a759866b` returned:

- `verify` — success;
- `ownership` — success;
- `snapshot` — success;
- `prune` — skipped.

This matches the earlier exact-head workflow/job qualification.

### Docs-only discovery — PR #336

Head `4d4b4a6e09b809104cbf7ff77c884107fa9972c1` returned:

- `ownership` — success;
- `prune` — skipped.

Agent Ops and Supervisor Snapshot did not materialize because their current pull-request path filters did not apply to the changed architecture docs. The absence is safe only because applicability is derived from the current workflow definitions first; absence by itself is never PASS.

## Current applicability evidence

At the time of this recut:

- **Coordination Guard / `ownership`** triggers for every pull request.
- **Agent Ops / `verify`** triggers on PR changes to `AGENTS.md`, `ops/**`, `tools/**`, `docs/plans/**`, `docs/kickstarts/**`, or its own workflow.
- **Supervisor Snapshot / `snapshot`** triggers on PR changes to `AGENTS.md`, `ops/**`, `tools/**`, Manager/GitOps kickstart paths, or its own workflow.

This table is evidence only. It is not a second registry. Applicability must continue to come from the checked-in workflow definitions.

Because this recut changes `AGENTS.md`, all three gates are expected to materialize on its PR and the recut can dogfood the new path.

## Qualification algorithm

Given a PR:

1. observe the PR and bind qualification to its current exact `head_sha`;
2. observe the changed paths and the current workflow definitions;
3. derive which qualification gates are applicable;
4. fetch check-runs for the exact `head_sha`;
5. group the relevant check-runs by gate/job identity;
6. for every applicable gate:
   - no materialized check -> `UNKNOWN`;
   - queued/in-progress/non-terminal -> `WAITING`;
   - completed + success -> candidate `PASS`;
   - completed + failure/cancelled/timed_out/action_required/etc. -> `BLOCKED`;
   - skipped -> not PASS for an applicable gate;
7. if duplicate runs exist for the same applicable job, accept direct projection only when all relevant completed instances are non-conflicting successes; otherwise drill down;
8. if the PR changes a qualification workflow itself, or applicability cannot be derived unequivocally, drill down into workflow/run/job evidence;
9. merge only after all applicable gates are proven PASS and the merge uses the same expected PR head SHA.

The check-run view is a projection of GitHub CI, not a new authority.

## Normal path vs fallback

### Normal path

`PR -> exact head SHA -> current applicability -> check-runs snapshot -> PASS/WAITING/BLOCKED -> expected-head merge`

### Diagnostic fallback

Use workflow/run/job inspection when:

- an expected check is absent;
- duplicate check-runs conflict;
- a check fails;
- a check remains non-terminal unusually long;
- a qualification workflow itself changed;
- a job name is insufficient to disambiguate provenance;
- GitHub returns incomplete or otherwise ambiguous evidence.

Fallback inspection does not create a competing normal path; it is evidence drill-down.

## Measurable ergonomics effect

For the recent runtime PRs, the previous happy-path qualification required:

- fetch workflow runs for the SHA;
- preserve multiple run IDs;
- fetch jobs for Agent Ops;
- fetch jobs for Coordination Guard;
- fetch jobs for Supervisor Snapshot;
- repeat one or more of those reads while jobs were running.

The exact-head projection reduces a happy-path poll to one check-runs observation. A typical PR that needs two or three polls can therefore use roughly two or three CI observations instead of six to ten workflow/run/job observations.

The larger gain is cognitive: the caller no longer propagates multiple run IDs merely to answer whether the exact PR head has passed its applicable gates.

## Safety properties preserved

- exact PR head binding remains mandatory;
- applicable gates are derived before interpreting absence;
- missing evidence never becomes PASS;
- `UNKNOWN` / `WAITING` / `BLOCKED` remain distinct;
- workflow/run/job evidence remains inspectable;
- merge still uses expected-head protection;
- no auto-merge is enabled;
- no repository ruleset is weakened;
- no workflow is added or modified;
- no CI status/check is synthesized by MobiliPresenter.

## Auto-merge remains out of scope

The repository currently has `allow_auto_merge=false`.

The active default-branch ruleset protects deletion and non-fast-forward updates, but does not encode Agent Ops, Coordination Guard and Supervisor Snapshot as required checks. Enabling auto-merge merely to reduce polling would therefore move the operational guarantee to a weaker policy.

This recut intentionally leaves merge as a separate explicit action after qualification.

## Accounting

Expected implementation surface:

- `AGENTS.md`: stable operational rule only;
- this evidence/contract document;
- runtime LOC: 0;
- workflow LOC: 0;
- authority/state/lifecycle: 0;
- new public commands/tools: 0;
- new registry/configuration source: 0.

## Promotion gate

Promote this default only if the recut's own PR proves:

- `verify`, `ownership` and `snapshot` all materialize for its exact head;
- the three are visible and unambiguous in the check-runs projection;
- each completes with `success`;
- no workflow/run/job drill-down is required in the happy path;
- merge succeeds with expected-head guard;
- post-merge `main` readback matches the merge result.

## Abort conditions

Do not promote the projection if making it safe requires:

- a persistent CI authority or status cache;
- a parallel registry of workflow path filters;
- a workflow aggregator solely to create one synthetic PASS;
- a polling daemon/service;
- weakening missing-check behavior from UNKNOWN to PASS;
- altering branch protection/rulesets only to fit this recut.

If any of those become necessary, retain the current workflow/run/job qualification rather than add architecture.
