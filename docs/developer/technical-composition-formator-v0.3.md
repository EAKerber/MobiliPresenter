# Technical Composition / Formator v0.3

## Objective

Move technical-dimension placement out of ad-hoc SVG/UI decoration and into a deterministic composition planner.

This slice does **not** create new physical authority. Scene Core remains authoritative for geometry and nominal dimensions; authored internal layouts remain authored technical data with explicit provenance.

## Ownership

Geometry-derived isometric SVGs produced by `technical-diagram.ts` now declare:

- `data-product-dimensions="true"`
- `data-technical-composition="technical-composition/v0.3"`

This makes the legacy UI-side isometric dimension decorator inert. The technical renderer is the only active writer of external isometric dimensions in this slice.

## Composition model

`technical-composition.ts` introduces a pure planner for overall isometric dimensions.

Each dimension has:

- semantic identity (`overall/width`, `overall/height`, `overall/depth`);
- provenance (`scene-geometry`);
- scope (`overall`);
- preferred external regions;
- discrete lanes inside a region;
- a computed label bounding box.

The initial regions are `top`, `right`, `bottom`, `left` plus diagonal fallback regions.

Preferred placement is deterministic:

- height prefers left;
- width prefers bottom;
- depth prefers right;
- each axis has ordered fallback regions.

A lane is accepted only when the label remains inside the SVG viewBox, outside the inflated geometry envelope and clear of previously placed labels.

If no valid placement exists, the planner fails closed with `TECHNICAL_COMPOSITION_UNPLACEABLE_DIMENSION` instead of silently overlapping labels.

## Deduplication gate

The planner accepts exactly one overall guide per physical axis. Duplicate guides fail with `TECHNICAL_COMPOSITION_DUPLICATE_DIMENSION`.

Numeric equality is not semantic identity. Authored internal segments such as module 03's `390 / 400 / 400` remain separate from overall width/depth/height and are not deduplicated against them.

## Stress fixtures

### Module 03

The geometry-derived isometric view must:

- preserve real drawer/door/carcass primitives;
- emit exactly one overall width, height and depth label;
- use semantic region/lane metadata;
- avoid label collisions.

The authored internal-front view remains `authored-internal-layout` and is not promoted to Scene Core geometry.

### Module 04

The refrigerator-side panel remains a panel, not a cabinet. Its isometric overall dimensions are `2400 × 600 × 18 mm`, each exactly once. The 18 mm dimension is deliberately used as a stress case: label placement must not depend on the projected guide being visually long.

## Known limits

This slice does not implement complete hidden-line removal, CAD-style sectioning, automatic internal-layout inference or a general constraint solver.

The next evolution can add region occupancy from projected features/edges and richer dimension priorities without changing the semantic identity/provenance model introduced here.
