# Responsive Fixed-Frame 0.1 — PresentationFrame Enforcement

Status: implementation slice RF-0.1A

## Objective

Make the normal Viewer Next runtime honor the `ScenePackage.presentationFrame` that is already published by Scene Core. UI may allocate any host rectangle, but that allocation must not redefine the physical fixed camera or the normalized composition of the scene.

This slice deliberately separates two questions:

1. **RF-0.1A:** does the renderer preserve the published frame inside any UI allocation?
2. **RF-0.1B:** does the UI allocate a useful amount of space to that frame at compact widths?

RF-0.1B is not part of this slice.

## Current contract

The current scene publishes a fixed calibrated camera and a `PresentationFrame` with a preferred aspect ratio, `fit: contain`, and no cropping. The physical camera fields remain unchanged. The frame is a presentation contract, not a request to pan, zoom, focus, or heuristically move the camera.

## Runtime rule

Normal runtime rendering follows:

```text
UI host allocation
  -> resolve PresentationFrame
  -> centered contained raster rectangle
  -> exact published projection aspect
  -> fixed camera render
```

Raster dimensions are integer pixels. Projection aspect is the exact `preferredAspectRatio`; pixel rounding must not redefine the camera projection.

When no `presentationFrame` is present, the legacy full-host behavior remains valid. A present but unsupported frame policy fails closed instead of silently falling back to host-dependent framing.

The fidelity crop path remains independent and keeps its calibrated full-viewport/crop semantics.

## Evidence

The runtime exposes diagnostic `data-presentation-*` markers on `#app` for browser verification. They are inspection evidence only and do not create application state or authority.

Browser evidence covers four host viewports:

- 1366x768;
- 1024x768;
- 768x1024;
- 390x844.

The same fixed camera and PresentationFrame must yield the same normalized landmark projection across all four.

## Non-goals

- no change to Guided Configurator flow;
- no UI breakpoint redesign;
- no compact-detail overlay policy;
- no Scene Core schema change;
- no camera movement;
- no pan, user zoom, focus-to-module, or heuristic reframe;
- no product/catalog/content changes.

## Completion gate

RF-0.1A is complete when the current fixed camera and current PresentationFrame produce invariant normalized composition across the four reference viewports, with contain/no-crop behavior, while Viewer Next, fidelity, browser smoke, and renderer lifecycle gates remain green.
