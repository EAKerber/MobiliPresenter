# Engine / Scene Core — Branch Semantic Disposition 2026-08-19

Status: **semantic review complete; no functional salvage required**  
Owner: **Engine / Scene Core semantic authority**  
Observed control branch: `main` @ `c065dfcf3f24218cc6e27c9d07eb01e7398417ed`  
Related Work: `engine-planning-salvage`  
Scope: semantic disposition only. Branch deletion, retention shrink, cold-archive mutation and PR lifecycle are Manager/GitOps responsibilities.

## Answer First

The Engine / Scene Core review found **no current Engine implementation or contract fact that exists only on the reviewed historical branches and must be ported before retirement**.

`planning/scope-and-documentation` contains useful historical facts and explicitly preliminary proposals, but no accepted current Engine architecture missing from `main`. Its generic constraint/capability engine is a proposal, not a latent requirement. `archive/legacy-fixed-view-variants-2026-08-11` contains important historical reasoning, but the surviving principles — fixed camera, millimeters as physical authority, pixels as projection evidence, explicit provenance, module topology, the module-02 freestanding-range fallback and technical dependency modeling — are already represented by current Scene Core / Viewer Next contracts or current product documentation. Old pixel-calibration placements, the 3550 mm planning envelope, a universal 600 mm prototype depth, the sprite/overlay renderer and the historical generic rules DSL must not be resurrected as current authority.

`architecture/technical-presentation-contract-v0.1` no longer carries live TPC work: its only exclusive delta against current `main` is the evidence-only `docs/architecture/parallel-baseline-0.1.md`. `feature/viewer-runtime-ui-v0.1` is fully contained in `main` and has no Engine-exclusive commits. PR #3 and PR #12 therefore no longer need to remain open as active semantic work surfaces; Manager/GitOps may close them as historical/superseded **without merge**, after this disposition is durably integrated/read back.

## Observed branch matrix

| Branch | Head observed | Classification | Surviving knowledge | Minimum action | Owner | Safe retirement? |
| --- | --- | --- | --- | --- | --- | --- |
| `planning/scope-and-documentation` | `985d8644a11bb73e3b174e3135fe1c8ea3986e63` | `HISTORICAL_EVIDENCE` + concept-level `SUPERSEDED` / `ALREADY_PROMOTED` | Historical V7 recovery facts; planning rationale; preliminary constraint/documentation proposals | Preserve exact head in cold archive; close PR #3 as historical; no code/doc port required | GitOps for mechanics; Engine disposition complete | **YES_AFTER_COLD_ARCHIVE_READBACK** |
| `archive/legacy-fixed-view-variants-2026-08-11` | `f503a6fb7248e9c3dfadcc8d7801ad042d8fe26f` | `HISTORICAL_EVIDENCE` + concept-level `ALREADY_PROMOTED` / `SUPERSEDED` | Historical fixed-view experiments and provenance; no missing current Engine contract | Preserve exact head in cold archive; no functional port | GitOps for mechanics; Engine disposition complete | **YES_AFTER_COLD_ARCHIVE_READBACK** |
| `architecture/technical-presentation-contract-v0.1` | `b8708535efdd4340a82566d215f39b5ff1c34144` | `ALREADY_PROMOTED` + `HISTORICAL_EVIDENCE` | Only exclusive delta is old parallel-baseline evidence note | Close PR #12 as historical/superseded, do not merge; cold archive branch | GitOps | **YES_AFTER_PR_CLOSE_AND_COLD_ARCHIVE_READBACK** |
| `feature/viewer-runtime-ui-v0.1` | `eb383dcbd0ce87b7295e8c6c9ef5bf6325391588` | `ALREADY_PROMOTED` | No exclusive commits relative to current `main` | After PR #12 closes, cold archive/prune according to Branch Hygiene; no Engine dependency | GitOps; UI semantics already represented in current main | **YES_AFTER_DYNAMIC_PR_PROTECTION_CLEARS** |

## `planning/scope-and-documentation`

### Evidence observed

Against current `main`, the branch is 12 commits ahead and hundreds behind. Its exclusive content is overwhelmingly planning/documentation: baseline recovery, scope reassessment, decision log, documentation architecture and `CONSTRAINTS-AND-REQUIREMENTS.md`.

The decision log explicitly labels the general capability/requirement engine as **proposal, not accepted**. `CONSTRAINTS-AND-REQUIREMENTS.md` likewise describes itself as a preliminary proposal and leaves central decisions open.

