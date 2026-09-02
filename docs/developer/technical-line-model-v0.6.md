# Technical Line Model v0.6

## Objective

Separate projected physical edge existence from the lines that are intentionally represented on a technical drawing.

The v0.4 edge constitution correctly made box topology explicit, but the SVG renderer then treated every projected physical edge as ink. On modules with multiple 18 mm fronts this produced duplicated front/rear perimeters, non-silhouette depth connectors and rear-plane lines that visually collapsed into a wireframe.

This slice introduces a derived representation boundary without claiming complete hidden-line removal.

## Authority

- physical geometry: Scene Core;
- physical topology and projected edge provenance: `technical-edge-graph.ts`;
- isometric projection: `technical-isometric.ts` / `isometric-projection/v0.5`;
- technical line selection: `technical-line-model.ts` / `technical-line-model/v0.6`;
- SVG: derived representation only.

`CompiledTechnicalViewGeometry.edges` remains the complete projected physical edge graph. The line model consumes that graph and does not mutate or replace physical authority.

## Pipeline

```text
Scene Core geometry
        |
        v
Physical projected edge graph
        |
        v
Technical line candidates
        |
        v
Rendered technical lines
        |
        v
SVG
```

A later occlusion slice may insert a visibility resolver between candidates and final visible lines. v0.6 deliberately does not pretend that this resolver already exists.

## Selection policy

| Physical edge class / context | Disposition | Reason |
| --- | --- | --- |
| `silhouette` | draw | `silhouette` |
| `front` | draw | `front-datum` |
| `shared` | draw | `shared-boundary` |
| `internal`, non-front primitive | draw | `planar-detail` |
| `internal`, source role includes `front` | omit | `front-thickness-rear` |
| `back` | omit | `rear-plane` |
| `depth` | omit | `non-silhouette-depth` |

The edge graph classifies silhouette first. Therefore a depth-oriented edge that actually belongs to the outer projected contour survives as `silhouette`; only non-silhouette depth connectors are omitted.

Front primitives are physical 18 mm boxes. Their front-datum perimeter is retained while the internal rear perimeter is omitted, preventing a door or drawer front from being drawn twice merely because it has thickness.

## Observable contract

Geometry-derived isometric SVGs declare both source and representation counts:

- `data-technical-edge-count`: complete projected physical edges;
- `data-technical-line-count`: lines selected for drawing;
- `data-isometric-constitution="isometric-projection/v0.5"`;
- `data-technical-line-constitution="technical-line-model/v0.6"`.

Rendered geometry uses `data-role="technical-line"` and keeps the physical source edge id/provenance as metadata. A physical edge is therefore no longer synonymous with a rendered SVG line.

## Gates

### Synthetic box

- physical topology remains 12 edges;
- technical representation selects 8 lines;
- no rendered line has physical class `back` or `depth`.

### Module 03

- the physical edge graph is preserved;
- the rendered line set is less than half the physical edge count;
- drawer and door provenance remains represented;
- rear planes, non-silhouette depth connectors and rear perimeters of front-thickness boxes are explicitly omitted;
- dimensions remain unique and unchanged.

### Module 04

- remains a generic thin-panel fixture using the same policy;
- physical topology remains 12 edges;
- technical representation selects 8 lines.

## Deliberate non-goals

This slice does not implement:

- cross-primitive occlusion;
- segment clipping against projected faces;
- dashed CAD hidden lines;
- collinear projected-segment merging;
- z-buffer or raster-derived visibility;
- changes to Scene Core geometry;
- changes to Technical Composition / Formator;
- changes to the fixed 3D viewer camera;
- appliance assets.

`hidden-line-removal` therefore remains an explicit omission in the technical presentation package.

## Follow-up

The next visibility slice can work from explicit technical line candidates rather than rediscovering physical topology:

```text
PhysicalEdge
  -> TechnicalLineCandidate
  -> OcclusionResolver
  -> VisibleTechnicalLine
```

That keeps physical authority, representation policy and visibility reasoning separately testable.
