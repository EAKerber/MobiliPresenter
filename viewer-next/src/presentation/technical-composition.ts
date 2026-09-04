import type { TechnicalAxis } from "./contracts.js";

export type TechnicalCompositionRegion =
  | "top"
  | "right"
  | "bottom"
  | "left"
  | "top-right"
  | "bottom-right"
  | "bottom-left"
  | "top-left";

export interface TechnicalCompositionPoint {
  readonly x: number;
  readonly y: number;
}

export interface TechnicalCompositionBox {
  readonly left: number;
  readonly top: number;
  readonly right: number;
  readonly bottom: number;
}

export interface TechnicalCompositionGuide {
  readonly axis: TechnicalAxis;
  readonly start: TechnicalCompositionPoint;
  readonly end: TechnicalCompositionPoint;
}

export interface TechnicalDimensionPlacement {
  readonly semanticKey: string;
  readonly source: "scene-geometry";
  readonly scope: "overall";
  readonly axis: TechnicalAxis;
  readonly valueMm: number;
  readonly region: TechnicalCompositionRegion;
  readonly lane: number;
  readonly offset: number;
  readonly start: TechnicalCompositionPoint;
  readonly end: TechnicalCompositionPoint;
  readonly shiftedStart: TechnicalCompositionPoint;
  readonly shiftedEnd: TechnicalCompositionPoint;
  readonly labelCenter: TechnicalCompositionPoint;
  readonly labelBox: TechnicalCompositionBox;
}

export interface TechnicalCompositionPlan {
  readonly version: "technical-composition/v0.3";
  readonly dimensions: readonly TechnicalDimensionPlacement[];
  readonly occupiedRegions: readonly TechnicalCompositionRegion[];
}

const AXIS_ORDER: readonly TechnicalAxis[] = ["height", "width", "depth"];
const REGION_PREFERENCES: Readonly<Record<TechnicalAxis, readonly TechnicalCompositionRegion[]>> = {
  height: ["left", "right", "top-left", "bottom-left"],
  width: ["bottom", "top", "bottom-left", "bottom-right"],
  depth: ["right", "bottom-right", "bottom", "top-right"]
};
const REGION_NORMALS: Readonly<Record<TechnicalCompositionRegion, TechnicalCompositionPoint>> = {
  top: { x: 0, y: -1 },
  right: { x: 1, y: 0 },
  bottom: { x: 0, y: 1 },
  left: { x: -1, y: 0 },
  "top-right": normalize({ x: 1, y: -1 }),
  "bottom-right": normalize({ x: 1, y: 1 }),
  "bottom-left": normalize({ x: -1, y: 1 }),
  "top-left": normalize({ x: -1, y: -1 })
};

function normalize(point: TechnicalCompositionPoint): TechnicalCompositionPoint {
  const length = Math.hypot(point.x, point.y);
  if (length < 1e-9) return { x: 0, y: 0 };
  return { x: point.x / length, y: point.y / length };
}

function translate(point: TechnicalCompositionPoint, normal: TechnicalCompositionPoint, distance: number): TechnicalCompositionPoint {
  return { x: point.x + normal.x * distance, y: point.y + normal.y * distance };
}

function midpoint(a: TechnicalCompositionPoint, b: TechnicalCompositionPoint): TechnicalCompositionPoint {
  return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
}

function estimateLabelBox(center: TechnicalCompositionPoint, label: string): TechnicalCompositionBox {
  const halfWidth = Math.max(16, label.length * 3.35);
  return {
    left: center.x - halfWidth,
    right: center.x + halfWidth,
    top: center.y - 8,
    bottom: center.y + 7
  };
}

function inflate(box: TechnicalCompositionBox, padding: number): TechnicalCompositionBox {
  return {
    left: box.left - padding,
    right: box.right + padding,
    top: box.top - padding,
    bottom: box.bottom + padding
  };
}

export function technicalCompositionBoxesIntersect(
  a: TechnicalCompositionBox,
  b: TechnicalCompositionBox,
  padding = 0
): boolean {
  return !(
    a.right + padding < b.left ||
    b.right + padding < a.left ||
    a.bottom + padding < b.top ||
    b.bottom + padding < a.top
  );
}

