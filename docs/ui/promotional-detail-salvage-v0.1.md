# M6-SALV-UI-A — Promotional Detail Semantic Salvage & Disposition

Status: **semantic salvage complete; no functional port required**  
Historical source: `ui/promotional-detail-v0.2` @ `232e12f4cf8d333d6b387388a2bde1379f8be368`  
Observed current baseline: `main` @ `ee2d337df88beaff27e84ca525722153b42daa6f`  
Owner: `ui-ux`  
Continuation: `ui-promotional-salvage`

## Purpose

This document resolves the remaining semantic salvage obligation for
`ui/promotional-detail-v0.2` before that branch becomes eligible for cold
archive. It does **not** promote the historical branch as a merge/cherry-pick
source.

The branch is materially stale relative to the integrated Guided Configurator
baseline. Its useful product/UI ideas are evaluated concept-by-concept against:

1. `ops/state/project.json`;
2. `docs/kickstarts/roles/ui-ux-current.md` and the current UI/UX Kickstart;
3. `docs/ui/guided-configurator-v0.3.md`;
4. `docs/ui/decisions-v0.1.md`;
5. `viewer-next/src/api/ui-contract.ts`;
6. current `viewer-next/src/ui/**`.

## Disposition vocabulary

- `ALREADY_PROMOTED` — the surviving concept is already represented in current
  docs/code and does not need a new port.
- `SUPERSEDED` — a later integrated UI decision explicitly replaced the
  historical behavior.
- `HISTORICAL_ONLY` — implementation/rationale remains useful only as history;
  replaying it would add obsolete coupling or churn.
- `BLOCKED_BY_CONTRACT` — the historical intent remains legitimate but faithful
  implementation still depends on a public contract that does not exist.
- `PORT` — still-valid behavior absent from current baseline and safe to port
  inside current UI ownership.

No item in this review requires `PORT`.

## Concept disposition

| Historical concept | Disposition | Current evidence / reason |
| --- | --- | --- |
| Warm neutral / editorial product palette | `ALREADY_PROMOTED` | Preserved by accepted UI decision `UI-D008` and current `runtime-controls.css` tokens. |
| Flat / restrained controls | `ALREADY_PROMOTED` | The current visual baseline already avoids the raised admin-panel treatment and remains free to refine controls inside UI authority. Replaying the historical override layer is unnecessary. |
| Selection independent from detail expansion | `ALREADY_PROMOTED` | Current `runtime-controls.ts` keeps `detailExpanded` local to UI; closing detail does not clear `selectedModuleAlias`. |
| One dominant technical view with compact selector | `ALREADY_PROMOTED` | Current module detail chooses one active technical asset and exposes a compact selector for the ready assets. |
| Disclosure before nested technical overflow | `ALREADY_PROMOTED` | Current detail uses a disclosure for representation coverage/evidence and keeps the main detail body as the vertical surface. |
| Semantic technical icon language | `ALREADY_PROMOTED` (concept) + `HISTORICAL_ONLY` (implementation) | Guided Configurator explicitly preserved semantic technical icon language as a reusable concept. The old `editorial-enhancements.ts` implementation is not portable: it post-processes the obsolete shell DOM and includes mappings for concrete component IDs such as `module02/component/outlet-20a`. If icons are refined later, they must derive only from published semantics such as `TechnicalTextFact.category`, `TechnicalComponentRequirement.kind`, notice severity, or another public typed field. |
| No user-visible internal codename/brand | `ALREADY_PROMOTED` | Product-facing naming is a current UI concern; the old DOM-removal shim is unnecessary and tied to the superseded shell. |
| Three-page rail/drawer (`Módulos / Cores / Acessórios`) | `SUPERSEDED` | Guided Configurator UI 0.3 replaced it with four stages: `Módulos / Acabamentos / Acessórios / Resumo`. |
| Drawer auto-collapse / rail toggle state model | `SUPERSEDED` | It belongs to the retired rail/page architecture and must not be revived as hidden parallel state. |
| Historical `Cores` terminology | `SUPERSEDED` | Current baseline uses `Acabamentos`. |
| Placeholder blocks such as “Descrição comercial a definir” | `SUPERSEDED` | Current baseline renders technical blocks only when supported and uses an explicit unavailable state when the selected module has no TPC. Unknown data is not converted into pseudo-content. |
| Generic configurable accessories | `BLOCKED_BY_CONTRACT` | Issue #22 remains the contract dependency. `ViewerUiContract 0.1.1` still does not expose a generic configurable-accessory catalog, compatibility model, or mutation commands. Current empty/unavailable state is correct. |
| Module editorial metadata / real thumbnails | `BLOCKED_BY_CONTRACT` | Issue #22 remains the authority boundary. UI must not infer thumbnails or duplicate a catalog. |
| Mounting a separate editorial-enhancement layer from `bootstrap.ts` | `HISTORICAL_ONLY` | `bootstrap.ts` is no longer normal UI ownership, and a MutationObserver post-processing layer would duplicate the current direct Guided Configurator implementation. |
| Editing `viewer-next/index.html` for this UI slice | `HISTORICAL_ONLY` | It is outside normal UI ownership and is not required by any surviving concept. |
| Historical runtime UI smoke selectors | `HISTORICAL_ONLY` | They gate the superseded shell/rail structure. Current runtime UI smoke covers the Guided Configurator baseline instead. |

