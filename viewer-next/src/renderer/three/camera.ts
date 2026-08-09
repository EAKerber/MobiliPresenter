import type { FixedPerspectiveCamera, Vec3 } from "@mobilipresenter/scene-core";
import { PerspectiveCamera, Vector3 } from "three";
import { sceneDirectionToThree, sceneVectorToThree } from "./coordinates.js";

export interface PixelViewport {
  readonly widthPx: number;
  readonly heightPx: number;
}

function configureOffAxisProjection(
  camera: PerspectiveCamera,
  source: FixedPerspectiveCamera,
  viewport: PixelViewport
): void {
  if (!(viewport.widthPx > 0 && viewport.heightPx > 0)) throw new Error("VIEWPORT_INVALID");
  const near = source.nearMm;
  const far = source.farMm;
  const fovRadians = source.fovYDeg * Math.PI / 180;
  const frustumHeight = 2 * near * Math.tan(fovRadians / 2);
  const frustumWidth = frustumHeight * viewport.widthPx / viewport.heightPx;
  const [principalX, principalY] = source.principalPointNormalized;

  const left = -principalX * frustumWidth;
  const right = (1 - principalX) * frustumWidth;
  const bottom = -(1 - principalY) * frustumHeight;
  const top = principalY * frustumHeight;

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

export function updateThreeCameraViewport(
  camera: PerspectiveCamera,
  source: FixedPerspectiveCamera,
  viewport: PixelViewport
): void {
  camera.aspect = viewport.widthPx / viewport.heightPx;
  configureOffAxisProjection(camera, source, viewport);
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