Current `main` already has stronger, executable operational semantics for authority, provenance and handoff, while current Scene Core / Viewer Next own the actual product contracts.

### Concept disposition

- V7 ZIP identity, recovery lineage and planning-pause history → `HISTORICAL_EVIDENCE`.
- “Do not confuse proposals with decisions”, explicit authority/status, evidence-bound handoff → `ALREADY_PROMOTED` in current operational semantics and repository governance.
- General `AssemblyConstraintEngine`, capability providers, generic declarative rule DSL, conditional field engine and aggregate validity states → `HISTORICAL_EVIDENCE`, **not accepted current architecture**.
- Old open questions about free 3D/yaw/pitch/product direction → `SUPERSEDED` by the current fixed-camera / Guided Configurator / TPC direction.
- Current need for typed configurable choices/dependencies is tracked independently by issue #22 and must be designed from current requirements, not by resurrecting the old proposal.

### Salvage proposed

**None.** No current Engine / Scene Core code, schema or accepted architectural decision needs to be copied from this branch.

### Explicitly discarded as current requirements

Do not promote the historical generic constraint engine, capability namespace, rule operators, correction policy, old document tree proposal or old scope questions merely to avoid losing them. Cold archive is the correct preservation mechanism.

### PR #3

PR #3 served its historical planning purpose. It should **not** be merged into current `main`: that would reintroduce stale `AGENTS.md`/README state and proposals as if they were current. Manager/GitOps may close it with a historical/superseded disposition after this record is integrated.

## `archive/legacy-fixed-view-variants-2026-08-11`

### Evidence observed

The branch is a 122-commit historical prototype lineage. It contains module contracts, rules, fixed-view prototypes, pixel-space calibration, sprite/overlay experiments, test workflows and visual assets.

Current Scene Core now supplies physical module geometry in millimeters, source/evidence bindings, module topology, substitutions and a calibrated fixed perspective camera. Current fidelity tooling projects physical points to pixels without treating pixel scale as physical authority.

### Concept disposition

- Fixed camera / fixed frame as product direction → `ALREADY_PROMOTED`.
- “Pixel does not become millimeter”; presentation evidence is distinct from physical authority → `ALREADY_PROMOTED`.
- Evidence/confidence and unknown values must remain explicit → `ALREADY_PROMOTED`.
- Module structural topology (for example module 03 front segmentation) → `ALREADY_PROMOTED` in current Scene Core geometry/tests.
- Module 02 hidden → conventional freestanding range visual replacement → `ALREADY_PROMOTED` as a current Scene Core substitution group.
- Lighting dependency semantics → `ALREADY_PROMOTED` in current TPC, with current facts taking precedence over the narrower historical rule.
- Persistent scene while UI flow changes → `ALREADY_PROMOTED` by current Guided Configurator documentation.
- `3550 mm` wall width as active planning/geometry authority → `SUPERSEDED`; current Promob/DXF-backed Scene Core geometry is authoritative.
- Universal prototype depth `600 mm` → `SUPERSEDED`; current modules preserve their actual nominal/geometry depths.
- Pixel rectangles in `FixedViewVisualCalibration 0.2` as current camera/module placement authority → `SUPERSEDED`; retain as historical calibration evidence only.
- Raster sprite / per-module overlay / topology-placeholder renderer as active rendering architecture → `SUPERSEDED` by current Scene Core + Three.js renderer.
- Historical generic rules DSL (`moduleEnabled`, `propertyEquals`, `recommendedOneOf`, etc.) → `HISTORICAL_EVIDENCE`; do not reintroduce it as current runtime architecture.
- Generic handle recommendation heuristics by placement class → `HISTORICAL_EVIDENCE`; current hardware authority is explicit Scene Core hardware definitions/anchors, not that heuristic.
- Historical checklist/rail UI flow → not an Engine authority; current UI documentation already establishes the Guided Configurator as the integrated flow.

### Salvage proposed

**None.** The correct action is preserving the exact branch head in cold archive. A code/document port would create duplicate or stale authority.

### Explicitly discarded as current requirements

Do not restore `3550 mm`, universal 600 mm depth, pixel-to-module placement rectangles, the raster/sprite overlay pipeline, the old topology renderer, the generic rules DSL or placement-class handle recommendations as current facts.

## `architecture/technical-presentation-contract-v0.1`

### Evidence observed

Compared with current `main`, the branch has only one exclusive file: `docs/architecture/parallel-baseline-0.1.md`. That note explicitly says it records evidence only and that the old integration branch was the operative baseline at that time.

