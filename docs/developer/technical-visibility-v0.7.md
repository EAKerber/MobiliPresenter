# Technical Visibility v0.7

## Objective

Introduce an explicit geometric visibility stage for geometry-derived technical isometric drawings.

R1 repaired the projection kernel. R2 separated the complete physical edge graph from the smaller technical-line representation. R2.1 fixed the semantic camera hemisphere so the furniture front is actually observed from the front and above. The remaining artifact is different: a line can be meaningful to the technical representation and still be hidden by a nearer physical surface.

R3 makes that distinction explicit instead of adding another role/class filter.

## Pipeline

The authority chain becomes:

```text
Scene Core geometry
    -> physical primitive topology
    -> isometric projection + view depth
    -> physical projected edge graph
    -> surface visibility intervals
    -> technical-line selection
    -> visible technical segments
    -> SVG
```

`technical-edge-graph.ts` remains the physical topology/provenance boundary. `technical-visibility.ts` owns occlusion. `technical-line-model.ts` keeps the R2 semantic selection policy and consumes the visibility evidence only after that selection.

## Visibility model

The technical camera remains the R2.1 orthographic isometric camera. `isometricViewDepth(point)` is the ordering authority: larger values are closer to the virtual camera.

Each primitive topology now exposes its boundary faces in addition to vertices and edges. A face is projected into the same technical 2D plane as the edge graph, while each projected face vertex retains view depth.

For every physical edge:

1. start/end projected coordinates and start/end view depth are retained;
2. projected intersections with all face boundaries become parametric breakpoints on the edge (`t` in `[0, 1]`);
3. each interval between breakpoints is tested at its midpoint;
4. face depth at that projected point is recovered by affine interpolation over the projected planar face;
5. an interval is hidden only when a surface is strictly nearer than the edge by the depth tolerance;
6. adjacent visible intervals are merged deterministically.

The result is visibility evidence on the physical edge, not destructive rewriting of the physical graph.

## Representation boundary

The R2 line-selection constitution remains `technical-line-model/v0.6`: silhouette/front/shared/planar-detail selection has not been redefined in this slice.

R3 adds the separate `technical-visibility/v0.1` contract. The line model reports that visibility contract and converts selected edges into zero, one, or multiple visible segments according to their visibility intervals.

This distinction is intentional:

- physical edge count answers what topology exists;
- R2 semantic selection answers what lines are technically meaningful;
- R3 visibility answers which portions of those lines can actually be seen from the canonical technical camera.

## Package evolution

`TechnicalPresentationPackage` advances from `0.1.4` to `0.1.5` because projected physical edges now carry serialized visibility evidence:

- `startViewDepth`;
- `endViewDepth`;
- `visibleIntervals`.

The added fields are derived from Scene Core geometry and the canonical technical camera. They are not a second physical authority.

## Structural gates

R3 must prove independently that:

- a line behind a nearer opaque face is fully hidden;
- the equivalent line in front of that face remains fully visible;
- partial overlap produces stable split intervals rather than dropping the whole edge;
- the line model turns split intervals into split visible technical segments;
- module 03 contains real occlusion/clipping evidence;
- module 03 still preserves drawer/door provenance after visibility is applied;
- the R1 equal-foreshortening and R2.1 camera-orientation gates remain green;
- module 04 remains the generic thin-panel stress case;
- dimensions remain unique and Technical Composition remains unchanged.

## Conservative scope

This slice intentionally keeps `hidden-line-removal` in the presentation omission list.

That is not because no hidden lines are removed. R3 now performs real surface-depth clipping for the selected technical lines. The omission remains until the solver is qualified across the full primitive/overlap space and the older R2 back/depth suppressions can be reconsidered without relying on them as a safety net.

A later qualification slice may promote visibility from partial/conservative coverage to complete hidden-line removal and then remove that omission.

## Non-goals

R3 does not:

- modify Scene Core geometry;
- modify the calibrated perspective viewer camera;
- change the canonical technical-isometric orientation;
- alter Technical Composition/Formator dimension placement;
- introduce dashed hidden lines;
- infer hardware or appliance geometry;
- merge collinear visible segments;
- remove the legacy schematic-envelope renderer;
- claim complete hidden-line removal.

## Follow-up

After R3 is visually qualified, inspect whether the R2 `rear-plane` and `non-silhouette-depth` suppressions are still necessary. If visibility can become the sole geometric authority for occlusion, those heuristics should be reduced or removed rather than accumulated indefinitely.
