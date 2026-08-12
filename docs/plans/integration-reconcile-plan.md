# Integration Reconcile Plan 0.1

Status: experimental, read-only

## Problem

Parallel slices can remain technically valid while their declared PR base becomes historical. GitOps then needs to determine, deterministically, whether the old base is already contained in the control branch, whether the slice diverged, which domains it touched, whether shared resources are involved, what CI actually validated the head, and whether ProjectState identity is aligned.

PR #33 exposed the recurring pattern:

- Developer started from `integration/viewer-parallel-v0.1`;
- `main` advanced independently;
- the Developer head remained valid and CI-green;
- the declared base was already contained in `main`;
- the safe mechanical action was to retarget to `main` and revalidate before promotion.

## Tool

Experimental surface:

```bash
python3 tools/integration_reconcile.py reconcile-plan <PR> --json
```

Optional target override:

```bash
python3 tools/integration_reconcile.py reconcile-plan <PR> --target main --json
```

The default target is `git.controlBranch` from `ops/state/project.json`.

## Contract

`IntegrationReconcilePlan 0.1` contains:

- exact PR number, state, draft/merged status, head ref/SHA and declared base ref/SHA;
- exact observed target branch/SHA;
- ancestry summaries for declared-base → target and target → head;
- changed-file inventory and deterministic domain classification;
- shared-resource detection for the current UI × Engine frontier;
- obvious owner-boundary signals for `engine/*`, `ui/*` and `ops/*` branches;
- latest observed non-Agent-Ops CI status per workflow name for the PR head;
- current canonical Developer identity and fields that should be reviewed after merge;
- a deterministic recommendation and `planHash`.

The plan is always read-only:

```json
{"applyEligible": false}
```

No retarget, merge, branch write or ProjectState mutation exists in 0.1.

## Recommendations

The planner can currently emit:

- `retarget-to-control-and-revalidate` — declared base is already contained in control;
- `manual-reconciliation` — ancestry is not a clean containment case;
- `semantic-owner-review` — obvious cross-boundary paths were detected;
- `fix-ci-before-integration` — current target is correct but head CI is failed;
- `wait-for-ci` — CI is pending or unproven;
- `review-current-target` — target is already control and CI is green;
- `already-merged` / `no-action` — no integration mutation is appropriate.

These are operational recommendations, not semantic approval.

## Boundary policy

The tool intentionally distinguishes shared contract files from hard violations.

For `engine/*`:

- `viewer-next/src/ui/**` is a boundary violation;
- `ops/**`, `tools/**` and `AGENTS.md` are GitOps boundary violations;
- `viewer-next/src/api/**` is a shared-contract review, not an automatic violation.

For `ui/*`:

- presentation/runtime/renderer/fixtures and `scene-core/**` are Engine-domain violations;
- `viewer-next/src/api/**` requires shared-contract review;
- GitOps files remain outside UI ownership.

For `ops/*`, product paths are flagged as GitOps/product boundary violations.

The classifier deliberately does not attempt to decide product semantics.

## PR #33 fixture

The unit fixture preserves the pre-retarget facts observed during the TPF-01 integration:

- declared base `integration/viewer-parallel-v0.1`;
- control `main` four commits ahead of that base;
- Developer head nine commits unique and four commits behind control;
- 8 changed Viewer Next files;
- 2 shared `src/api/**` files;
- no Engine→UI boundary violation;
- Viewer Next CI green.

Expected recommendation: `retarget-to-control-and-revalidate`.

## Promotion criteria

Do not add an apply mode from this experiment alone. Revisit after at least two additional real reconciliation events.

Possible future steps, only after repeated evidence:

1. route the planner through `tools/agent.py integration reconcile-plan`;
2. add explicit state-reconciliation planning;
3. add guarded mechanical operations such as retarget using expected PR head + `planHash`;
4. keep semantic approval and merge as separately authorized transitions.
