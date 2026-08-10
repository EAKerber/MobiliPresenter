# FH-06.1 — Oven surround + stone/sink/faucet specification

Status: **design-default / renderer contract**  
Branch: `renderer/fixed-view-realistic-v1`  
Purpose: stop treating the oven surround and sink station as afterthoughts. These values are intentionally generic but plausible. They are stable renderer/product defaults, **not construction instructions**; explicit future project data may supersede them.

## 1. Authority and intent

- Fixed camera remains invariant.
- mm remains physical/model authority; pixels are projection evidence.
- The current user references are the visual target for proportions and reading.
- Vendor data below is used as a dimensional archetype, not as a claim that the rendered scene contains those commercial products.
- Indispensable realism: oven+MDF surround, countertop, rear upstand, sink and faucet.
- Optional realism: cookware, rack, utensils and decorative props. These may never be required for the sink station to pass.

## 2. Full-wall tile finish

Decision: **tile is the complete wall finish**, not a local backsplash patch.

Contract:
- apply to all visible rear-wall surfaces from laundry through kitchen;
- continue over the visible faces of the column/projection where that same wall finish wraps;
- geometry remains EnvironmentGeometry; tile is a material/appearance assignment;
- default tile module: `400 x 400 mm`;
- default grout: `2 mm`;
- default finish: warm off-white, subtle normal/roughness variation;
- cabinets/appliances occlude the tiled wall naturally; no hand-cut central overlay.

## 3. Module 02 — oven and MDF surround

### 3.1 Problem being corrected

The current renderer may use the large host slot as the oven's visual envelope. That stretches/fits the appliance into the bay and removes the MDF field visible in the references.

The host slot and the **oven front opening are different contracts**.

### 3.2 Stable visual dimensions

Current module 02 nominal front envelope:
- width: `790 mm`;
- height: `760 mm`.

Generic 60 cm built-in oven archetype:
- front face: `596 x 596 mm`;
- front opening / flush recess: `600 x 600 mm`.

Derived MDF surround in the 790 x 760 front:
- left stile: `95 mm`;
- right stile: `95 mm`;
- top rail: `80 mm`;
- bottom rail: `80 mm`.

MDF material thickness remains `18 mm`; **18 mm is panel thickness, not the visible surround width**.

### 3.3 Render rules

- oven fit policy: `physical-size/contain`, never stretch-to-slot;
- front opening is 600 x 600 and centered in the 790 x 760 module face;
- oven face is 596 x 596, leaving a small installation/reveal tolerance inside the 600 x 600 opening;
- four explicit MDF front-surround primitives must exist and remain visible;
- the older 755 x 724 bay may remain as host/cavity evidence but must not define the oven's front-face size;
- current 530 mm module depth is **not certified for physical installation** of the dimensional archetype; visual front fidelity is the contract for this increment.

### 3.4 Acceptance

Hard:
- outer module envelope unchanged;
- opening = 600 x 600 mm;
- derived surround = 95/95/80/80 mm;
- oven never changes the module geometry digest;
- module 02 hidden still activates the freestanding-range replacement policy.

Visual:
- at canonical viewport the MDF surround must be unmistakable on all four sides without cookware/props;
- projected widths are measured analytically from the 3D endpoints and compared by the Fidelity Harness.

## 4. Countertop as two owned stone pieces

Decision: the countertop is physically/semantically **two pieces**:
- `STONE-02`, owned by module 02;
- `STONE-03`, owned by module 03.

They remain separate entities even when the same finish is selected.

### 4.1 Geometry defaults

- each piece inherits authoritative current module X-span/depth when available;
- current visual depth target remains approximately `550 mm`;
- design-default slab thickness when no stronger source is supplied: `30 mm`;
- front overhang target relative to a 530 mm cabinet: `20 mm`;
- adjoining pieces touch at their module boundary; no fake physical gap is added;
- the seam may receive a subtle `~1 mm` render/readability cue without altering physical span.

A prior Promob/DXF proxy thickness may be preserved as provenance. The 30 mm value is the stable **design default** because the final physical stone specification was never decided.

### 4.2 Rear upstand / batente

Each stone piece owns its corresponding rear upstand:
- height: `100 mm`;
- thickness/depth: `20 mm`;
- same finish as its owner stone piece by default;
- same seam position as the 02/03 countertop split;
- sits on the rear edge of the countertop and in front of the tiled wall.

`100 mm` is a project design convention selected from the visual references, not an asserted universal installation standard.

### 4.3 Finish presets

Minimum stable presets:
1. `stone-light-speckled` — default/reference-like;
2. `stone-warm-beige-speckled`;
3. `stone-graphite-speckled`.

Rules:
- geometry is identical across colors;
- finish selection is linked across STONE-02 and STONE-03 by default;
- independent override remains possible later;
- physical texture scale is stable in mm;
- no texture change may modify cutouts, seam position or transforms.

