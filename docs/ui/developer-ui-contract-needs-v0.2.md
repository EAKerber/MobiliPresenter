# Developer handoff — UI contract needs v0.2

Status: proposed handoff for Developer / Engine / presentation contract
Source UI work: PR #214 (`work/ui/netlify-guided-configurator-current`)
Base observed: `main@539173ed46de49b90ca32f09d3ac4caabd183c56`

## Purpose

The current Guided Configurator can already implement most remaining visual work without upstream changes. This document records only the data/semantic gaps that should not be inferred or hardcoded by the UI.

The governing rule remains:

> Domain semantics, relationships, authoritative state and availability come from the public contract. UI owns hierarchy, layout, styling and interaction presentation.

This is not a request for the Developer to redesign the UI.

## Current public surface observed

`ViewerUiContract 0.1.1` currently publishes:

- module aliases only (`modules: ModuleAlias[]`);
- front, stone and lighting presets as `{ id, label }`;
- selected module alias;
- per-module visibility;
- per-module front preset overrides;
- global stone and lighting preset ids;
- selected technical presentation availability;
- selected `TechnicalPresentationPackage`;
- selected technical diagram assets;
- commands for module visibility, per-module front preset, stone, lighting, reset and module selection.

The selected `TechnicalPresentationPackage 0.1.1` already carries useful semantics: identity, dimensions, specifications, components, notices, dependencies, controls, finishes, technical view requests, geometry-derived view data, fidelity/coverage/omissions and provenance.

The gaps below are therefore intentionally narrower than a new general-purpose schema.

---

## P0 — blocks or materially weakens the next UI pass

### 1. Global furniture finish must be a first-class configuration concept

### Problem

The product UX treats furniture colour as one global choice. The current public state is still `frontPresetByModule`, and the UI has to emulate a global choice by calling `setFrontPreset(alias, preset)` for every module.

That creates avoidable semantic debt:

- global state can drift;
- newly introduced modules are not naturally covered;
- reset/default behaviour is not defined as one product-level value;
- the UI must know that all front presets should move together.

The requested initial product state is the neutral grey/greige finish for the whole kitchen. At present, an empty `frontPresetByModule` means “use original scene appearance”, which leaves at least module 03 visually wooden.

### Needed semantic capability

Equivalent functionality to:

```ts
snapshot.furnitureFinishPresetId: FrontPresetId
catalog.furnitureFinishPresets: readonly FinishOption[]
api.setFurnitureFinishPreset(presetId)
```

Naming is not prescribed. A scope-based generic configuration model is equally valid.

The authoritative product default should resolve to the neutral grey/greige preset (currently `neutral-greige`) so `resetConfiguration()` returns to the same coherent product baseline.

Legacy per-module front controls may remain for diagnostics or lower-level tooling if useful; the product UI should not need them for the normal path.

### Acceptance

- fresh product configuration renders all furniture in the neutral grey/greige finish;
- reset returns to that same product default;
- one public write changes the furniture finish globally;
- UI no longer fans out N writes across module aliases.

---

### 2. Module catalog descriptors must exist without selecting the module

### Problem

`ViewerUiCatalog.modules` is currently only an alias list. Name, category and dimensions are available only when the selected module has a ready technical presentation.

Consequences today:

- module cards fall back to `Módulo 01`, `Módulo 05`, etc.;
- summary rows cannot use authoritative titles for every module;
- dimensions cannot be shown in the module list unless that module has first been selected and has a technical catalog entry;
- UI cannot distinguish “metadata unknown” from “technical presentation unavailable”.

### Needed semantic capability

A lightweight catalog descriptor for every configurable module, conceptually:

```ts
interface ViewerUiModuleDescriptor {
  alias: ModuleAlias;
  title: string;
  shortLabel?: string;
  category?: string;
  dimensions?: DimensionTripleMm;
  technicalPresentationStatus?: "ready" | "unavailable";
}
```

Do not duplicate physical dimensions if the authoritative source already exists. The adapter can compile the descriptor from Scene Core + technical catalog.

### Acceptance

The UI can render the complete module list and summary with authoritative names and available dimensions **without changing selection** and without hardcoded alias-to-title maps.

---

### 3. Declare the entities that belong in a module’s promotional/detail render

### Product need

