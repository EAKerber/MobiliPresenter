# Environment Realism 0.2

Status: stacked opt-in implementation slice  
Base: `work/ui/surface-fidelity-v0.2`  
Scope: Viewer/UI presentation renderer  
Authority impact: none

## Objective

Make the existing presentation-only window explain the scene lighting more convincingly after Surface Fidelity 0.2 made wood, stone and other PBR responses more visible.

Environment Realism 0.1 proved the window/daylight infrastructure, but the canonical studio rig remained dominant:

- ambient relative intensity `0.32`;
- directional key resolves to `1.44` in Three;
- directional fill resolves to `0.48`;
- neutral PMREM environment `0.28`;
- window `RectAreaLight` intensity `58`.

That makes the window visually useful but weak as a causal explanation for the scene lighting.

## Runtime policy

The slice remains behind the existing switch:

- default: canonical renderer unchanged;
- `?realism=1`: Environment Realism + Surface Fidelity + calibrated daylight balance;
- `?fidelity=1`: realism is suppressed by the existing composition policy.

No new query flag or product configuration authority is introduced.

## Lighting calibration

Only in realism mode:

- window `RectAreaLight`: `58 -> 76`;
- ambient studio support: `x0.78`;
- canonical directional key: calibrated as the shadow-producing proxy for the window direction;
- lateral studio fill: `x0.62`;
- PMREM reflection/environment contribution: `x1.12`;
- renderer exposure remains exactly `1.0`.

The goal is not to make the frame brighter. It is to move the causal balance from `studio rig + decorative window` toward `window-motivated key + restrained studio support`.

### Shadow direction

Three.js `RectAreaLight` does not cast shadows. Rather than adding another shadow authority, the existing `key-front-high` directional light remains the sole base shadow caster and is repositioned only in realism mode to an inferred external source point aligned with the laundry window.

This is presentation-only lighting direction. It does not assert a physical sun position, building orientation or architectural fact.

The window area light remains the soft local daylight contribution while the existing directional key provides coherent shadow direction.

## Runtime sync

`syncRuntimeLighting` restores canonical light intensity/color whenever a lighting preset or full configuration reset is applied.

Therefore the realism calibration is deliberately reapplied immediately after that canonical sync. This preserves the layering rule:

1. canonical Appearance lighting remains authority;
2. runtime sync restores it;
3. Environment Realism applies a derived presentation calibration;
4. no canonical policy is rewritten.

## Preserved invariants

This slice does not change:

- Scene Core geometry or schemas;
- fixed camera or PresentationFrame;
- module/appliance dimensions or placement;
- appliance fit/envelopes;
- TPC/public UI contracts;
- CSS/layout or `viewer-next/src/ui/**`;
- renderer tone-mapping exposure;
- production Netlify branch;
- `main`.

The existing window geometry and 0.70 mm tile face/grout relief are retained.

## Validation

Required automated evidence:

1. Environment Realism still leaves `sceneGeometryDigest` unchanged.
2. Window daylight remains a real `RectAreaLight` and is raised to the v0.2 intensity.
3. Studio ambient/key/fill calibration matches the declared bounded scales.
4. The key remains the existing shadow caster, but its presentation direction is aligned with the window source.
5. Environment intensity is a bounded multiplier over the canonical Appearance value.
6. Calibration can be reapplied after canonical lighting sync resets light state.
7. Product UI Evidence remains green for responsive shell and stage navigation.
8. Existing captures `environment-realism-1366x768` and `surface-fidelity-wood-1366x768` are reviewed on the final head.
9. Viewer Next is classified independently from the inherited Chrome DevTools `Runtime.evaluate` timeout.

## Visual acceptance

Accept when:

- window-side lighting has a more plausible direction without obvious theatrical spotlighting;
- warm under-cab lighting remains visibly distinct;
- neutral MDF is not washed out;
- wood retains readable grain and PBR response;
- inox/glass do not clip;
- the frame is not globally brighter merely to signal realism;
- fixed framing remains unchanged.

If a stronger realism jump requires additional objects, richer appliance geometry or HDRI/image-based environment content, those belong to later Scene Dressing / Appliance Visual Skin slices rather than further overdriving this lighting calibration.