# Technical Visibility v0.7 — architecture revision

## Objective

Repair the technical-isometric line pipeline without accumulating module-specific
filters or post-render cleanup rules.

R1 repaired projection. R2 introduced a smaller technical-line representation.
R2.1 fixed the camera hemisphere. The first R3 implementation added real
surface-depth clipping, but visual review of modules 03 and 06 exposed two
different facts that must not be conflated:

1. module 03 is physically less complete in Scene Core than module 06;
2. the R2 line-selection policy still used world-axis/depth heuristics as if
   they were visibility semantics.

This revision corrects the second problem and explicitly refuses to hide the
first one inside presentation code.

## Source-geometry finding

Module 06 has a comparatively complete modeled carcass: left/right sides,
bottom, top, divider, shelves and fronts.

Module 03 does not. Its current Scene Core geometry contains:

- drawer base;
- drawer left side;
- drawer right side;
- right base;
- four drawer fronts;
- center door;
- right door.

There is no modeled complete center/right carcass, top or equivalent set of
structural members in the current authority.

Therefore a geometry-derived technical isometric cannot truthfully "complete"
module 03 by inventing those missing members. Any future completion must happen
either:

- upstream in Scene Core from authoritative source evidence; or
- as an explicitly authored/schematic representation with different fidelity.

The presentation layer must not synthesize cabinet structure merely because a
bounding envelope exists.

## Architecture correction

The earlier R2 policy classified physical edges as:

- `front`;
- `back`;
- `depth`;
- `internal`;
- `shared`;
- `silhouette`.

That mixed three different concepts:

- world-axis direction (`depth`);
- position in the module envelope (`front` / `back`);
- drawing semantics (`silhouette` / `shared`).

The most harmful consequence was treating every non-silhouette edge parallel
to depth as dispensable. That happens to look acceptable on simple solids, but
it removes legitimate creases/boundaries from compound furniture.

R3 replaces that classification with camera-relative topology semantics:

- `silhouette` — incident faces transition between camera-facing and
  away/edge-on;
- `crease` — two or more incident faces are camera-facing;
- `boundary` — a camera-facing surface boundary has one incident face;
- `shared` — coincident physical boundary contributed by more than one
  primitive, with camera-facing support;
- `back-facing` — no incident surface faces the technical camera.

The classification is derived from primitive face normals and the gradient of
the canonical `viewDepth` function. It is not inferred from `x/y/z` edge
direction and no longer requires a projected convex-hull heuristic.

## Pipeline

The authority chain is now:

```text
Scene Core geometry
    -> primitive topology (vertices + edges + faces + outward normals)
    -> canonical isometric projection + view depth
    -> camera-relative physical edge semantics
    -> technical-line selection
    -> surface-depth visibility on selected lines only
    -> visible technical segments
    -> SVG
```

The important ordering rule is **selection before occlusion**.

Occlusion is no longer evaluated for physical edges that have already been
rejected as `back-facing`. Their absence of `visibleIntervals` means "not
evaluated", not "hidden".

This preserves a distinction among:

- physical topology exists;
- topology says the edge is a meaningful line candidate;
- geometry says part or all of that candidate is occluded.

## Visibility model

`technical-visibility/v0.1` remains the conservative depth solver introduced by
R3.

For each selected physical edge:

1. intersections with projected surface boundaries define parametric
   breakpoints;
2. each interval is tested at its midpoint;
3. face depth at the projected point is recovered by affine interpolation;
4. an interval is hidden only when another surface is strictly nearer than the
   line by the depth tolerance;
5. adjacent visible intervals are merged deterministically.

No minimum-length fragment filter is added in this revision.

If a short visible segment remains after the topology correction, it must be
diagnosed back to its source edge/surface relation before any cleanup policy is
considered.

## Render-style compatibility

Physical edge semantics and SVG style classes are now separate concepts.

The external `technical-line-model/v0.6` render-style contract remains stable:

- physical `silhouette` -> silhouette style;
- physical `crease` -> internal/detail style;
- physical `boundary` -> front/boundary style;
- physical `shared` -> shared style;
- physical `back-facing` -> omitted.

This avoids coupling topology vocabulary to stroke styling.

## Package evolution

`TechnicalPresentationPackage 0.1.5` remains the R3 package version.

Selected projected edges may carry `visibleIntervals`. The field is optional:

- present = visibility evaluated;
- absent = edge was not selected for visibility evaluation.

`startViewDepth` and `endViewDepth` remain derived camera-order evidence, not a
second physical authority.

## Structural gates

The revised R3 must prove:

1. a box still has all 12 physical edges;
2. a front-left-above isometric box selects 9 camera-meaningful edges and
   rejects the 3 fully back-facing edges;
3. selection is based on face incidence/orientation, not whether an edge runs
   along the Scene Core depth axis;
4. a selected line behind a nearer face is hidden;
5. a selected line in front is preserved;
6. partial occlusion splits the selected line deterministically, without a
   fragment-size cleanup heuristic;
7. only selected module-03 edges receive visibility evidence;
8. drawer/door provenance survives selection + clipping;
9. R1 projection and R2.1 camera invariants stay green;
10. module 04 remains the thin-panel topology stress fixture.

## Module 03 limitation

This revision may improve the coherence of module 03 by restoring legitimate
visible creases that R2 incorrectly discarded. It cannot make the modeled
cabinet structurally complete because those members do not currently exist in
Scene Core.

That is an upstream data/geometry question and must remain visible as such.

## Module 06 dimension note

The visually poor `400 mm` placement is a Technical Composition issue, not a
visibility issue.

`technical-composition/v0.3` currently checks the dimension **label box**
against an inflated rectangular geometry envelope. It does not evaluate the
dimension line/extension lines against actual projected technical geometry, and
its region normals are global layout directions rather than normals derived
from the dimension guide itself.

That will be handled in a separate composition slice after R3, generically. No
module-06-specific offset is introduced here.

Possible partial shelf-height dimensions are an authored/semantic enhancement
and are explicitly not part of this repair.

## Non-goals

R3 does not:

- invent missing module-03 carcass geometry;
- add a minimum rendered-segment length;
- special-case module IDs;
- adjust the `400 mm` dimension with a hard-coded offset;
- change Scene Core physical authority;
- change the calibrated perspective viewer camera;
- claim complete hidden-line removal;
- add authored shelf dimensions.

## Promotion rule

R3 is not promotable solely because CI is green.

It must first prove that the architectural replacement survives the full Viewer
Next suite and then be visually rechecked on at least modules 03 and 06. If
module 03 remains structurally incomplete after legitimate line semantics are
restored, that result is classified as source-geometry incompleteness rather
than another presentation defect.
