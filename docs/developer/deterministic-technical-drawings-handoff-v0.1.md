# Developer handoff — deterministic technical drawings v0.1

Status: proposal / docs-only handoff  
Audience: Developer / Engine / TPC  
Scope: technical drawing generation consumed by the product UI  
Non-goal: redesigning the UI shell or changing camera authority

## 1. Why this exists

The current technical views are functionally useful but visually and semantically insufficient for the product presentation target. The main issue is not only styling: several current views are schematic/envelope-like and therefore do not provide the same confidence as a drawing genuinely derived from the module geometry.

Image generation can produce attractive technical-looking illustrations, but it should not become the authoritative product pipeline. It may be used for style exploration or temporary visual references only. Final technical views must be reproducible, dimensionally reliable and derived from authoritative geometry/data.

## 2. Target responsibility split

### Developer / Engine / TPC owns

- extracting projections from authoritative module geometry;
- deriving frontal, lateral, isometric and internal views where geometry supports them;
- obtaining dimensions from authoritative dimensional data, never from pixels;
- positioning dimension anchors from geometry or declared datum points;
- declaring fidelity, coverage and omissions;
- emitting deterministic SVG/vector assets or an equivalent structured representation;
- guaranteeing reproducibility for the same input package/version.

### UI owns

- typography, line hierarchy and visual styling;
- responsive sizing and gallery composition;
- spacing, captions, legends and disclosure;
- presentation of fidelity/coverage evidence;
- commercial/editorial placement of the drawings;
- never reconstructing geometry or inventing missing dimensions.

## 3. Recommended pipeline

```text
authoritative module geometry + authoritative dimensions
        ↓
projection stage
        ├── front
        ├── side
        ├── isometric
        └── internal / section when supported
        ↓
feature extraction / silhouette / opening lines
        ↓
dimension anchors + dimension values
        ↓
vector technical asset
        ↓
TechnicalPresentationPackage
        ↓
UI styling only
```

A technical view should be generated from the same authoritative geometry used by the viewer or from another explicitly declared authoritative technical source. Bounding-box envelopes are acceptable only when explicitly labeled `schematic`; they must never silently substitute a geometry-derived drawing.

## 4. Minimum information expected per technical asset

The exact schema is Developer-owned, but the UI needs enough semantics to distinguish at least:

- `viewId` / stable identity;
- `kind`: front | side | isometric | internal | section | other;
- `status`: ready | unavailable | external-required;
- `fidelity`: geometry-derived | authored | schematic;
- `source` / provenance;
- `coverage[]`;
- `omitted[]`;
- vector asset / SVG;
- units;
- dimensional annotations or enough structured geometry to place them deterministically;
- optional datum/reference information when required for non-trivial dimension placement.

## 5. Drawing quality requirements

### Geometry

- silhouette follows the real module geometry;
- openings, doors, drawers, cavities and major internal divisions appear when represented by the authoritative geometry;
- front/side projections use the correct orientation and datum;
- isometric projection must be a true deterministic projection, not a generic cuboid derived only from width/height/depth when richer geometry exists;
- internal view is emitted only if the model contains enough information to support it honestly.

### Dimensions

- values come from authoritative dimensional data or exact geometry-derived distances;
- extension lines and dimension lines are anchored to the represented geometry;
- width, height and depth are supported where applicable;
- duplicate/overlapping dimensions are resolved deterministically;
- labels do not cross major geometry when a valid alternative placement exists;
- all dimensions declare/assume a single explicit unit system per asset.

### Visual structure exposed to UI

SVG elements should preferably expose semantic hooks such as roles/classes/data attributes for:

- primary geometry;
- secondary/internal geometry;
- hidden/omitted geometry when intentionally represented;
- dimension line;
- extension line;
- arrow/tick;
- dimension label;
- opening/cavity;
- optional datum/reference.

The UI must be able to restyle strokes and typography without changing geometry or values.

## 6. Desired view set

Priority order:

1. **front — geometry-derived**
2. **side — geometry-derived**
3. **isometric — geometry-derived**
4. **internal — geometry-derived where the model supports it**
5. authored/external technical assets where geometry alone is insufficient

A missing truthful view is preferable to a polished invented one.

## 7. Fidelity semantics

Recommended interpretation:

- `geometry-derived`: deterministic projection from authoritative scene/technical geometry;
- `authored`: trusted external/technical drawing explicitly associated with the module;
- `schematic`: dimensional/envelope representation that is useful but not a faithful depiction of complete geometry.

The UI will present these differently. It must be possible to tell whether a technical view is appropriate for high-confidence product presentation without inspecting SVG internals.

## 8. Acceptance criteria

The recut is complete when:

1. at least one representative lower module with doors/drawers has front, side and isometric views generated deterministically from authoritative geometry;
2. the same input produces byte-stable or semantically stable output under the same generator/version;
3. all displayed dimension values can be traced to authoritative dimensions/geometry;
4. a geometry-derived view cannot silently fall back to a plain width/height/depth envelope;
5. `coverage` and `omitted` explicitly communicate what the drawing does and does not represent;
6. UI can change stroke weight, typography, background and dimension styling without changing any geometric coordinates or dimension values;
7. tests compare key projected bounds/dimensions against authoritative geometry;
8. modules lacking enough geometry degrade to `schematic`, `external-required` or `unavailable` rather than receiving an invented drawing.

## 9. Suggested validation cases

Use modules that exercise different geometry families:

- appliance-hosting lower module;
- drawer module;
- two-door lower module;
- upper module;
- tall/narrow module;
- module with meaningful internal geometry, when available.

For each representative case verify:

- projected width/height;
- side depth;
- isometric extents;
- opening/division count where authoritative;
- dimension values;
- no clipping of dimension labels at canonical viewport sizes.

## 10. Role of image generation

Generative imagery is explicitly **non-authoritative** for this pipeline.

Allowed uses:

- exploring visual language;
- proposing line weights, typography and annotation style;
- generating a temporary mood/reference image for UI review.

Not allowed as final technical authority:

- deriving dimensions from generated pixels;
- using generated geometry as truth;
- replacing missing internal structure with plausible-looking content;
- publishing generated technical drawings as `geometry-derived` or `authored` without an authoritative source.

## 11. Relationship with the current UI work

The UI can continue improving presentation now: typography, spacing, iconography, scroll behavior and SVG styling remain UI-owned.

This handoff specifically targets the remaining fidelity gap in technical drawings. When this contract/pipeline is available, the product UI should consume the richer assets directly; no UI-side redrawing or generative-image fallback should be required.
