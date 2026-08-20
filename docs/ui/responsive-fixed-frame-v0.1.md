# Responsive Fixed-Frame 0.1 — frame enforcement + compact allocation

Status: RF-0.1A and RF-0.1B implemented

## Objective

Viewer Next keeps one calibrated fixed camera while the UI reallocates screen space around it. `ScenePackage.presentationFrame` owns framing; responsive UI owns only the host rectangle made available to that frame.

Responsive Fixed-Frame 0.1 is split into two proofs:

1. **RF-0.1A — PresentationFrame Enforcement:** any host rectangle preserves the published fixed-frame composition.
2. **RF-0.1B — Compact Allocation:** opening contextual module detail at compact widths must not collapse or reframe the scene host.

## Frame contract

The current scene publishes a fixed calibrated camera and a `PresentationFrame` with a preferred aspect ratio, `fit: contain`, and no cropping. Physical camera fields remain unchanged. Raster dimensions may round to integer pixels, but projection uses the exact published `preferredAspectRatio`.

Normal runtime rendering follows:

```text
UI host allocation
  -> resolve PresentationFrame
  -> centered contained raster rectangle
  -> exact published projection aspect
  -> fixed camera render
```

The fidelity crop path remains independent and keeps its calibrated full-viewport/crop semantics.

## Compact allocation policy

At wide desktop widths, module detail remains a right-hand contextual panel and may reserve horizontal layout space.

Between 761px and 1240px wide, the stage remains persistent but narrows to a compact width. Module detail becomes a bounded overlay above the scene instead of subtracting its width from `#app`.

```text
compact host, detail closed
┌──────────┬────────────────────────────┐
│  stage   │            scene           │
└──────────┴────────────────────────────┘

compact host, detail open
┌──────────┬────────────────────────────┐
│  stage   │         scene              │
│          │              ┌───────────┐ │
│          │              │  detail   │ │
│          │              └───────────┘ │
└──────────┴────────────────────────────┘
```

The scene host rectangle is identical before and after detail opens. Because RF-0.1A already binds projection to `PresentationFrame`, this also guarantees no detail-triggered camera reframe.

At 760px and below, the existing mobile composition remains in force: scene on top, stage below, contextual detail as a bottom sheet.

## Browser evidence

Runtime UI evidence covers:

- 1366x768 wide desktop;
- 1024x768 compact landscape;
- 768x1024 compact portrait boundary pressure;
- 390x844 mobile.

For the compact 1024x768 and 768x1024 cases, evidence additionally compares detail-open and detail-closed DOMs and requires exactly equal `data-presentation-host-*` dimensions.

The compact landscape host must retain at least 700px of scene width. The 768px portrait boundary must retain at least 500px. These are allocation guards, not camera or Scene Core semantics.

## Non-goals

- no camera movement, pan, user zoom, focus-to-module, or heuristic reframe;
- no Scene Core schema change;
- no change to Guided Configurator semantics;
- no technical-content or catalog changes;
- no framework rewrite;
- no new product state or authority.

## Completion gate

Responsive Fixed-Frame 0.1 is complete when:

1. the same fixed camera and PresentationFrame preserve normalized composition across all four reference viewports;
2. contain/no-crop remains true;
3. compact detail open/close leaves the scene host geometry unchanged;
4. compact scene width stays above the declared allocation guards;
5. Viewer Next verify, runtime UI smoke, fidelity, readability and lifecycle gates remain green.