function insideViewBox(
  box: TechnicalCompositionBox,
  viewBox: { readonly width: number; readonly height: number },
  margin = 4
): boolean {
  return box.left >= margin && box.top >= margin && box.right <= viewBox.width - margin && box.bottom <= viewBox.height - margin;
}

function labelFor(valueMm: number): string {
  const value = Number.isInteger(valueMm) ? String(valueMm) : String(Number(valueMm.toFixed(3)));
  return `${value} mm`;
}

function validateGuides(guides: readonly TechnicalCompositionGuide[]): Map<TechnicalAxis, TechnicalCompositionGuide> {
  const byAxis = new Map<TechnicalAxis, TechnicalCompositionGuide>();
  for (const guide of guides) {
    if (byAxis.has(guide.axis)) {
      throw new Error(`TECHNICAL_COMPOSITION_DUPLICATE_DIMENSION:overall/${guide.axis}`);
    }
    byAxis.set(guide.axis, guide);
  }
  for (const axis of AXIS_ORDER) {
    if (!byAxis.has(axis)) throw new Error(`TECHNICAL_COMPOSITION_REQUIRED_AXIS_MISSING:${axis}`);
  }
  return byAxis;
}

export function planIsometricDimensions(input: {
  readonly guides: readonly TechnicalCompositionGuide[];
  readonly valuesMm: Readonly<Record<TechnicalAxis, number>>;
  readonly geometryBox: TechnicalCompositionBox;
  readonly viewBox: { readonly width: number; readonly height: number };
  readonly maxLanesPerRegion?: number;
}): TechnicalCompositionPlan {
  const guides = validateGuides(input.guides);
  const occupiedLabels: TechnicalCompositionBox[] = [];
  const occupiedRegions: TechnicalCompositionRegion[] = [];
  const dimensions: TechnicalDimensionPlacement[] = [];
  const geometryExclusion = inflate(input.geometryBox, 8);
  const maxLanes = input.maxLanesPerRegion ?? 5;

  for (const axis of AXIS_ORDER) {
    const guide = guides.get(axis)!;
    const valueMm = input.valuesMm[axis];
    if (!Number.isFinite(valueMm) || valueMm <= 0) {
      throw new Error(`TECHNICAL_COMPOSITION_INVALID_DIMENSION:overall/${axis}:${valueMm}`);
    }
    const semanticKey = `overall/${axis}`;
    const label = labelFor(valueMm);
    let placement: TechnicalDimensionPlacement | null = null;

    for (const region of REGION_PREFERENCES[axis]) {
      const normal = REGION_NORMALS[region];
      for (let lane = 0; lane < maxLanes; lane += 1) {
        const baseOffset = axis === "height" ? 28 : 30;
        const offset = baseOffset + lane * 16;
        const shiftedStart = translate(guide.start, normal, offset);
        const shiftedEnd = translate(guide.end, normal, offset);
        const labelCenter = translate(midpoint(shiftedStart, shiftedEnd), normal, 10);
        const labelBox = estimateLabelBox(labelCenter, label);

        if (!insideViewBox(labelBox, input.viewBox)) continue;
        if (technicalCompositionBoxesIntersect(labelBox, geometryExclusion)) continue;
        if (occupiedLabels.some(existing => technicalCompositionBoxesIntersect(labelBox, existing, 4))) continue;

        placement = {
          semanticKey,
          source: "scene-geometry",
          scope: "overall",
          axis,
          valueMm,
          region,
          lane,
          offset,
          start: guide.start,
          end: guide.end,
          shiftedStart,
          shiftedEnd,
          labelCenter,
          labelBox
        };
        break;
      }
      if (placement) break;
    }

    if (!placement) throw new Error(`TECHNICAL_COMPOSITION_UNPLACEABLE_DIMENSION:${semanticKey}`);
    dimensions.push(placement);
    occupiedLabels.push(placement.labelBox);
    if (!occupiedRegions.includes(placement.region)) occupiedRegions.push(placement.region);
  }

  return {
    version: "technical-composition/v0.3",
    dimensions,
    occupiedRegions
  };
}
