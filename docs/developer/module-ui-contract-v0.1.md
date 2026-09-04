# Module Data / UI Contract 0.1

## Baseline

This slice is derived from the branch currently published by Netlify at implementation start:

- branch: `work/ui/netlify-guided-configurator-current`
- observed deployed head: `296470e647474fa617d79d8b7c25dc52a979ba5c`
- working branch: `work/developer/module-ui-contract-v0.1`

The slice responds to the remaining UI contract needs recorded in `docs/ui/developer-ui-contract-needs-v0.2.md` and deliberately does **not** implement the full deterministic technical-drawing rewrite described in `docs/developer/deterministic-technical-drawings-handoff-v0.1.md`.

## Authority rule

Physical dimensions remain owned by Scene Core.

User-provided technical sheets for modules 01–07 are used only to fill semantic/editorial gaps such as titles, construction facts, hardware, functional descriptions and requested technical views. They do not overwrite existing `ModuleGeometry.dimensions`.

Example: the module 01 sheet displays 760 mm width, while Scene Core already carries a confirmed nominal width of 763.3 mm. The public UI descriptor therefore continues to publish 763.3 mm as physical authority.

## Delivered contract

### Complete module descriptors

`ViewerUiContract 0.2.0` now publishes `moduleDescriptors` for modules 01–07 without requiring a selected module. Each descriptor includes:

- alias and entity id;
- authored title/category;
- nominal/geometry dimensions from Scene Core;
- presentation order/labels for dimensions;
- technical-presentation availability;
- declarative presentation relation (`primaryEntityId` + `companionEntityIds`).

The compatibility alias list `catalog.modules` remains available for existing UI consumers.

### Technical catalog coverage

`CURRENT_TECHNICAL_CATALOG` now covers modules 01–07 plus lighting 08.

New semantic coverage was added for modules 01, 05, 06 and 07 from the supplied technical sheets. Existing module 02, 03 and 04 entries remain grounded in their prior catalog data, with presentation companions added where the current scene already has the corresponding entities.

Module 04 keeps its special dimensional presentation as `A × P × E`; the API does not assume every module is `L × A × P`.

### Presentation companions

The technical contract can now declare entities that should accompany a module in a presentation context without changing physical ownership or visibility rules. Current examples include:

- module 02 → oven, cooktop, stone and plinth;
- module 03 → sink, stone and plinth;
- module 05 → hood;
- module 06 → microwave and under-cab lighting;
- module 07 → refrigerator.

These are presentation relations, not new Scene Core ownership.

### Furniture finish as first-class state

`ViewerConfigurationState 0.1.1` adds `furnitureFinishPresetId` with canonical default `neutral-greige`.

The runtime now exposes one public `setFurnitureFinishPreset` action. The derived appearance applies the global finish to every module that owns a `front` material slot, then applies any explicit per-module override as a lower-level capability.

Consequences:

- module 03 now starts with the same neutral finish as the other modules;
- reset returns to the neutral global finish;
- product mode no longer loops through seven module writes to simulate a global change;
- `index.html` no longer injects seven `front=...neutral-greige` query parameters.

### Finish visual metadata

Furniture and stone options expose material-owned preview metadata (`materialId` and `previewColorSrgb`). Product UI no longer owns a preset-id → hex-color lookup table.

### Semantic keys

Facts/components may publish optional `semanticKey` values. UI presentation can consume these keys for icon/presentation decisions without inferring domain meaning from free text.

## Validation intent

The slice adds/updates coverage for:

- all seven module descriptors available before selection;
- Scene Core dimensions winning over rounded sheet display values;
- module 04 dimensional presentation order;
- presentation companion relations;
- neutral furniture finish as canonical default;
- module 03 neutral at initial configuration;
- one global furniture-finish action applying to all front-capable modules;
- finish preview metadata from material authority;
- removal of the product-mode global-finish fan-out and hardcoded swatch map;
- module 01 runtime UI evidence changing from `unavailable` to a real cataloged technical presentation.

## Explicit exclusions / next slices

This slice does not implement:

- the full deterministic technical drawing pipeline/projection rewrite;
- new UI layout or styling decisions;
- selection-emphasis tuning;
- zoom/focus controls;
- wood/PBR refinement;
- window/camera changes;
- appliance visual skins or appliance asset normalization.

The intended next architecture slice is **Technical Drawing System 0.1**, followed by a short visual-corrections slice. The next major product-realism focus after the UI information/drawing foundation is appliance presentation.
