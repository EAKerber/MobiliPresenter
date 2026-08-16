# ADR-0006 — ProjectState 2.0 slim

- Status: proposed for authority migration in M4B; consumer preparation implemented in M4A
- Date: 2026-08-16

## Context

`ProjectState 1.0` became a mixed container for current operational facts, durable product contracts, publication metadata duplicated from the SourceBuild manifest, narrative planning, implementation/tuning details, historical milestones, and toolbox discovery. That shape increased bootstrap cost and allowed the same fact to have more than one representation.

M3.5 established semantic ownership, managed authorities, component topology and a single supported writer per mutable managed authority. ProjectState should now follow the same authority discipline: current mutable facts belong in state; permanent knowledge belongs in contracts; recurring procedure belongs in tools; derived information belongs in projections; history remains recoverable from Git/evidence.

## Decision

ProjectState 2.0 will keep only:

- project identity and canonical repository;
- current control branch, active development branch and an explicit sanitation protection list;
- publication endpoint and pointer to the publication manifest;
- a minimal current development summary: initiative, phase, last verified checkpoint, next transition, blockers and PR identity.

It will remove:

- `project.productInvariants`;
- `git.publishedBranch`;
- duplicated publication `release` and `artifactSha256`;
- `development.constraints` and `development.plan`;
- the complete `operations` block.

`git.preserveBranches` becomes `git.protectedBranches`. The new name is intentionally narrow: it means an explicit current guard against automatic branch sanitation. It does **not** mean retained, archived, active, canonical, authoritative or permanently preserved. M6 owns branch lifecycle/retention.

The current work summary remains temporarily in ProjectState. M5 will decide the WorkState/Continuation evolution and may remove `activeDevelopmentBranch`, initiative, PR identity and blockers from ProjectState after a real work authority exists.

## Publication authority

ProjectState 2.0 keeps only `published.url` and `published.artifactManifest`. The pointed `SourceBuild 1.0` manifest owns the current release identity, source branch and source-build fingerprint.

The field historically named `artifactSha256` is not an artifact-bytes digest. The SourceBuild manifest declares it as `sha256(sourceBase|sourcePaths|buildCommand|publishPath)`. Derived projections therefore call it `sourceBuildFingerprint` and preserve its declared `fingerprintKind`.

## Constraint destination audit

Every value embedded in `ProjectState 1.0 development.constraints` must have an explicit destination before removal. M4A materializes `ops/migrations/project-state-2.0.json`, which classifies each current constraint as one of:

- durable contract;
- executable contract/gate;
- implementation authority;
- evidence;
- history.

M4B may migrate the live authority only if that map still covers the exact V1 constraint list with no duplicate or unresolved entry. The migration map is temporary migration evidence, not a replacement global constraints document.

## M4A / M4B boundary

### M4A — consumer decoupling

M4A does **not** mutate `ops/state/project.json` and does **not** replace the canonical `ops/schemas/project-state.schema.json`.

It introduces:

- a strict ProjectState V1 validator and candidate V2 validator;
- a stable `operational_view()` understood by readers regardless of V1/V2 representation;
- a pure deterministic `migrate_v1_to_v2()` candidate builder;
- a strict candidate V2 schema;
- a SourceBuild validator/projection;
- consumer boundary tests that prevent reintroduction of fields scheduled for removal;
- ProjectMachineInspection 0.3 using `protectedBranches`.

During M4A, `validate_current()` continues to accept only ProjectState 1.0.

### M4B — authority migration

M4B will perform the actual state/schema transition using the existing ProjectState canonical writer and Transition Protocol semantics: exact before-state, deterministic candidate, expected plan identity, atomic apply, readback and rollback.

M4B must remove temporary V1 compatibility and leave the canonical ProjectState schema accepting ProjectState 2.0 only.

## Consequences

Positive:

- ProjectState bootstrap becomes substantially smaller;
- publication facts have one authority instead of duplicated copies;
- tooling discovery no longer lives in state;
- product/tuning knowledge no longer grows the operational state;
- consumers become insulated from the raw schema through a small operational projection;
- M5 and M6 can migrate work and branch lifecycle independently.

Costs:

- M4A requires a temporary V1/V2 compatibility layer and migration evidence;
- ProjectMachineInspection changes from 0.2 to 0.3 because its public project projection renames `preserveBranches` to `protectedBranches`;
- Handoff changes from 1.0 to 2.0 because it no longer embeds the raw ProjectState.

## Non-decisions

This ADR does not define WorkState, branch retention/lifecycle classes, Capability lifecycle changes, Peer Recovery disposition, UI/Engine behavior, or product geometry/rendering policy.
