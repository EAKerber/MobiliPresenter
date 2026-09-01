# Isometric Projection Kernel v0.5

## Objective

Repair the projection regression introduced by the v0.4 depth-sign correction without mixing projection work with line visibility.

The technical isometric projection must be derived from one geometric camera frame. Independent tuning of width/depth/height screen vectors is no longer an acceptable authority.

This slice intentionally leaves the v0.4 physical edge constitution in place. Hidden-line removal and technical-line selection belong to the next slice.

## Regression biopsy

v0.4 authored the projected basis directly:

- width: `(1.00, -0.28)`
- depth: `(-0.62, +0.28)`
- height: `(0.00, +1.00)`

Width and depth became almost antiparallel. Their projected angle was about 171 degrees and their normalized parallelogram area was about 0.15. The view therefore flattened the physical width/depth plane before the edge renderer drew the complete physical wireframe.

The previous formula was also heuristic. Reversing the v0.4 sign would reduce the regression but would restore another non-isometric basis instead of fixing the authority.

## Canonical frame

Scene Core remains right-handed:

- `x`: width/right;
- `y`: depth;
- `z`: up.

v0.5 derives projection from:

- view direction: normalized `(1, 1, 1)`;
- screen right: normalized `(1, -1, 0)`;
- screen up: `screenRight × viewDirection`;
- one uniform drawing scale: `sqrt(3 / 2)`.

The resulting unit-axis basis is derived, not authored:

- width: approximately `( +0.866025, -0.5 )`;
- depth: approximately `( -0.866025, -0.5 )`;
- height: `( 0, +1 )`.

All three Scene Core axes therefore have projected length `1` per millimeter. Width/depth normalized projected area is `sqrt(3)/2`, so the horizontal physical plane cannot collapse into the near-collinear v0.4 configuration.

Projection coordinates remain technical vertical-up. SVG screen-Y inversion remains owned by the renderer.

## Authority

`technical-isometric.ts` remains the only projection authority.

The authoritative object is now `ISOMETRIC_PROJECTION_FRAME`. `ISOMETRIC_PROJECTION_BASIS` is a derived diagnostic/consumer representation.

`isometricDepthRecedes()` is removed because a single sign check cannot establish projection correctness.

## Structural gates

The kernel must prove:

- view direction, screen-right and screen-up are unit vectors;
- the three frame vectors are mutually orthogonal where required by the camera plane;
- width, depth and height have equal projected scale;
- width/depth projected area stays non-degenerate;
- projection remains linear;
- module 03 preserves a non-degenerate width/depth frame;
- module 04 remains valid on the same generic projection;
- technical edge provenance and dimension uniqueness remain intact.

The old quadrant-only gate is insufficient and is replaced rather than relaxed.

## Deliberate non-goals

This slice does not:

- remove hidden lines;
- suppress internal/back physical edges;
- merge collinear projected line segments;
- change `technical-edge-graph.ts` topology;
- change Scene Core geometry;
- change Technical Composition / Formator lane policy;
- change the fixed 3D viewer camera;
- add appliance assets.

The module 03 SVG may therefore remain visually busier than the desired final technical drawing. R1 succeeds when spatial projection is mathematically coherent; technical-line visibility is the responsibility of the next slice.

## Follow-up

The next slice should introduce an explicit boundary:

`PhysicalEdge -> ProjectedEdge -> TechnicalLineCandidate -> VisibleTechnicalLine`

so physical topology no longer maps directly to every line rendered on paper.
