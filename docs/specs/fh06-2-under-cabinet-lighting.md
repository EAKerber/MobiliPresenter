# FH-06.2 — Under-cabinet corner lighting specification

Status: **design-default / renderer contract**  
Branch: `renderer/fixed-view-realistic-v1`  
Purpose: freeze a stable visual and semantic representation for the under-cabinet linear light without pretending that the final construction profile has already been selected.

## 1. User visual decision

Use the **rear corner-mounted profile** shown in the supplied references as the visual base.

The exact commercial extrusion is intentionally unspecified. The renderer family represents a plausible 45-degree aluminum corner profile with opal diffuser; future project data may replace the specific cross-section without changing the light-run contract.

## 2. Current source evidence

Current scene already contains one under-cabinet accessory hosted by module 06:
- entity: `scene/traditional/accessory/under-cab-led-06`;
- definition: `ACC-UNDERCAB-LED-01`;
- host: module 06;
- source evidence: `Promob DXF LAYER115`;
- source/placement envelope: approximately `1200 x 40.91 x 32.02 mm`.

This source envelope remains useful for run extent and placement. It **does not force the visual extrusion to be a 40.91 x 32.02 rectangular box**.

## 3. Stable visual profile

Definition family: `LIGHT-PROFILE-CORNER-45-01`.

Design defaults:
- mounting class: surface-mounted rear corner;
- optical orientation: `45°` down-and-forward toward the worktop;
- housing: anodized/matte aluminum;
- diffuser: opal white;
- visible light must read as a continuous line, without exposed LED dots;
- nominal visual housing cross-section: approximately `18 x 18 mm` inside the larger Promob placement envelope;
- housing and diffuser are appearance geometry; the Promob source envelope remains placement/provenance evidence.

The 18 x 18 mm cross-section is a project design default, not an asserted construction dimension.

## 4. LED archetype

Stable renderer archetype:
- supply class: `24 V DC`;
- strip width class: `8 mm`;
- LED technology: high-density / COB-like continuous strip;
- correlated color temperature: `3000 K`;
- color rendering: `CRI > 90`;
- nominal luminous flux archetype: approximately `1000 lm/m`;
- nominal electrical power archetype: approximately `11 W/m`;
- dimmable by policy.

These electrical/photometric numbers are used only as a stable authoring archetype. The renderer may continue using normalized intensity until a photometric renderer contract is introduced.

## 5. Scene ownership and extent

Current scene:
- the main linear run is hosted by **module 06**;
- it spans the module 06 underside, near the rear tiled wall;
- it does not become a wall-owned entity;
- hood task LEDs under module 05 remain a separate emitter family;
- no strip is added under module 07/fridge upper or module 01/laundry by default unless explicit scene evidence is later supplied.

Future scenes may instantiate the same profile family under other upper modules.

If adjacent hosts later carry the same light-run family, each segment remains separately owned but their optical run should visually join with only a minimal seam; renderer/UI may group them as one linked `LightingRun` without losing host ownership.

## 6. Position and direction contract

The profile is mounted at the **rear junction between the underside of the upper cabinet and the tiled wall**, not near the front edge.

Optical axis:
- approximately the 45-degree bisector between vertical-down and cabinet-front directions;
- illuminates countertop/upstand/sink region;
- must not point straight down as the current generic emitter effectively does.

The light source must interact with stone, stainless sink/faucet and tiled wall through the normal renderer lighting path. Bloom remains a restrained post-effect on the diffuser/emissive surface only.

## 7. Acceptance

Hard:
- host ownership remains module 06 for the current run;
- hiding module 06 hides its light segment and semantic emitter;
- light geometry and lighting changes never mutate module geometry/camera;
- profile placement remains within the Promob LAYER115 placement envelope;
- F0-F4 remain PASS.

Visual:
- profile reads as a rear-corner extrusion, not a floating luminous rectangle;
- no discrete LED dots are visible at canonical viewport;
- emitted line is warm-neutral `~3000 K`, not orange decorative glow;
- worktop/upstand receive a continuous soft wash;
- sink/faucet metal receives believable local highlights;
- tiled wall immediately behind the worktop receives some illumination without flattening the full-wall tile material;
- light does not need excessive bloom to be visible.

## 8. Implementation change from current state

Current appearance definition uses:
- `3200 K`;
- generic line emitter;
- essentially downward local direction;
- rectangular accessory proxy from LAYER115.

FH-06.2 implementation should therefore:
1. preserve the confirmed LAYER115 run placement/width;
2. replace the rectangular proxy with a corner-profile housing + opal diffuser;
3. change the semantic emitter to `3000 K`;
4. aim it down-and-forward at approximately 45 degrees;
5. keep hood LEDs independent;
6. add fidelity probes for profile start/end, diffuser line and projected light run.

## 9. External archetype notes

- LEDVANCE professional COB strip families provide a plausible reference class around `24 V`, `8 mm`, `3000 K`, `CRI > 90`, and roughly `1000 lm/m` / `11 W/m`.
- Häfele Loox profile systems demonstrate aluminum housings with opal diffusers sized for narrow LED strips and explicitly use profiles for diffuse distribution, protection and heat management.

These products are references for plausibility only; no commercial product identity is asserted by the renderer.
