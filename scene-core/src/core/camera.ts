import { cross, dot, norm, sub } from "./math.js";
import type { Vec3 } from "./math.js";
import type { FixedPerspectiveCamera, PresentationFrame } from "../contracts/model.js";

export interface Viewport {
  readonly widthPx: number;
  readonly heightPx: number;
}

export interface ProjectedPoint {
  readonly xPx: number;
  readonly yPx: number;
  readonly depthMm: number;
  readonly insideClipRange: boolean;
}

export interface CameraBasis {
  readonly right: Vec3;
  readonly up: Vec3;
  readonly forward: Vec3;
}

export function cameraBasis(camera: FixedPerspectiveCamera): CameraBasis {
  const forward = norm(sub(camera.targetMm, camera.positionMm));
  const right = norm(cross(forward, camera.up));
  const up = norm(cross(right, forward));
  return { right, up, forward };
}

export function focalLengthPx(camera: FixedPerspectiveCamera, viewport: Viewport): number {
  if (!(viewport.widthPx > 0 && viewport.heightPx > 0)) throw new Error("VIEWPORT_INVALID");
  return (viewport.heightPx / 2) / Math.tan((camera.fovYDeg * Math.PI / 180) / 2);
}

export function projectPoint(
  camera: FixedPerspectiveCamera,
  viewport: Viewport,
  pointMm: Vec3
): ProjectedPoint {
  const basis = cameraBasis(camera);
  const relative = sub(pointMm, camera.positionMm);
  const depthMm = dot(relative, basis.forward);
  if (Math.abs(depthMm) < 1e-9) throw new Error("POINT_ON_CAMERA_PLANE");

  const xCamera = dot(relative, basis.right);
  const zCamera = dot(relative, basis.up);
  const focalPx = focalLengthPx(camera, viewport);
  const principalX = camera.principalPointNormalized[0] * viewport.widthPx;
  const principalY = camera.principalPointNormalized[1] * viewport.heightPx;

  return {
    xPx: principalX + focalPx * xCamera / depthMm,
    yPx: principalY - focalPx * zCamera / depthMm,
    depthMm,
    insideClipRange: depthMm >= camera.nearMm && depthMm <= camera.farMm
  };
}

export function preferredViewportHeight(widthPx: number, frame: PresentationFrame): number {
  if (!(widthPx > 0 && frame.preferredAspectRatio > 0)) throw new Error("PRESENTATION_FRAME_INVALID");
  return widthPx / frame.preferredAspectRatio;
}
