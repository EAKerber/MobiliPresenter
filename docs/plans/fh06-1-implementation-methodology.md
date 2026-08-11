# FH-06.1 — implementation methodology

Status: **planned / execution-ready**  
Branch: `renderer/fixed-view-realistic-v1`  
Depends on:
- `docs/specs/fh06-1-oven-stone-sink-faucet.md`
- `docs/specs/fh06-2-under-cabinet-lighting.md`
- `docs/plans/fidelity-harness-v1.md`

Purpose: implement oven surround, two-piece stone, rear upstand, realistic sink/faucet and corner under-cabinet lighting without using appearance to compensate for wrong geometry.

## 1. Method invariant

Every slice follows:

`observe -> contract -> implement -> unit/metric gate -> projection/readability gate -> browser artifact -> readback`

A slice is not accepted because a screenshot looks better. It must state which fidelity dimension it changes and which dimensions are forbidden to change.

Global invariants:
- fixed camera is unchanged;
- mm is physical/model authority;
- F0-F4 may not regress;
- FH-05 readability remains the F5 regression baseline until explicitly superseded;
- user-facing binaries are delivered only after CI materializes them on `tmp/fh06-user-artifacts` and GitHub readback confirms them;
- no decorative props are required for acceptance.

## 2. Representation boundary

### Scene Core owns

- module/entity identity and ownership;
- authoritative/inferred envelopes and transforms;
- module 02 front-opening semantics;
- explicit MDF surround primitives;
- STONE-02 / STONE-03 ownership and external envelope;
- rear-upstand entities/envelopes;
- sink slot/cutout bounds;
- faucet anchor;
- lighting accessory host/placement;
- substitution state module02 <-> freestanding range.

### Viewer owns deterministic visual recipes

- rounded/filleted sink bowl mesh;
- real stone mesh with hole generated from core cutout bounds;
- faucet swept-tube mesh;
- deterministic stone texture/roughness presets;
- tile material mapping;
- corner LED profile cross-section/diffuser;
- PBR/light interaction and selective bloom.

Rationale: metric facts remain renderer-independent; curved/high-detail meshes do not force the Scene Core 0.1 primitive schema to become a general CAD kernel.

## 3. Slice S1 — module 02 front-opening contract

Goal: eliminate the current ambiguity between the large internal cavity and the visible oven opening.

Implementation:
1. extend the appliance-slot contract with an optional renderer-independent `frontOpeningMm` / equivalent visual-fit envelope;
2. preserve the existing internal cavity dimensions as evidence;
3. set module 02 visible front opening to `600 x 600 mm`, centered in the `790 x 760 mm` facade;
4. add four explicit MDF surround primitives at the front plane:
   - left stile: 95 mm;
   - right stile: 95 mm;
   - top rail: 80 mm;
   - bottom rail: 80 mm;
   - panel material thickness: 18 mm;
5. oven physical front remains `596 x 596 mm` and uses contain/physical-size fitting inside the 600 x 600 opening;
6. never scale the oven to the 755 x 724 internal cavity.

Preferred frame construction:
- stiles run full facade height;
- top/bottom rails span only the 600 mm opening width between stiles;
- no overlapping duplicate front surfaces.

Hard gates:
- outer module envelope unchanged;
- opening exactly 600 x 600;
- 95/95/80/80 derived fields exact;
- oven front 596 x 596;
- replacement stove behavior unchanged;
- camera/projection landmarks unchanged outside module 02.

F5 probes:
- eight surround edges + oven four bounds.

Rollback boundary: one commit/slice; no stone/sink changes allowed in S1.

## 4. Slice S2 — stone ownership and dimensions

Goal: make the worktop an explicit two-piece assembly before adding sink detail.

Implementation:
1. preserve two semantic entities:
   - `STONE-02`, owner module 02;
   - `STONE-03`, owner module 03;
2. migrate visual slab thickness to the FH-06.1 design default `30 mm` because final physical stone was explicitly undecided; preserve Promob/DXF 36/18 mm observations as provenance, not silently delete them;
3. use authoritative X spans from current modules;
4. use stable target depth ~550 mm and 20 mm front overhang relative to the 530 mm cabinet where applicable;
5. seam occurs exactly at module boundary; no physical fake gap;
6. add one rear upstand per stone owner:
   - 100 mm high;
   - 20 mm deep;
   - same finish by default;
   - seam aligned with STONE-02/STONE-03 boundary.

Hard gates:
- stone ownership follows module visibility;
- combined X span unchanged;
- seam == module boundary;
- stone color changes do not change geometry digest;
- upstands disappear with their owner.

## 5. Slice S3 — deterministic stone finishes

Goal: establish the minimum three color options without changing geometry.

Presets:
- `stone-light-speckled`;
- `stone-warm-beige-speckled`;
- `stone-graphite-speckled`.

Method:
- generate a deterministic seeded procedural texture/roughness pair locally;
- physical texture scale is expressed in mm;
- use the same seed/pattern phase across STONE-02 and STONE-03 when linked so the result reads as one material family while retaining the real seam;
- no downloaded runtime texture is required for v1.

Hard gates:
- identical geometry/transforms across all three presets;
- stable hashes for generated maps given preset/version;
- no seam movement across presets.

## 6. Slice S4 — sink cutout and bowl

Goal: replace the rectangular proxy with a recognizable undermount stainless sink.

Core contract:
- definition `SINK-UNDERMOUNT-40X34-01`;
- 400 x 340 mm outer archetype;
- 170 mm bowl depth;
- rounded-rectangle cutout/anchor hosted by STONE-03;
- current scene placement continues to come from the confirmed sink slot where available.

