import { projectPoint } from "../core/camera.js";
import { add, mul, norm } from "../core/math.js";
import type { Vec3 } from "../core/math.js";
import type { FixedPerspectiveCamera } from "../contracts/model.js";

export type FidelitySupersampleFactor = 1 | 4 | 8;

export interface FidelityViewport {
  readonly widthPx: number;
  readonly heightPx: number;
}

export interface ScreenMetricProfile {
  readonly canonicalViewport: FidelityViewport;
  readonly supersampleFactor: FidelitySupersampleFactor;
  readonly renderViewport: FidelityViewport;
}

export interface ProjectedMetricEndpoint {
  readonly worldMm: Vec3;
  readonly xPx: number;
  readonly yPx: number;
  readonly canonicalXPx: number;
  readonly canonicalYPx: number;
  readonly depthMm: number;
  readonly insideClipRange: boolean;
}

export interface ProjectedMetricSegment {
  readonly a: ProjectedMetricEndpoint;
  readonly b: ProjectedMetricEndpoint;
  readonly physicalLengthMm: number;
  readonly renderedLengthPx: number;
  readonly canonicalLengthPx: number;
  readonly supersampleFactor: FidelitySupersampleFactor;
}

function assertViewport(viewport: FidelityViewport): void {
  if (!(viewport.widthPx > 0 && viewport.heightPx > 0)) throw new Error("FIDELITY_VIEWPORT_INVALID");
}

export function createScreenMetricProfile(
  canonicalViewport: FidelityViewport,
  supersampleFactor: FidelitySupersampleFactor = 4
): ScreenMetricProfile {
  assertViewport(canonicalViewport);
  if (![1, 4, 8].includes(supersampleFactor)) throw new Error("FIDELITY_SUPERSAMPLE_UNSUPPORTED");
  return {
    canonicalViewport,
    supersampleFactor,
    renderViewport: {
      widthPx: canonicalViewport.widthPx * supersampleFactor,
      heightPx: canonicalViewport.heightPx * supersampleFactor
    }
  };
}

function endpoint(
  camera: FixedPerspectiveCamera,
  profile: ScreenMetricProfile,
  pointMm: Vec3
): ProjectedMetricEndpoint {
  const projected = projectPoint(camera, profile.renderViewport, pointMm);
  const factor = profile.supersampleFactor;
  return {
    worldMm: pointMm,
    xPx: projected.xPx,
    yPx: projected.yPx,
    canonicalXPx: projected.xPx / factor,
    canonicalYPx: projected.yPx / factor,
    depthMm: projected.depthMm,
    insideClipRange: projected.insideClipRange
  };
}

export function projectMetricSegment(
  camera: FixedPerspectiveCamera,
  profile: ScreenMetricProfile,
  pointAmm: Vec3,
  pointBmm: Vec3
): ProjectedMetricSegment {
  const a = endpoint(camera, profile, pointAmm);
  const b = endpoint(camera, profile, pointBmm);
  const physicalLengthMm = Math.hypot(
    pointBmm.x - pointAmm.x,
    pointBmm.y - pointAmm.y,
    pointBmm.z - pointAmm.z
  );
  const renderedLengthPx = Math.hypot(b.xPx - a.xPx, b.yPx - a.yPx);
  return {
    a,
    b,
    physicalLengthMm,
    renderedLengthPx,
    canonicalLengthPx: renderedLengthPx / profile.supersampleFactor,
    supersampleFactor: profile.supersampleFactor
  };
}

export function projectedPixelsPerMm(
  camera: FixedPerspectiveCamera,
  profile: ScreenMetricProfile,
  pointMm: Vec3,
  direction: Vec3
): number {
  const unit = norm(direction);
  const segment = projectMetricSegment(camera, profile, pointMm, add(pointMm, mul(unit, 1)));
  return segment.canonicalLengthPx;
}

export function normalizeSupersampledError(
  supersampledErrorPx: number,
  supersampleFactor: FidelitySupersampleFactor
): number {
  if (![1, 4, 8].includes(supersampleFactor)) throw new Error("FIDELITY_SUPERSAMPLE_UNSUPPORTED");
  return supersampledErrorPx / supersampleFactor;
}
