import type {
  GeometryPrimitive,
  Vec3
} from "@mobilipresenter/scene-core";
import type {
  TechnicalPoint2Mm,
  TechnicalProjectedEdge,
  TechnicalVisibilityInterval
} from "./contracts.js";
import { technicalPrimitiveTopology } from "./technical-edge-graph.js";

export const TECHNICAL_VISIBILITY_VERSION = "technical-visibility/v0.1" as const;

const EPSILON = 1e-7;
const DEPTH_EPSILON_MM = 1e-4;

interface ProjectedDepthPoint extends TechnicalPoint2Mm {
  readonly viewDepth: number;
}

interface ProjectedSurface {
  readonly id: string;
  readonly sourcePrimitiveId: string;
  readonly sourcePrimitiveRole: string;
  readonly points: readonly ProjectedDepthPoint[];
}

function cross2(
  ax: number,
  ay: number,
  bx: number,
  by: number
): number {
  return ax * by - ay * bx;
}

function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

function interpolatePoint(
  start: TechnicalPoint2Mm,
  end: TechnicalPoint2Mm,
  t: number
): TechnicalPoint2Mm {
  return {
    horizontalMm: lerp(start.horizontalMm, end.horizontalMm, t),
    verticalMm: lerp(start.verticalMm, end.verticalMm, t)
  };
}

function polygonArea(points: readonly ProjectedDepthPoint[]): number {
  let twiceArea = 0;
  for (let index = 0; index < points.length; index += 1) {
    const a = points[index]!;
    const b = points[(index + 1) % points.length]!;
    twiceArea += a.horizontalMm * b.verticalMm - a.verticalMm * b.horizontalMm;
  }
  return twiceArea / 2;
}

function buildProjectedSurfaces(
  primitives: readonly GeometryPrimitive[],
  project: (point: Vec3) => TechnicalPoint2Mm,
  viewDepth: (point: Vec3) => number
): readonly ProjectedSurface[] {
  const surfaces: ProjectedSurface[] = [];
  for (const primitive of primitives) {
    const topology = technicalPrimitiveTopology(primitive);
    for (let faceIndex = 0; faceIndex < topology.faces.length; faceIndex += 1) {
      const face = topology.faces[faceIndex]!;
      const points = face.map(vertexIndex => {
        const vertex = topology.vertices[vertexIndex]!;
        return {
          ...project(vertex),
          viewDepth: viewDepth(vertex)
        };
      });
      if (Math.abs(polygonArea(points)) <= EPSILON) continue;
      surfaces.push({
        id: `${primitive.id}/visibility-face-${faceIndex + 1}`,
        sourcePrimitiveId: primitive.id,
        sourcePrimitiveRole: primitive.role,
        points
      });
    }
  }
  return surfaces;
}

function segmentBoundaryIntersectionParameter(
  lineStart: TechnicalPoint2Mm,
  lineEnd: TechnicalPoint2Mm,
  edgeStart: TechnicalPoint2Mm,
  edgeEnd: TechnicalPoint2Mm
): number | null {
  const rx = lineEnd.horizontalMm - lineStart.horizontalMm;
  const ry = lineEnd.verticalMm - lineStart.verticalMm;
  const sx = edgeEnd.horizontalMm - edgeStart.horizontalMm;
  const sy = edgeEnd.verticalMm - edgeStart.verticalMm;
  const denominator = cross2(rx, ry, sx, sy);
  if (Math.abs(denominator) <= EPSILON) return null;

  const qpx = edgeStart.horizontalMm - lineStart.horizontalMm;
  const qpy = edgeStart.verticalMm - lineStart.verticalMm;
  const t = cross2(qpx, qpy, sx, sy) / denominator;
  const u = cross2(qpx, qpy, rx, ry) / denominator;
  if (t <= EPSILON || t >= 1 - EPSILON) return null;
  if (u < -EPSILON || u > 1 + EPSILON) return null;
  return t;
}

