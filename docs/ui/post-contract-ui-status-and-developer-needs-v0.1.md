# UI post-contract status and Developer needs 0.1

Date: 2026-08-31

## Purpose

Record the UI state after integrating `Module Data / UI Contract 0.1` from PR #220, distinguish work that is now owned and executable by UI from work that still requires a public Engine/Developer contract, and prevent the UI from recreating domain authority locally.

This document is intentionally a coordination boundary. It does not authorize UI to infer missing product facts, compatibility, technical fidelity or commercial values.

## Current UI baseline

The current UI keeps the four-stage configurator flow:

1. Módulos
2. Acabamentos
3. Acessórios
4. Resumo

The scene remains persistent and independent from UI state. Camera/framing authority is unchanged.

The working baseline already includes the following product-facing refinements:

- compact responsive stage navigation;
- module visibility kept separate from module inspection;
- module detail as a contextual product surface;
- real-render-derived module thumbnails;
- responsive desktop / compact / mobile presentation modes;
- module-detail carousel on wide desktop;
- mobile finish cards arranged densely enough to avoid unnecessary nested scroll;
- fixed bottom action geometry corrected so stage content can scroll completely above the CTA;
- a Chromium clearance gate validating the mobile end-of-scroll condition;
- product-facing shell without exposing the internal project codename.

## Completed after PR #220

PR #220 removes several former UI bridges and publishes enough authority to make the following behavior contract-driven.

### Module catalog presentation

`ViewerUiContract 0.2.0` publishes `moduleDescriptors` for modules 01–07 without requiring the module to be selected first.

UI may now use, without local domain hardcode:

- module title / short presentation identity;
- category when published;
- authoritative dimensional values;
- the contract-defined display order and labels for dimensions.

The UI has been adapted so module cards can present descriptor title and dimensions even when the module is not the current technical-detail target.

### Furniture finish state

Furniture finish is now first-class configuration state and is mutated through the public global action instead of UI fan-out across seven modules.

No UI-owned global-finish state machine is required.

### Finish visual metadata

Finish options now publish `materialId` and `previewColorSrgb` from the appearance authority.

The UI can therefore render finish swatches and current-finish indicators from public metadata instead of maintaining preset-to-hex tables.

### Semantic technical icon hooks

Published facts and components may carry `semanticKey`, including currently observed keys such as:

- `electrical.outlet`;
- `electrical.cable`;
- `electrical.switch`;
- `hardware.hinge`;
- `hardware.drawer-runner`.

This is sufficient for UI to choose more specific presentation icons without textual inference. Icon drawing/style remains UI-owned; the semantic meaning remains contract-owned.

### Module presentation relations

The contract now publishes `primaryEntityId + companionEntityIds` for a module presentation.

UI may use this relationship to structure module presentation/detail without guessing which appliance, fixture, stone or accessory belongs to the module's product story. This does not authorize alternate camera behavior or geometry changes.

### Technical catalog coverage

Technical catalog coverage now includes modules 01–07 plus the declared lighting entry. Module 01 now resolves to an actual ready presentation instead of the former unavailable fallback.

## UI work now unblocked

The following work belongs to UI and can proceed without additional Engine/Developer changes:

1. remove the remaining preset-to-hex presentation bridge and consume `previewColorSrgb` end-to-end;
2. use `moduleDescriptors` consistently in module cards, labels and accessibility copy while preserving stable technical aliases where tests/contracts depend on them;
3. map published `semanticKey` values to specific icons from the existing UI icon library, falling back to category only when no semantic key is published;
4. improve information hierarchy in module details using the now-complete technical catalog and declared presentation relations;
5. improve absence/loading/error presentation without inventing facts;
6. continue responsive spacing, density, scrolling and interaction refinements;
7. continue commercial/editorial composition using only sourced facts already present in the public presentation package.

## Still requires Developer / authority work

### P0 — Real configurable accessories

The Acessórios stage is still blocked from becoming a real configurator surface.

The public UI contract still needs generic accessory/choice groups that expose, when supported by runtime:

- stable id and user-facing label;
- family/category;
- current selection;
- allowed options;
- availability;
- compatibility by module/target/context;
- reason when unavailable/incompatible;
- optional presentation asset/metadata;
- public mutation command only when an actual runtime binding exists.

Until this exists, UI must not build a parallel accessory catalog or present simulated selectable hardware as real configuration.

Related existing issue: #22.

### P0/P1 — Deterministic technical drawings

The current technical views are sufficient for schematic/dimensional presentation but are not yet a universally faithful fabrication-drawing pipeline.

Developer/Engine still owns:

- geometry-derived orthographic/internal/isometric generation;
- authoritative dimension placement;
- deterministic SVG/vector output or equivalent semantic drawing asset;
- explicit fidelity / coverage / omitted / provenance metadata;
- fail-closed behavior when a requested geometry-derived view cannot actually be produced.

UI owns typography, line weight, color, spacing and responsive composition only after the technical asset truth is published.

Related existing handoff: #217.

### P1 — Explicit absence semantics

For richer product surfaces, the contract should eventually distinguish where useful:

- known value;
- unknown / not provided;
- not applicable;
- declared but not bound;
- unavailable due to compatibility/runtime state.

UI can currently degrade conservatively, but explicit semantics would reduce ambiguity and make placeholders/warnings more precise.

### P2 — Commercial value / pricing authority

Resumo must not invent estimated values. If price/value is expected in the product flow, a commercial authority must publish the applicable value, currency, scope and any estimate/disclaimer semantics.

Until then, UI may summarize the configuration but must not manufacture pricing.

### P2 — Rich editorial/product copy, if desired

The UI can compose published technical facts into a stronger point-of-sale layout, but it should not invent product claims or benefits. If richer marketing copy is desired beyond the factual catalog, that copy needs a declared content/authority source.

## Explicitly not Developer blockers

The following remain UI responsibilities and should not be pushed back into the public contract merely to simplify CSS/presentation code:

- layout and responsive composition;
- stage navigation geometry;
- scroll behavior and fixed-action clearance;
- typography;
- spacing/density;
- flat visual style;
- icon drawing choice once a semantic key exists;
- carousel behavior;
- product-detail information hierarchy;
- button/icon styling;
- animation and interaction polish;
- mobile vs desktop presentation pattern.

## Promotion boundary

This branch may continue UI-only refinements against the published contract. It must stop and request Developer/authority work rather than introduce local domain models when a change requires:

- a new configurable accessory;
- new compatibility logic;
- a new mutation path;
- new product facts;
- new commercial values;
- higher technical-drawing fidelity than the published asset/contract supports;
- reinterpretation of renderer/Scene Core internals.

The intended result is a thinner UI: presentation logic becomes richer while domain inference and authority duplication decrease.