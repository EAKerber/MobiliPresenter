import type { FixedPerspectiveCamera, Vec3 } from "@mobilipresenter/scene-core";
import { PerspectiveCamera, Vector3 } from "three";
import { sceneDirectionToThree, sceneVectorToThree } from "./coordinates.js";

export interface PixelViewport {
  readonly widthPx: number;
  readonly heightPx: number;
}

export interface PixelCrop {
  readonly xPx: number;
  readonly yPx: number;
  readonly widthPx: number;
  readonly heightPx: number;
}

function assertViewport(viewport: PixelViewport): void {
  if (!(viewport.widthPx > 0 && viewport.heightPx > 0)) throw new Error("VIEWPORT_INVALID");
}

function assertAspectRatio(aspectRatio: number): void {
  if (!Number.isFinite(aspectRatio) || aspectRatio <= 0) throw new Error("CAMERA_ASPECT_INVALID");
}

function assertCrop(fullViewport: PixelViewport, crop: PixelCrop): void {
  if (!(crop.widthPx > 0 && crop.heightPx > 0 && crop.xPx >= 0 && crop.yPx >= 0)) {
    throw new Error("CAMERA_CROP_INVALID");
  }
  if (crop.xPx + crop.widthPx > fullViewport.widthPx || crop.yPx + crop.heightPx > fullViewport.heightPx) {
    throw new Error("CAMERA_CROP_OUTSIDE_VIEWPORT");
  }
}

function configureOffAxisProjection(
  camera: PerspectiveCamera,
  source: FixedPerspectiveCamera,
  fullViewport: PixelViewport,
  crop?: PixelCrop
): void {
  assertViewport(fullViewport);
  if (crop) assertCrop(fullViewport, crop);

  const near = source.nearMm;
  const far = source.farMm;
  const fovRadians = source.fovYDeg * Math.PI / 180;
  const fullFrustumHeight = 2 * near * Math.tan(fovRadians / 2);
  const fullFrustumWidth = fullFrustumHeight * fullViewport.widthPx / fullViewport.heightPx;
  const [principalX, principalY] = source.principalPointNormalized;

  const fullLeft = -principalX * fullFrustumWidth;
  const fullRight = (1 - principalX) * fullFrustumWidth;
  const fullBottom = -(1 - principalY) * fullFrustumHeight;
  const fullTop = principalY * fullFrustumHeight;

  let left = fullLeft;
  let right = fullRight;
  let bottom = fullBottom;
  let top = fullTop;

  if (crop) {
    const u0 = crop.xPx / fullViewport.widthPx;
    const u1 = (crop.xPx + crop.widthPx) / fullViewport.widthPx;
    const v0 = crop.yPx / fullViewport.heightPx;
    const v1 = (crop.yPx + crop.heightPx) / fullViewport.heightPx;
    left = fullLeft + (fullRight - fullLeft) * u0;
    right = fullLeft + (fullRight - fullLeft) * u1;
    top = fullTop - (fullTop - fullBottom) * v0;
    bottom = fullTop - (fullTop - fullBottom) * v1;
  }

  const x = 2 * near / (right - left);
  const y = 2 * near / (top - bottom);
  const a = (right + left) / (right - left);
  const b = (top + bottom) / (top - bottom);
  const c = -(far + near) / (far - near);
  const d = -2 * far * near / (far - near);

  camera.projectionMatrix.set(
    x, 0, a, 0,
    0, y, b, 0,
    0, 0, c, d,
    0, 0, -1, 0
  );
  camera.projectionMatrixInverse.copy(camera.projectionMatrix).invert();
}

export function createThreeCamera(
  source: FixedPerspectiveCamera,
  viewport: PixelViewport
): PerspectiveCamera {
  const camera = new PerspectiveCamera(
    source.fovYDeg,
    viewport.widthPx / viewport.heightPx,
    source.nearMm,
    source.farMm
  );
  camera.position.copy(sceneVectorToThree(source.positionMm));
  camera.up.copy(sceneDirectionToThree(source.up));
  camera.lookAt(sceneVectorToThree(source.targetMm));
  camera.updateMatrixWorld(true);
  configureOffAxisProjection(camera, source, viewport);
  return camera;
}

export function updateThreeCameraAspect(
  camera: PerspectiveCamera,
  source: FixedPerspectiveCamera,
  aspectRatio: number
): void {
  assertAspectRatio(aspectRatio);
  camera.aspect = aspectRatio;
  configureOffAxisProjection(camera, source, { widthPx: aspectRatio, heightPx: 1 });
}

export function updateThreeCameraViewport(
  camera: PerspectiveCamera,
  source: FixedPerspectiveCamera,
  viewport: PixelViewport
): void {
  assertViewport(viewport);
  updateThreeCameraAspect(camera, source, viewport.widthPx / viewport.heightPx);
}

export function updateThreeCameraCrop(
  camera: PerspectiveCamera,
  source: FixedPerspectiveCamera,
  fullViewport: PixelViewport,
  crop: PixelCrop
): void {
  camera.aspect = crop.widthPx / crop.heightPx;
  configureOffAxisProjection(camera, source, fullViewport, crop);
}

export function projectScenePointWithThree(
  camera: PerspectiveCamera,
  viewport: PixelViewport,
  pointMm: Vec3
): readonly [number, number] {
  const point = sceneVectorToThree(pointMm).project(camera);
  return [
    (point.x + 1) * 0.5 * viewport.widthPx,
    (1 - point.y) * 0.5 * viewport.heightPx
  ];
}

export function principalPointPixels(
  source: FixedPerspectiveCamera,
  viewport: PixelViewport
): readonly [number, number] {
  return [
    source.principalPointNormalized[0] * viewport.widthPx,
    source.principalPointNormalized[1] * viewport.heightPx
  ];
}

export function cameraForwardThree(source: FixedPerspectiveCamera): Vector3 {
  return sceneVectorToThree({
    x: source.targetMm.x - source.positionMm.x,
    y: source.targetMm.y - source.positionMm.y,
    z: source.targetMm.z - source.positionMm.z
  }).normalize();
}
