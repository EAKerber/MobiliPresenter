# Surface Fidelity 0.2

Status: implementation slice, stacked on Environment Realism 0.1  
Base: `work/ui/environment-realism-v0.1-r2`  
Scope owner: Viewer/UI presentation renderer  
Authority impact: none

## Objective

Increase perceived material realism without changing physical geometry, fixed camera policy, Scene Core authority, TPC semantics, module placement or appliance envelopes.

The P0 problem is the current `front-wood` response. It already has deterministic module-continuous procedural grain in physical millimeter coordinates, but the visible variation is mainly diffuse-color modulation and is too weak to read as wood at the canonical fixed frame.

Surface Fidelity 0.2 preserves that deterministic mapping and upgrades only the opt-in realism profile.

## Runtime policy

Surface Fidelity is enabled by the existing Environment Realism switch:

- default: legacy material response;
- `?realism=1`: window/daylight + tile micro-relief + Surface Fidelity;
- `?fidelity=1`: realism remains suppressed by the existing composition policy.

No new query parameter or product configuration concept is introduced.

The material registry receives the already-resolved `environmentRealism` boolean from `ViewerComposition`; it does not independently parse browser state.

## Wood v3

Legacy profile remains:

`module-mm-world-z-v2`

The opt-in profile is:

`module-mm-world-z-v3`

Both retain:

- `front-wood` material identity;
- `mappingPolicy=module-continuous`;
- `grainDirection=world-z`;
- `physicalTextureScaleMm`;
- module-local reset of cross-grain mapping;
- no raster texture dependency.

The v3 field combines:

1. low-frequency macro variation;
2. warped medium fiber bands;
3. fine variation;
4. a smaller pore-scale field.

The same deterministic field influences three visual channels:

- base-color/tone variation;
- bounded roughness variation;
- subtle derivative-based micro-normal perturbation.

No vertices move. The micro-normal is a shading response only.

## Stone v2

Legacy world-space millimeter speckle remains available unchanged.

When Surface Fidelity is enabled, `stone-speckled-*` keeps the same color speckle and physical world mapping while adding a bounded roughness delta from the existing deterministic coarse/fine fields.

No normal map, displacement map or raster texture is added in this slice.

## Ceramic

Environment Realism 0.1 already gives tile faces and grout separate roughness values and a bounded physical face/grout offset of `0.70 mm`.

Surface Fidelity 0.2 intentionally does not add a second ceramic shader. The combination of:

- recessed grout;
- tile/grout roughness separation;
- daylight;

is retained as the ceramic baseline until visual evidence demonstrates a real need for another layer.

## Neutral solid MDF

Solid neutral furniture finishes are deliberately not reinterpreted as wood.

The enhanced registry does not apply procedural wood grain to `front-primary`; the visual distinction between a solid MDF finish and the `warm-wood` finish remains explicit.

## Invariants

This slice must not change:

- Scene Core geometry;
- `sceneGeometryDigest`;
- camera transform or projection;
- fixed-frame behavior;
- entity placement;
- hardware anchors;
- appliance fit/envelopes;
- ownership/picking semantics;
- public UI/TPC contracts;
- `main`;
- Netlify production branch.

Surface Fidelity is presentation-only derived appearance.

## Tests

Focused structural coverage verifies:

- legacy wood remains v2 when Surface Fidelity is off;
- v3 preserves metric/module-continuous mapping metadata;
- v3 adds albedo, roughness and micro-normal shader paths;
- wood uses no raster `map`, `roughnessMap` or `normalMap`;
- stone v2 adds roughness while keeping world-mm speckle;
- neutral `front-primary` receives no wood grain;
- material mapping bindings follow the active shader version rather than a hard-coded legacy version.

Existing Viewer Next tests continue to protect geometry, interaction, fit, camera and renderer invariants.

## Visual evidence

Product UI Evidence adds a canonical 1366×768 capture:

`surface-fidelity-wood-1366x768.png`

The capture uses:

`?controls=1&realism=1&front=03:warm-wood`

This intentionally exercises the real product/runtime path and makes the lower sink module use the wood finish while keeping the fixed camera.

Review criteria:

- wood is recognizable without zoom;
- macro variation does not become blotchy;
- medium fibers do not look periodic;
- specular/roughness response follows the grain;
- micro-normal does not create carved/displaced-looking geometry;
- door/drawer readability is not reduced;
- stone remains secondary to cabinetry.

## Promotion policy

Do not make the realism profile default from this slice alone.

Promotion requires:

1. focused tests and build pass;
2. Product UI Evidence pass;
3. canonical Surface Fidelity screenshot reviewed;
4. Viewer Next result classified independently;
5. no geometry/camera/ownership regression;
6. explicit decision to promote the stacked realism profile.

The pre-existing Chrome DevTools `Runtime.evaluate` timeout in the Viewer Next harness is not relaxed or hidden by this slice.