function triangleDepthAt(
  point: TechnicalPoint2Mm,
  a: ProjectedDepthPoint,
  b: ProjectedDepthPoint,
  c: ProjectedDepthPoint
): number | null {
  const abx = b.horizontalMm - a.horizontalMm;
  const aby = b.verticalMm - a.verticalMm;
  const acx = c.horizontalMm - a.horizontalMm;
  const acy = c.verticalMm - a.verticalMm;
  const apx = point.horizontalMm - a.horizontalMm;
  const apy = point.verticalMm - a.verticalMm;
  const denominator = cross2(abx, aby, acx, acy);
  if (Math.abs(denominator) <= EPSILON) return null;

  const weightB = cross2(apx, apy, acx, acy) / denominator;
  const weightC = cross2(abx, aby, apx, apy) / denominator;
  const weightA = 1 - weightB - weightC;
  if (weightA < -EPSILON || weightB < -EPSILON || weightC < -EPSILON) return null;

  return (
    weightA * a.viewDepth +
    weightB * b.viewDepth +
    weightC * c.viewDepth
  );
}

function surfaceDepthAt(
  surface: ProjectedSurface,
  point: TechnicalPoint2Mm
): number | null {
  const anchor = surface.points[0];
  if (!anchor) return null;
  for (let index = 1; index < surface.points.length - 1; index += 1) {
    const depth = triangleDepthAt(
      point,
      anchor,
      surface.points[index]!,
      surface.points[index + 1]!
    );
    if (depth !== null) return depth;
  }
  return null;
}

function uniqueSorted(values: readonly number[]): number[] {
  const sorted = [...values].sort((a, b) => a - b);
  const result: number[] = [];
  for (const value of sorted) {
    if (result.length === 0 || Math.abs(value - result[result.length - 1]!) > EPSILON) {
      result.push(value);
    }
  }
  return result;
}

function intervalVisible(
  edge: TechnicalProjectedEdge,
  startT: number,
  endT: number,
  surfaces: readonly ProjectedSurface[]
): boolean {
  const midpointT = (startT + endT) / 2;
  const point = interpolatePoint(edge.startMm, edge.endMm, midpointT);
  const lineDepth = lerp(edge.startViewDepth, edge.endViewDepth, midpointT);

  for (const surface of surfaces) {
    const surfaceDepth = surfaceDepthAt(surface, point);
    if (surfaceDepth === null) continue;
    if (surfaceDepth > lineDepth + DEPTH_EPSILON_MM) return false;
  }
  return true;
}

function visibleIntervalsForEdge(
  edge: TechnicalProjectedEdge,
  surfaces: readonly ProjectedSurface[]
): readonly TechnicalVisibilityInterval[] {
  const breakpoints: number[] = [0, 1];

  for (const surface of surfaces) {
    for (let index = 0; index < surface.points.length; index += 1) {
      const start = surface.points[index]!;
      const end = surface.points[(index + 1) % surface.points.length]!;
      const t = segmentBoundaryIntersectionParameter(edge.startMm, edge.endMm, start, end);
      if (t !== null) breakpoints.push(t);
    }
  }

  const sorted = uniqueSorted(breakpoints);
  const visible: TechnicalVisibilityInterval[] = [];
  for (let index = 0; index < sorted.length - 1; index += 1) {
    const startT = sorted[index]!;
    const endT = sorted[index + 1]!;
    if (endT - startT <= EPSILON) continue;
    if (!intervalVisible(edge, startT, endT, surfaces)) continue;

    const previous = visible[visible.length - 1];
    if (previous && Math.abs(previous.endT - startT) <= EPSILON) {
      visible[visible.length - 1] = {
        startT: previous.startT,
        endT
      };
    } else {
      visible.push({ startT, endT });
    }
  }
  return visible;
}

export function resolveTechnicalEdgeVisibility(
  primitives: readonly GeometryPrimitive[],
  edges: readonly TechnicalProjectedEdge[],
  project: (point: Vec3) => TechnicalPoint2Mm,
  viewDepth: (point: Vec3) => number
): readonly TechnicalProjectedEdge[] {
  const surfaces = buildProjectedSurfaces(primitives, project, viewDepth);
  if (surfaces.length === 0) return edges;

  return edges.map(edge => ({
    ...edge,
    visibleIntervals: visibleIntervalsForEdge(edge, surfaces)
  }));
}
