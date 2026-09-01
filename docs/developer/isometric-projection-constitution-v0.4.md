# Isometric Projection Constitution v0.4

## Objective

Make the geometry-derived isometric view obey one explicit projection convention and render a complete technical edge constitution without reintroducing schematic boxes or a second geometry authority.

This slice follows the Scene Core coordinate contract:

- `x`: right
- `y`: depth
- `z`: up
- right-handed

The frontal datum is the minimum physical `y` represented by the selected primitive set. Positive Scene Core depth must recede from that datum in the technical isometric projection.

## Canonical projection basis

Projection coordinates use a technical `verticalMm` axis that points upward. The SVG renderer later maps that value into screen Y by inversion.

The canonical basis is:

- width: `(horizontal +1.00, vertical -0.28)`
- depth: `(horizontal -0.62, vertical +0.28)`
- height: `(horizontal 0.00, vertical +1.00)`

Therefore positive depth moves left and upward on the final SVG. The back plane visually recedes from the frontal datum instead of advancing toward the observer.

`technical-isometric.ts` is the only formula authority for this projection. Geometry polygons, openings, dimension guides, the edge graph, and the schematic fallback consume the same basis.

## Technical edge graph

`technical-edge-graph.ts` derives line constitution from authoritative `GeometryPrimitive` values before projection.

Topology rules:

- box: 8 physical vertices, 12 physical edges;
- face: 4 physical vertices, 4 physical perimeter edges;
- local transforms are applied in millimeters before edge normalization;
- physically identical edges are deduplicated by canonicalized 3D endpoints;
- source primitive IDs and roles remain attached as provenance.

Projected edges are classified as:

- `back`
- `depth`
- `shared`
- `internal`
- `front`
- `silhouette`

The renderer uses that order, with front and silhouette lines composed last. Classification is presentation metadata derived from physical geometry; it is not a new physical authority.

## Rendering ownership

Geometry-derived orthographic views keep their existing projected-polygon renderer.

Geometry-derived isometric views render the compiled edge graph instead of restroking convex primitive polygons. The SVG declares:

- `data-technical-composition="technical-composition/v0.3"`
- `data-isometric-constitution="isometric-projection/v0.4"`

Dimension composition remains owned by Formator v0.3. v0.4 only changes the shared projected anchors by correcting the canonical basis.

## Module 03 gate

Module 03 is the primary orientation fixture because its physical front primitives make front/back inversion observable.

The gate requires:

- the depth dimension guide recedes in the canonical direction;
- real drawer and door primitive provenance survives into the edge graph;
- front, depth, and silhouette classes exist;
- projected edge identities are unique;
- the isometric SVG uses technical edges, not `primary-geometry` polygons;
- overall dimensions `1200`, `760`, and `530` remain unique;
- `hardware` and `hidden-line-removal` remain declared omissions.

The authored `390 / 400 / 400` internal layout remains separate technical-catalog data and is not promoted to Scene Core geometry.

## Module 04 gate

Module 04 remains a generic stress fixture, not a special renderer.

Scene Core currently represents it as one physical box primitive with geometry `18 × 2400 × 610 mm` and nominal presentation dimensions `18 × 2400 × 600 mm`. The generic topology must therefore compile exactly 12 unique physical edges while the existing nominal dimension policy continues to display `18 / 2400 / 600`.

No projector, edge compiler, or renderer branch is allowed to depend on module 04 identity.

## Explicit limits

v0.4 does **not** implement:

- hidden-line removal;
- dashed hidden edges;
- sections or cuts;
- inferred internal dimensions;
- new dimension-region heuristics;
- free camera or 3D navigation;
- module-specific isometric renderers.

`hidden-line-removal` remains an explicit omission until a separate slice defines visibility policy and gates.

## Gates

The slice is considered structurally valid when:

- positive Scene Core depth recedes under the canonical basis;
- a synthetic box compiles to 12 unique edges;
- a synthetic face compiles to 4 perimeter edges;
- module 03 passes orientation, provenance, edge uniqueness, and dimension regression gates;
- module 04 passes the same generic pipeline with 12 edges;
- existing technical drawing tests remain green;
- Viewer Next build/test/browser regressions remain green.