Module details should include a real rendered “module view”: conceptually the same capture pipeline already used for thumbnails, but with the appliances/items that belong to the module included.

Examples:

- oven/fogão module should visually include the relevant appliance(s);
- sink module may include the sink/fixture that belongs to that composition;
- a module should not acquire nearby appliances merely because their bounding boxes or positions happen to overlap.

### Current gap

Scene Core can render and hide individual entities, so the rendering mechanism itself already exists. What is missing from the public/presentation semantics is an authoritative answer to:

> Which non-module entities are part of this module’s product presentation?

`TechnicalDependencySpec` is not sufficient: dependency and presentation companionship are different relations. `TechnicalComponentRequirement.linkedEntityId` is optional and is not currently a general presentation contract.

### Needed semantic capability

A declarative relation or presentation specification, for example:

```ts
presentation: {
  primaryEntityId: string;
  companionEntityIds: readonly string[];
  // optional, only if necessary:
  includeEnvironment?: boolean;
}
```

Alternative generic relation naming is welcome (`presentation-companion`, `hosted-item`, etc.).

The Developer does **not** need to return a PNG through the API if that is architecturally undesirable. Publishing the authoritative entity set is enough for UI/tooling to use the existing renderer and capture pipeline deterministically.

### Acceptance

UI/tooling can create a module detail render using the real viewer without:

- spatial heuristics;
- string matching;
- hardcoded appliance IDs per alias;
- accidental inclusion of unrelated neighbouring items.

---

### 4. Finish options need public visual metadata

### Problem

`ViewerUiOption` exposes only `id` + `label`. The product UI therefore currently hardcodes swatch colours for `warm-wood` and `neutral-greige`.

That is presentation data derived from an appearance authority and should not be duplicated in UI code.

### Needed semantic capability

Each finish option should carry enough visual preview information to render a swatch generically, e.g. one of:

```ts
visual: { kind: "solid"; color: "#..." }
visual: { kind: "texture"; assetUrl: "..."; fallbackColor?: "#..." }
visual: { kind: "material"; materialId: string; previewColor?: "#..." }
```

Exact shape is not prescribed. `materialId` already exists in compiled finish options, but the global UI catalog does not expose equivalent visual metadata and should not require a selected TPC just to draw the finish selector.

### Acceptance

UI can render front/stone finish swatches without preset-id-specific colour tables.

---

## P1 — necessary for faithful product/technical presentation

### 5. Technical views need richer authoritative geometry or authored assets

### Current limitation

The contract correctly exposes fidelity and omissions, but current useful geometry-derived coverage is primarily the module front (`width-height`). Side views and isometric views often degrade to envelope schematics; `CompiledTechnicalViewGeometry` is currently constrained to `width-height`, and common omissions include `hardware` and `hidden-geometry`.

This is why the current technical drawings are visually much weaker than the product scene.

### Needed capability

Any architecture that gives the presentation layer trustworthy content for the requested views is acceptable. Candidates include:

- geometry-derived projections for `depth-height` and `width-depth`;
- geometry-derived/isometric primitives from the real module geometry;
- authored SVG/vector assets for views that cannot be derived faithfully;
- internal-layout assets/geometry where known;
- explicit openings/cutouts and hardware when authoritative;
- dimension annotation intent/axes where the drawing needs more than overall envelope dimensions.

Existing `fidelity`, `coverage` and `omitted` metadata should remain authoritative.

### Acceptance

For each published view, the UI can clearly know whether it is:

- authored;
- geometry-derived;
- schematic;
- externally required/unavailable.

A geometry-derived view must not silently collapse to a generic envelope.

---

### 6. Technical entities need semantic identifiers fine-grained enough for meaningful iconography

### What already exists

The contract already provides useful broad categories:

- fact category (`function`, `construction`, `installation`, `finish`, `hardware`, `electrical`);
- component kind (`hardware`, `electrical`, `panel`, `interface`, `other`);
- dependency relation and target kind;
- notice severity.

These are enough for **category-level** icons.

### Remaining gap

For meaningful technical iconography — e.g. outlet/tomada, switch, drawer runner, hinge — the UI would currently need to parse human-readable labels such as `Tomada 20 A` or `Corrediça telescópica reforçada H45`.

### Needed semantic capability

Add an optional stable semantic identifier to facts/components/dependencies when a more specific icon or treatment is meaningful, e.g.:

