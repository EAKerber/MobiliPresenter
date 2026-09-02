import type { Vec3 } from "@mobilipresenter/scene-core";
import type { TechnicalPoint2Mm } from "./contracts.js";

export const ISOMETRIC_PROJECTION_CONTRACT_VERSION = "isometric-projection/v0.5" as const;

export interface TechnicalProjectionBasisVector {
  readonly horizontalMm: number;
  readonly verticalMm: number;
}

export interface IsometricProjectionBasis {
  readonly width: TechnicalProjectionBasisVector;
  readonly depth: TechnicalProjectionBasisVector;
  readonly height: TechnicalProjectionBasisVector;
}

export interface IsometricProjectionFrame {
  readonly viewDirection: Vec3;
  readonly screenRight: Vec3;
  readonly screenUp: Vec3;
  readonly drawingScale: number;
}

export interface IsometricProjectionMetrics {
  readonly widthScale: number;
  readonly depthScale: number;
  readonly heightScale: number;
  readonly normalizedWidthDepthArea: number;
}

function length3(vector: Vec3): number {
  return Math.hypot(vector.x, vector.y, vector.z);
}

function normalize3(vector: Vec3): Vec3 {
  const length = length3(vector);
  if (length < 1e-12) throw new Error("ISOMETRIC_PROJECTION_ZERO_VECTOR");
  return {
    x: vector.x / length,
    y: vector.y / length,
    z: vector.z / length
  };
}

function cross3(a: Vec3, b: Vec3): Vec3 {
  return {
    x: a.y * b.z - a.z * b.y,
    y: a.z * b.x - a.x * b.z,
    z: a.x * b.y - a.y * b.x
  };
}

function dot3(a: Vec3, b: Vec3): number {
  return a.x * b.x + a.y * b.y + a.z * b.z;
}

/**
 * Canonical engineering-isometric frame.
 *
 * The frame is the authority. The 2D basis below is derived from it, rather than
 * authored as three independent screen vectors. The view direction has equal
 * contribution from Scene Core x/y/z; screen-right and screen-up form an
 * orthonormal camera plane. A uniform drawingScale removes the common
 * orthographic foreshortening so one millimeter along any Scene Core axis has
 * the same projected length.
 *
 * Projection coordinates use technical vertical-up space. The SVG renderer
 * later inverts verticalMm into screen Y.
 */
const VIEW_DIRECTION = normalize3({ x: 1, y: 1, z: 1 });
const SCREEN_RIGHT = normalize3({ x: 1, y: -1, z: 0 });
const SCREEN_UP = normalize3(cross3(SCREEN_RIGHT, VIEW_DIRECTION));

export const ISOMETRIC_PROJECTION_FRAME: IsometricProjectionFrame = {
  viewDirection: VIEW_DIRECTION,
  screenRight: SCREEN_RIGHT,
  screenUp: SCREEN_UP,
  drawingScale: Math.sqrt(3 / 2)
};

function projectVector(
  vector: Vec3,
  frame: IsometricProjectionFrame = ISOMETRIC_PROJECTION_FRAME
): TechnicalProjectionBasisVector {
  return {
    horizontalMm: dot3(vector, frame.screenRight) * frame.drawingScale,
    verticalMm: dot3(vector, frame.screenUp) * frame.drawingScale
  };
}

export const ISOMETRIC_PROJECTION_BASIS: IsometricProjectionBasis = {
  width: projectVector({ x: 1, y: 0, z: 0 }),
  depth: projectVector({ x: 0, y: 1, z: 0 }),
  height: projectVector({ x: 0, y: 0, z: 1 })
};

function basisLength(vector: TechnicalProjectionBasisVector): number {
  return Math.hypot(vector.horizontalMm, vector.verticalMm);
}

export function isometricProjectionMetrics(
  basis: IsometricProjectionBasis = ISOMETRIC_PROJECTION_BASIS
): IsometricProjectionMetrics {
  const widthScale = basisLength(basis.width);
  const depthScale = basisLength(basis.depth);
  const heightScale = basisLength(basis.height);
  const widthDepthArea = Math.abs(
    basis.width.horizontalMm * basis.depth.verticalMm -
    basis.width.verticalMm * basis.depth.horizontalMm
  );
  return {
    widthScale,
    depthScale,
    heightScale,
    normalizedWidthDepthArea: widthDepthArea / Math.max(1e-12, widthScale * depthScale)
  };
}

export function projectIsometricPoint(
  point: Vec3,
  frame: IsometricProjectionFrame = ISOMETRIC_PROJECTION_FRAME
): TechnicalPoint2Mm {
  return projectVector(point, frame);
}
