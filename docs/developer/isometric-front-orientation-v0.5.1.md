# Isometric Front Orientation v0.5.1

## Objective

Correct the camera hemisphere of the technical isometric projection without reopening the v0.5 equal-foreshortening kernel or the v0.6 technical-line policy.

The v0.5 projection is mathematically isometric, but `viewDirection = (1, 1, 1)` did not define whether the vector pointed from the camera into the scene or from the scene toward the camera. The resulting drawing was spatially coherent while reading as if the product face were on the far side.

## Scene semantics

Scene Core uses:

- `x`: width/right;
- `y`: depth/back;
- `z`: up.

Current cabinet fronts are physically on the lower-y side of the module. Module 03 front boxes occupy `y = -18 .. 0`, while the carcass extends from `y = 0` toward `y = 530`.

The calibrated product viewer also observes the scene from the lower-y side. Relative to module 03 it is on the front-left-above hemisphere.

The technical isometric does not copy the perspective camera calibration. It only adopts the same semantic hemisphere.

## Canonical orientation

v0.5.1 replaces the ambiguous `viewDirection` field with an explicit `sceneToCameraDirection`.

The canonical virtual technical camera is front-left-above:

```text
sceneToCameraDirection = normalize(-1, -1, +1)
worldUp                = (0, 0, +1)
screenRight            = normalize(worldUp x sceneToCameraDirection)
screenUp               = normalize(sceneToCameraDirection x screenRight)
```

The common drawing scale remains `sqrt(3 / 2)`.

The derived projected basis becomes approximately:

- width: `( +0.866025, +0.5 )`;
- depth: `( -0.866025, +0.5 )`;
- height: `( 0, +1 )`.

Projection coordinates are still technical vertical-up; SVG screen-Y inversion remains renderer-owned.

## Front-facing invariant

The kernel exposes `isometricViewDepth(point)`. Larger values are closer to the technical camera.

For points sharing x/z:

```text
front y=-18  >  carcass front y=0  >  rear y=530
```

in view-depth order.

This makes front/back semantics independently testable instead of relying on visual intuition or a final SVG mirror.

## Gates

The R2.1 gates require:

- the scene-to-camera direction to be unit length;
- camera hemisphere `x < 0`, `y < 0`, `z > 0`;
- screen-right and screen-up to remain orthonormal to the viewing normal;
- positive Scene Core z to remain screen-up;
- front physical datum to be closer than the rear datum;
- equal foreshortening and non-degenerate width/depth area from v0.5 to remain unchanged;
- module 03 width/depth guides to recede upward from the front datum;
- the R2 technical-line model to preserve its physical/rendered counts and provenance;
- module 04 to remain the generic thin-panel stress case;
- all three dimensions to remain unique.

## Deliberate non-goals

This slice does not:

- add hidden-line removal;
- change which R2 line classes are rendered;
- merge collinear segments;
- change Scene Core geometry;
- change Technical Composition / Formator policy;
- alter the calibrated 3D viewer camera;
- add appliance assets.

The technical drawing may therefore still contain more internal structure than the desired final presentation. R2.1 succeeds when the product is observed from the correct physical front/upper hemisphere while preserving the mathematical and representation contracts already established.