```ts
semanticKey?: "electrical.outlet" | "electrical.switch" | "hardware.drawer-runner" | ...
```

Do not encode UI icon names (`lucide-plug`, etc.). The contract should declare domain semantics; UI maps those semantics to its chosen icon set.

Specific ratings/specifications (`20 A`, `H45`) remain data fields/text, not necessarily part of the icon key.

### Acceptance

UI can choose a technically meaningful icon without parsing labels or descriptions.

---

### 7. Distinguish unknown data from not-applicable data

### Problem

An empty collection currently cannot always tell UI whether:

- the concept does not apply to this module;
- the information is genuinely not known/mapped yet;
- the catalog entry is incomplete.

The UX direction explicitly allows real knowledge gaps and should show placeholders only when the missing information is meaningful.

### Needed capability

A lightweight coverage/knowledge-status mechanism at either section or field level, conceptually:

```ts
"known" | "unknown" | "not-applicable"
```

The exact representation can be more compact (coverage map, catalog completeness metadata, etc.).

### Acceptance

UI can omit non-applicable blocks while explicitly representing known knowledge gaps without guessing from `[]`, `null` or missing fields.

---

### 8. Optional editorial/commercial module content

### Problem

The technical catalog contains factual `function` text, but the desktop detail surface is intentionally also a point-of-sale/editorial surface. UI must not transform technical facts into invented marketing claims.

### Useful optional data

For modules where this knowledge exists:

- short description;
- 1–3 product benefits/highlights;
- optional editorial priority/importance;
- optional badge/feature labels.

This should remain optional. Missing editorial data must not block a module.

### Acceptance

UI can present authored commercial copy when available and fall back to factual technical content when it is not, without generating claims.

---

## P1/P2 — already known but still absent from `ViewerUiContract 0.1.1`

### 9. Generic configurable accessory/choice groups

This remains aligned with the previously identified accessory contract gap (see existing issue #22 / related handoffs).

The Accessories stage needs generic published choices rather than reinterpretation of renderer presentation controls such as `lightingPresets`.

Minimum semantics:

- group id/label;
- option id/label;
- scope/target;
- selected state;
- availability/compatibility + reason;
- runtime binding/implementation status;
- optional visual metadata.

The important rule remains:

> configurable choice != technical specification != dependency.

---

### 10. Commercial value/price summary (not a blocker for current UI pass)

The current public contract exposes no price/value authority. The UI therefore intentionally omits real value rather than inventing one.

When commercial integration becomes in scope, UI will need at minimum:

- amount;
- currency;
- whether value is exact/estimated/from-price;
- scope/inclusions;
- availability state/reason.

This is not required to proceed with current visual refinement.

---

## Explicitly NOT Developer/API work

The following items remain UI-owned and should not expand this Developer recut:

- font family, scale, weights and typography rhythm;
- layout/disposition of the right + bottom detail surfaces;
- styled scrollbars and scroll containment;
- icon library and visual style;
- mapping already-published semantic categories to icons;
- borders, radius, spacing and hierarchy;
- animation/microinteraction;
- visual treatment of fidelity labels and technical drawing captions;
- SVG styling where the authoritative geometry already exists;
- selection contour styling;
- responsive composition of the product-detail panel.

## Suggested implementation order

1. Global furniture finish + neutral-grey canonical default.
2. Module catalog descriptors.
3. Module presentation companion/entity relations.
4. Finish visual metadata.
5. Generic configurable choices/accessories (existing related work may be reused).
6. Specific technical semantic keys for iconography.
7. Technical-view geometry/authored asset expansion.
8. Knowledge-status/editorial extensions when their source data is available.

The ordering is not mandatory; existing Developer work may make a different batching cheaper.

## Exit criterion for the contract recut

A successful contract evolution should allow product UI to implement the next design pass while deleting, not adding, domain-specific hardcode.

Concretely, UI should no longer need to:

- fan out a global colour choice across every module;
- hardcode finish colours by preset id;
- hardcode module names/dimensions by alias;
- infer which appliance belongs in a module hero render;
- parse technical prose to determine the semantic icon;
- call empty data “not applicable” or “unknown” by guesswork;
- represent a technical envelope as if it were a faithful fabrication view.

Subtractive/unifying contract solutions are preferred over parallel UI-specific data models.