## File-level disposition

The historical branch differs from current `main` in eleven UI-related files.
They are resolved as follows:

| Historical path | Disposition |
| --- | --- |
| `docs/ui/README.md` | `ALREADY_PROMOTED` / current README now records Guided Configurator precedence and current ownership rules. |
| `docs/ui/decisions-v0.1.md` | `ALREADY_PROMOTED` / current decision log retains surviving decisions and explicitly marks replaced ones superseded. |
| `docs/ui/promotional-detail-v0.2.md` | `HISTORICAL_ONLY` / retained as source history after this disposition document records the surviving concepts. |
| `viewer-next/index.html` | `HISTORICAL_ONLY` |
| `viewer-next/src/bootstrap.ts` | `HISTORICAL_ONLY` |
| `viewer-next/src/ui/editorial-enhancements.ts` | `HISTORICAL_ONLY` |
| `viewer-next/src/ui/editorial-overrides.css` | `HISTORICAL_ONLY` |
| `viewer-next/src/ui/runtime-controls.css` | `SUPERSEDED` as a branch-level implementation; current file is the integrated baseline. |
| `viewer-next/src/ui/runtime-controls.ts` | `SUPERSEDED` as a branch-level implementation; current file is the integrated baseline. |
| `viewer-next/tests/runtime_ui_smoke.py` | `SUPERSEDED` as a branch-level test shape; current smoke gates the four-stage baseline. |
| `viewer-next/tests/ui_editorial.test.mjs` | `HISTORICAL_ONLY` / its assertions target obsolete shell classes and explicitly require a concrete component-id mapping that must not be restored. |

## Why no code port is correct

A semantic salvage is not successful merely because it produces a code diff.
The historical branch was the source of several ideas that the later Guided
Configurator already integrated in a cleaner architecture. Re-applying those
ideas would duplicate behavior.

The only conspicuous implementation absent from current code is the old
semantic-icon enhancement layer. Its **design intent** is already retained by
the Guided Configurator documentation, while its **mechanism** violates the
current anti-corruption direction by depending on obsolete DOM classes and
concrete domain IDs. Preserving the intent and rejecting that mechanism avoids
both knowledge loss and accidental architectural regression.

A future visual refinement may implement semantic icons directly inside
`viewer-next/src/ui/**`, but that would be a new UI slice, not unfinished
historical salvage. It must consume typed public semantics rather than branch
specific IDs or text heuristics.

## Contract dependencies preserved

Issue #22 remains open for:

- authoritative module presentation metadata / thumbnail references;
- generic configurable accessories;
- compatibility and current selection;
- mutation commands only when runtime binding exists;
- semantic distinction between configurable choices, specifications,
  components, dependencies, notices and representations.

This salvage does not close, weaken or work around that dependency.

## Safety / ownership readback

This salvage intentionally makes no changes to:

- `viewer-next/src/api/**`;
- `viewer-next/src/runtime/**`;
- `viewer-next/src/renderer/**`;
- `viewer-next/src/presentation/**`;
- `viewer-next/src/bootstrap.ts`;
- `viewer-next/index.html`;
- Scene Core;
- ProjectState;
- PR #12;
- camera behavior;
- the historical `ui/promotional-detail-v0.2` ref itself.

The only repository mutation for this slice is this UI-owned disposition record.

## Completion decision

`ui/promotional-detail-v0.2` contains no remaining current UI knowledge that is
available only on the historical branch.

Semantic result: **SAFE_FOR_COLD_ARCHIVE_AFTER_WORK_COMPLETION_READBACK**.

Operational archive/retention changes belong to the subsequent GitOps slice and
must independently observe the exact branch head, ProjectState protections,
open PRs, Work authority and the live prune plan.