Current `main` contains the evolved Technical Presentation Package, typed technical view fidelity/coverage, geometry-derived technical projections in millimeters, current UI contract boundary and the historical-parallelization documentation that explicitly says the old branch topology is no longer the automatic current topology.

### Disposition

- TPC concepts and implementation → `ALREADY_PROMOTED`.
- Old parallel-baseline note → `HISTORICAL_EVIDENCE`.
- No remaining Engine work requires PR #12.
- Do **not** merge PR #12 into its stale UI base.

### PR #12

Manager/GitOps may close PR #12 as **superseded/historical, not merged** after this disposition is integrated. The current TPC authority is `main`, not the open historical PR.

## `feature/viewer-runtime-ui-v0.1`

The branch is an ancestor of current `main` (`ahead_by = 0`) and has no exclusive Engine or UI commits relative to current `main`.

From the Engine perspective there is **no semantic dependency** on this branch. Its only current lifecycle significance is that it is the base of open PR #12. Once PR #12 is closed, GitOps can treat it as duplicate history and retire it by the normal cold-archive / Branch Hygiene path.

## Answers to the required questions

1. **Current Engine / Scene Core knowledge in `planning/scope-and-documentation` not represented in `main`?**  
   No current accepted Engine knowledge. There are exclusive historical facts and proposals, but no accepted missing implementation/contract requiring promotion.

2. **Knowledge in legacy fixed-view that deserves salvage?**  
   No functional salvage. The surviving principles are already promoted; the rest is historical evidence or superseded mechanism/data.

3. **Items to implement/promote before archive?**  
   None.

4. **Items that are only history?**  
   V7 recovery/planning process, the preliminary constraint engine, old documentation architecture proposal, fixed-view pixel calibration, sprite/overlay prototypes, old rules DSL, old prototype workflows and historical UI flows.

5. **Old proposals that should be explicitly prevented from resurrection?**  
   Generic historical constraint/rules engine as a current requirement; `3550 mm` as current wall authority; universal 600 mm module depth; pixel rectangles as physical/current placement authority; sprite/overlay renderer; placement-class handle recommendation rules; old checklist/rail navigation as product baseline.

6. **Should PR #3 remain open?**  
   No. Its planning purpose is complete. Close as historical/superseded after disposition readback; do not merge.

7. **Does PR #12 still represent necessary Engine/TPC work?**  
   No. Current TPC is already in `main` and newer. The only branch-exclusive delta is historical parallel-baseline evidence.

8. **Lifecycle for `architecture/technical-presentation-contract-v0.1`?**  
   Historical. Preserve exact head in cold archive, close PR #12 without merge, then retire the branch.

9. **Real Engine semantic dependency on `feature/viewer-runtime-ui-v0.1`?**  
   None. It is fully contained in `main`; only PR #12 currently gives it dynamic lifecycle significance.

10. **Branches semantically `SAFE_FOR_COLD_ARCHIVE_AFTER_READBACK`?**  
    `planning/scope-and-documentation`, `archive/legacy-fixed-view-variants-2026-08-11`, `architecture/technical-presentation-contract-v0.1`, and — after PR #12 closure — `feature/viewer-runtime-ui-v0.1`.

11. **Smallest Work/PR sequence?**  
    Integrate this semantic disposition document → complete `engine-planning-salvage` through the canonical continuation writer → close PR #3/#12 as historical without merge → cold-archive exact heads → shrink ProjectState retention via canonical state tooling → run canonical Branch Hygiene plan/apply with readback.

12. **Does anything require user input?**  
    No semantic product decision is required for this retirement. Existing authorities are sufficient. A future implementation of generic configurable choices/dependencies remains separate work under issue #22 and must not be inferred from these historical branches.

## GitOps handoff

Semantic owner decision:

`NO_FUNCTIONAL_SALVAGE_REQUIRED`

For Engine / Scene Core, the reviewed refs may proceed through:

`semantic disposition -> cold archive exact heads -> ProjectState retention shrink -> canonical prune-plan/prune-apply`

with these guards:

- bind every cold-archive entry to the exact head reobserved immediately before archive;
- if any reviewed head differs from the SHA recorded above, invalidate this retirement plan and request semantic re-review of the delta;
- close PR #3 and #12 as historical/superseded, never merge them as a preservation strategy;
- use canonical writers for Work and ProjectState;
- preserve issue #22 independently as current future-contract work;
- do not treat this disposition as permission to reopen fixed-camera or physical-authority decisions.

No branch deletion, ProjectState retention change or cold-archive mutation is performed by the Engine semantic owner in this review.
