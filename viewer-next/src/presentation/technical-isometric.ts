import type { Vec3 } from "@mobilipresenter/scene-core";
import type { TechnicalPoint2Mm } from "./contracts.js";

export interface TechnicalProjectionBasisVector {
  readonly horizontalMm: number;
  readonly verticalMm: number;
}

export interface IsometricProjectionBasis {
  readonly width: TechnicalProjectionBasisVector;
  readonly depth: TechnicalProjectionBasisVector;
  readonly height: TechnicalProjectionBasisVector;
}

/**
 * Projection coordinates use technical vertical-up space.
 * The SVG renderer flips verticalMm into screen-y, so a positive depth.verticalMm
 * moves the back plane upward on screen: depth recedes from the frontal datum.
 */
export const ISOMETRIC_PROJECTION_BASIS: IsometricProjectionBasis = {
  width: { horizontalMm: 1, verticalMm: -0.28 },
  depth: { horizontalMm: -0.62, verticalMm: 0.28 },
  height: { horizontalMm: 0, verticalMm: 1 }
};

export function projectIsometricPoint(
  point: Vec3,
  basis: IsometricProjectionBasis = ISOMETRIC_PROJECTION_BASIS
): TechnicalPoint2Mm {
  return {
    horizontalMm:
      point.x * basis.width.horizontalMm +
      point.y * basis.depth.horizontalMm +
      point.z * basis.height.horizontalMm,
    verticalMm:
      point.x * basis.width.verticalMm +
      point.y * basis.depth.verticalMm +
      point.z * basis.height.verticalMm
  };
}

export function isometricDepthRecedes(
  basis: IsometricProjectionBasis = ISOMETRIC_PROJECTION_BASIS
): boolean {
  return basis.depth.verticalMm > 0;
}
