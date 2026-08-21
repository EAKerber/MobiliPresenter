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

Between 901px and 1240px wide, the stage remains persistent but narrows to a compact width. Module detail becomes a bounded overlay above the scene instead of subtracting its width from `#app`.

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

At 900px and below, the mobile composition remains in force: scene on top, stage below, contextual detail as a bottom sheet. The explicit 900/901 boundary prevents tablet portrait from inheriting a desktop-style overlay that leaves too little of the scene visible.

## Browser evidence

Runtime UI evidence uses Chrome DevTools Protocol viewport emulation, so the requested CSS viewport is also observed from inside the page. It covers:

- 1366x768 wide desktop;
- 1024x768 compact landscape;
- 768x1024 compact portrait boundary pressure;
- 390x844 mobile.

For the compact 1024x768 and mobile-sheet 768x1024 cases, evidence additionally compares detail-open and detail-closed DOMs and requires equal `#app` rectangles and `data-presentation-host-*` dimensions.

At compact landscape width, the overlay must leave at least the stage width plus 24px of the scene host horizontally unoccluded. Every reference viewport must report the exact requested `innerWidth`/`innerHeight`, no horizontal document overflow, and all primary UI rectangles inside the viewport. Dedicated DOM probes require `mobile-sheet` at 900px and `compact-overlay` at 901px.

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
4. compact overlay clearance stays above the declared stage-plus-24px guard;
5. requested and observed CSS viewports match, with no horizontal document overflow;
6. the 900/901 responsive boundary selects mobile sheet and compact overlay respectively;
7. Viewer Next verify, runtime UI smoke, fidelity, readability and lifecycle gates remain green.
