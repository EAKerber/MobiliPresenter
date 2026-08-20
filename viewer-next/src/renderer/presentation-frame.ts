import type { PresentationFrame } from "@mobilipresenter/scene-core";

export interface PresentationHostViewport {
  readonly widthPx: number;
  readonly heightPx: number;
}

export interface PresentationRasterRect {
  readonly xPx: number;
  readonly yPx: number;
  readonly widthPx: number;
  readonly heightPx: number;
}

export interface ResolvedPresentationFrame {
  readonly active: boolean;
  readonly hostViewport: PresentationHostViewport;
  readonly rasterRect: PresentationRasterRect;
  readonly projectionAspectRatio: number;
  readonly fit: "legacy" | "contain";
  readonly cropped: false;
}

function assertFinitePositive(value: number, code: string): void {
  if (!Number.isFinite(value) || value <= 0) throw new Error(code);
}

function assertHostViewport(viewport: PresentationHostViewport): void {
  assertFinitePositive(viewport.widthPx, "PRESENTATION_HOST_WIDTH_INVALID");
  assertFinitePositive(viewport.heightPx, "PRESENTATION_HOST_HEIGHT_INVALID");
}

function fullHost(viewport: PresentationHostViewport): ResolvedPresentationFrame {
  return {
    active: false,
    hostViewport: viewport,
    rasterRect: { xPx: 0, yPx: 0, widthPx: viewport.widthPx, heightPx: viewport.heightPx },
    projectionAspectRatio: viewport.widthPx / viewport.heightPx,
    fit: "legacy",
    cropped: false
  };
}

export function resolvePresentationFrame(
  hostViewport: PresentationHostViewport,
  frame?: PresentationFrame
): ResolvedPresentationFrame {
  assertHostViewport(hostViewport);
  if (frame === undefined) return fullHost(hostViewport);

  assertFinitePositive(frame.preferredAspectRatio, "PRESENTATION_FRAME_ASPECT_INVALID");
  if (frame.fit !== "contain") throw new Error("PRESENTATION_FRAME_POLICY_UNSUPPORTED");

  const widthLimit = Math.max(1, Math.round(hostViewport.widthPx));
  const heightLimit = Math.max(1, Math.round(hostViewport.heightPx));
  const hostAspect = hostViewport.widthPx / hostViewport.heightPx;
  const targetAspect = frame.preferredAspectRatio;

  let widthPx: number;
  let heightPx: number;
  if (hostAspect >= targetAspect) {
    heightPx = heightLimit;
    widthPx = Math.min(widthLimit, Math.max(1, Math.round(heightPx * targetAspect)));
  } else {
    widthPx = widthLimit;
    heightPx = Math.min(heightLimit, Math.max(1, Math.round(widthPx / targetAspect)));
  }

  const xPx = Math.floor((widthLimit - widthPx) / 2);
  const yPx = Math.floor((heightLimit - heightPx) / 2);

  return {
    active: true,
    hostViewport: { widthPx: widthLimit, heightPx: heightLimit },
    rasterRect: { xPx, yPx, widthPx, heightPx },
    projectionAspectRatio: targetAspect,
    fit: "contain",
    cropped: false
  };
}
