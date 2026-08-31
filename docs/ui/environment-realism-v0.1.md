# Environment Realism 0.1

Status: opt-in implementation slice derived from the current Netlify production branch.

## Baseline

The slice is based on:

- Netlify site: `mobilipresenter`
- production branch: `work/ui/netlify-guided-configurator-current`
- exact production commit: `35b1bc915dc1c2045e16c3441ec51963d127fb3c`
- production deploy: `6a95cf4e1ecdc100084456d2` (`ready`)

Observed baseline gate state on that exact commit:

- Coordination Guard: PASS
- Module Thumbnails: PASS
- Product UI Evidence: PASS
- Viewer Next: build/verify PASS, but the Browser WebGL baseline step failed/timed out

The WebGL failure predates this slice. It is not treated as green or waived; fresh PR CI must determine whether it is transient or reproducible before any promotion.

## Intent

Raise scene realism toward the supplied catalog-render reference without weakening fixed-camera, metric or semantic authority.

This slice deliberately targets the environment first because it improves the whole scene while keeping appliance geometry out of scope.

## Activation

Environment Realism 0.1 is opt-in:

```text
?realism=1
```

`fidelity=1` always suppresses the experimental realism mode so canonical fidelity baselines remain isolated.

No production-default behavior changes in this slice.

## Implemented surface

### Presentation-only daylight window

A renderer-owned presentation group adds:

- a left-side wall extension outside the authoritative Scene Core envelope;
- an inferred window opening with frame, mullion, glass and sill;
- a simple outdoor sky/greenery backdrop;
- a 6200 K `RectAreaLight` aligned with the window.

The group is explicitly marked:

- `appearanceOnly = true`
- `presentationInferred = true`
- `realismId = window-daylight-relief-v1`

This geometry is not a technical fact and must never be used for dimensions, module placement, BOM, installation or Scene Core derivation.

### Recessed tile micro-relief

The existing wall-tile renderer gains an opt-in micro-relief mode.

Instead of introducing a raster height/displacement map in 0.1:

- grout becomes the backing plane;
- individual tile faces sit `0.70 mm` proud of the grout;
- the existing 400 mm world-phase grid and 2 mm grout contract remain unchanged.

This creates real edge/shadow response while keeping the relief sub-millimetric and appearance-only.

The legacy flat tile path remains the default and is byte-for-byte behaviorally available when `realism=1` is absent.

## PBR / height-map decision

The current renderer already uses physically based materials, PMREM environment lighting, anisotropic brushed metal and procedural material response.

Therefore 0.1 does **not** add height maps indiscriminately.

Policy for this slice:

- geometric displacement is allowed only for bounded appearance-only micro-relief where it cannot redefine measured geometry;
- future normal/roughness maps are preferred for MDF, stone, ceramic and appliance skins;
- full displacement must not become a hidden second source of physical dimensions;
- external GLB/PBR appliance skins remain a later slice and must fit existing authoritative appliance envelopes.

## Boundaries

This slice does not change:

- Scene Core packages or schemas;
- camera or fixed-frame policy;
- module/appliance dimensions;
- appliance placement or fit;
- TPC/public UI contracts;
- ProjectState, Work, Coordination or publication state;
- production branch or `main`.

No decorative object layer is added yet; scene dressing remains a separate follow-up so the window/lighting effect can be evaluated cleanly.

## Validation

Required automated evidence:

1. `sceneGeometryDigest(currentSceneBase)` is unchanged after applying Environment Realism.
2. The presentation window root is idempotent.
3. The daylight source is a real `RectAreaLight` with explicit 6200 K metadata.
4. Legacy wall tiling remains available.
5. Opt-in relief is positive and below 1 mm.
6. Product UI Evidence captures a 1366x768 canvas from `?controls=1&realism=1`.
7. Existing non-realism product UI evidence remains green.
8. Viewer Next must be read back independently; any repeated Browser WebGL failure must be classified before promotion.

## Leeway / correction policy

If visual evidence shows the window outside the useful fixed frame, excess exposure or too-strong relief, the implementation may tune only:

- presentation-only window dimensions/placement;
- daylight color/intensity;
- sub-mm relief amount/material response.

It must **not** fix the experiment by changing the authoritative camera, Scene Core geometry or module placement.

If the inherited Browser WebGL failure reproduces, diagnose that failure as a separate baseline blocker rather than weakening its gate.

## Promotion gate

Environment Realism 0.1 is eligible to become product-default only after:

- fresh CI is green or the inherited baseline failure is independently resolved;
- the realism capture is visually reviewed;
- no fixed-frame/readability regression is accepted silently.

Promotion is a separate mutation.

## Likely successor

After this environmental baseline is judged useful:

1. Surface Microdetail 0.2 — restrained normal/roughness response for stone, MDF and ceramic;
2. Scene Dressing 0.1 — sparse presentation-only countertop/laundry props;
3. Appliance Visual Skins 0.1 — GLB/PBR skins fitted to the existing appliance authority envelopes, retaining parametric proxies as fallback.