## 5. Sink — stable generic family

Definition ID: `SINK-UNDERMOUNT-40X34-01`.

Dimensional archetype is a common 40 x 34 cm undermount stainless bowl:
- outer length: `400 mm`;
- outer width: `340 mm`;
- bowl depth: `170 mm`;
- flange/rim reference: `15 mm`;
- outer corner radius reference: `80 mm`;
- installation class: **undermount only**;
- material class: brushed AISI 304 stainless;
- drain: centered in X, offset approximately `112 mm` from the referenced rear/short edge, matching the dimensional archetype drawing.

### 5.1 Geometry strategy

**Own parametric geometry is authoritative at runtime.**

Do not use a rectangular box approximation.

Required construction:
- rounded-rectangle rim/flange;
- continuous bowl walls with filleted/lofted transition;
- rounded bottom transition;
- real countertop cutout: stone must not remain as a solid slab through the bowl;
- subtle drain geometry may be included; it is not a hard visual requirement.

Official vendor CAD/DXF/SketchUp may be used as a **development fidelity oracle**, but must not become an undeclared runtime dependency or be redistributed unless reuse rights are clear.

## 6. Faucet — stable generic high-arc family

Definition ID: `FAUCET-HIGH-ARC-01`.

Dimensional archetype:
- deck-mounted;
- overall height: `340 mm`;
- maximum reach/projection: `255 mm`;
- principal body width/diameter reference: `35 mm`;
- brushed stainless visual class;
- high articulated/rotating spout silhouette.

### 6.1 Geometry strategy

Use **own deterministic geometry**, not a random internet model:
- base/body;
- swept tubular high-arc spout using a smooth curve;
- separate nozzle/aerator;
- visible single lever/control;
- physically plausible circular/rounded sections;
- no single-cylinder proxy.

Official CAD from a real dimensional archetype can be used to validate silhouette/bounds during authoring, but the runtime family remains our own generic asset.

### 6.2 Placement

Current scene:
- retain the confirmed sink/countertop placement where available;
- faucet is hosted by STONE-03, not by the wall;
- nominal default fallback: faucet centered on the sink X and mounted behind the bowl with sufficient deck clearance;
- future explicit project data may override its local anchor without changing the family definition.

## 7. Sink-station acceptance gate

The station does **not** pass because props make it look realistic.

Hard acceptance:
- STONE-02 and STONE-03 exist as separate owned geometry;
- seam/boundary equals module boundary;
- 3 finish presets do not alter geometry;
- rear upstand exists across both pieces;
- sink cutout is real and no impossible stone/bowl intersection exists;
- sink bounds and depth match the definition;
- faucet remains hosted to STONE-03 and deterministic;
- F0-F4 remain PASS.

Visual acceptance at canonical 1865 x 967:
- countertop reads as stone, not a flat generic box;
- short rear stone upstand is clearly visible in front of the full tiled wall;
- sink is immediately recognizable as a real undermount stainless bowl;
- faucet is immediately recognizable as a realistic high-arc kitchen faucet;
- sink/faucet cannot look like late-added primitives;
- no cookware, rack or decorative props are required to achieve the above;
- F5 semantic edge/readability does not regress;
- F6 human gate explicitly approves oven-surround and sink-station reading.

## 8. Fidelity probes to add

### Module 02
- left/right MDF stile inner and outer edges;
- top/bottom MDF rail inner and outer edges;
- oven facade bounds.

### Stone/sink/faucet
- STONE-02/STONE-03 seam;
- countertop front edge;
- upstand top edge;
- sink cutout left/right/front/back bounds;
- sink rim silhouette;
- faucet base and topmost/high-arc landmark.

All probes are defined in mm and projected analytically; 4x crops remain measurement-only.

## 9. Source-backed rationale

Research anchors used for this design-default:
- Electrolux 60 cm built-in oven family: ~596 x 596 mm product face and ~600 x 600 mm flush opening; installation documentation distinguishes front opening from internal niche/body requirements.
- Tramontina Lavínia 40 BL family: 400 x 340 x 170 mm undermount bowl, AISI 304, technical drawing with 15 mm flange reference and rounded geometry; official page exposes technical drawing and CAD/DXF/SketchUp/Revit downloads.
- Tramontina high-arc deck faucet family: approximately 340 mm high x 255 mm projection x 35 mm principal width; official page exposes CAD DXF.
- Quartz/engineered-stone manufacturers commonly publish 20 and 30 mm countertop slab options; this project chooses 30 mm as its stable unsourced design-default.

## 10. Explicitly deferred

- construction-ready oven ventilation/electrical design;
- actual stone supplier/fabricator specification;
- plumbing connections and drain traps;
- vendor-specific faucet/sink branding;
- props such as cookware, dish rack and utensils;
- alternative sink/faucet presets beyond the first stable family.