Viewer method:
1. generate STONE-03 top geometry with `THREE.Shape` + hole path and `ExtrudeGeometry` (or equivalent deterministic polygon-with-hole extrusion), not CSG;
2. generate the sink rim/bowl parametrically from rounded rectangles and lofted/filleted sections;
3. create visible bowl depth and bottom transition;
4. place below the stone as undermount;
5. use brushed-inox PBR material.

Why polygon-with-hole instead of CSG:
- deterministic;
- simpler topology;
- easier tests;
- avoids Boolean robustness problems for a simple planar slab cutout.

Hard gates:
- cutout contained inside STONE-03;
- no stone exists through the bowl opening;
- bowl bounds = definition bounds within tolerance;
- no impossible intersections;
- sink visibility follows module03/stone ownership correctly.

F5/F6 probes:
- cutout four bounds;
- rim silhouette;
- deepest visible bowl region;
- human gate: immediately recognizable as an undermount stainless sink without props.

## 7. Slice S5 — faucet family and anchor

Goal: replace the cylinder proxy with a stable generic high-arc faucet.

Core:
- `FAUCET-HIGH-ARC-01`;
- host = STONE-03;
- stable local anchor behind/relative to sink;
- nominal height 340 mm;
- nominal reach 255 mm.

Viewer recipe:
- base/body primitive;
- smooth curve + `TubeGeometry` for high arc;
- separate nozzle/aerator;
- single lever/control;
- brushed stainless/chrome PBR;
- deterministic segment counts and radii.

Hard gates:
- base remains on deck/upstand-safe region;
- top landmark and reach satisfy definition tolerance;
- changing stone finish never changes faucet transform;
- hide/show module03 does not leave faucet orphaned.

F6 gate: faucet silhouette must read as a real kitchen faucet at 1865 x 967 without enlarging it beyond plausible dimensions.

## 8. Slice S6 — complete wall tile finish

Goal: fix the current local/faint backsplash treatment.

Method:
- tile is a wall material policy, not a central overlay mesh;
- cover all visible rear wall from laundry through kitchen and corresponding visible column/projection faces;
- generate deterministic warm off-white tile material;
- 400 x 400 mm module, 2 mm grout;
- add subtle normal/roughness contrast, not a dark drawn grid;
- derive UV/world-planar coordinates from world mm so scale remains physical and stable.

Hard gates:
- no effect on EnvironmentGeometry;
- tile scale is stable under viewport changes;
- cabinetry naturally occludes the wall;
- no abrupt material termination behind module boundaries unless geometry itself ends.

## 9. Slice S7 — corner under-cabinet profile

Goal: turn the current generic light block into a believable installed profile.

Core facts retained:
- placement/extent from Promob/DXF LAYER115 where available;
- ownership remains module-based;
- module 06 segment is confirmed; no unverified extra strip is invented.

Viewer method:
- corner-profile visual cross-section approximately 18 x 18 mm inside the source placement envelope;
- aluminum body + opal diffuser;
- continuous emissive surface;
- 3000 K semantic area/line light;
- direction approximately 45 degrees down/forward;
- selective bloom remains secondary, never the primary lighting mechanism.

Potential future abstraction:
- `LightingRun` can visually join adjacent hosted segments while each segment retains its host/visibility identity.

Hard gates:
- hiding host hides profile + emitter;
- light affects stone/upstand/sink/faucet/tile physically through the lighting pass;
- bloom disabled still leaves a plausible lit scene;
- no light leakage from a hidden segment.

## 10. Slice S8 — drawer/front readability

Only after S1-S7 pass.

Allowed tools:
- current <=1.25 mm visual bevel;
- contact shadow/AO refinement;
- PBR roughness separation;
- renderer supersampling/downsample tuning.

Forbidden shortcut:
- increasing physical drawer/door gaps solely to make them visible.

Acceptance:
- F5 targeted seam recall/contrast improves relative to FH-05;
- F1/F2 geometry does not change.

## 11. Test order for every slice

1. TypeScript strict build;
2. unit tests for new contract/recipe;
3. Scene Core `verify`;
4. F0-F4 fidelity report;
5. targeted F5 4x crops if affected;
6. Viewer Next browser WebGL smoke;
7. canonical 1865 x 967 screenshot;
8. artifact publication to `tmp/fh06-user-artifacts`;
9. GitHub readback of `LATEST.json`, PNG and manifest hash;
10. only then present the image to the user.

## 12. Commit / rollback sequence

Recommended isolated commits:
1. `scene: separate oven cavity from front opening`
2. `scene: add module02 MDF front surround`
3. `scene: formalize two-piece stone and rear upstands`
4. `viewer: add deterministic stone presets`
5. `viewer: generate stone cutout and parametric undermount sink`
6. `viewer: add deterministic high-arc faucet`
7. `viewer: apply complete wall tile material`
8. `viewer: implement corner under-cabinet profile`
9. `viewer: tune front readability without geometry drift`
10. `test: freeze FH-06.1 candidate and publish durable artifact`

A failed visual experiment should be revertible at its own commit without reverting the semantic/metric contracts that already passed.

## 13. Acceptance milestone

FH-06.1 is complete only when one candidate satisfies simultaneously:

- F0-F4 PASS;
- F5 no regression and targeted improvements where intended;
- module 02 MDF surround unmistakable;
- stone visibly reads as two owned pieces with rear upstand;
- all three stone presets work without geometry changes;
- sink immediately reads as realistic undermount stainless;
- faucet immediately reads as realistic high-arc kitchen faucet;
- full rear wall tile reads continuously from laundry through kitchen;
- corner LED profile reads as installed hardware and lights the worktop plausibly;
- no decorative props are needed for any of the above;
- user F6 gate explicitly approves the candidate.

Only after this milestone should the PR move from visual-correction-loop toward integration readiness.