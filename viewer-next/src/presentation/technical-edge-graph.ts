import type {
  GeometryPrimitive,
  RigidTransform,
  Vec3
} from "@mobilipresenter/scene-core";
import type {
  TechnicalPoint2Mm,
  TechnicalProjectedEdge,
  TechnicalProjectedEdgeClass
} from "./contracts.js";

const EPSILON = 1e-6;
const BOX_EDGES: readonly (readonly [number, number])[] = [
  [0, 1], [1, 2], [2, 3], [3, 0],
  [4, 5], [5, 6], [6, 7], [7, 4],
  [0, 4], [1, 5], [2, 6], [3, 7]
];
const BOX_FACES: readonly (readonly number[])[] = [
  [0, 1, 2, 3],
  [4, 5, 6, 7],
  [0, 1, 5, 4],
  [1, 2, 6, 5],
  [2, 3, 7, 6],
  [3, 0, 4, 7]
];
const FACE_EDGES: readonly (readonly [number, number])[] = [
  [0, 1], [1, 2], [2, 3], [3, 0]
];
const FACE_FACES: readonly (readonly number[])[] = [[0, 1, 2, 3]];

export interface TechnicalPrimitiveTopology {
  readonly vertices: readonly Vec3[];
  readonly edges: readonly (readonly [number, number])[];
  readonly faces: readonly (readonly number[])[];
}

export function rotateTechnicalVector(vector: Vec3, transform: RigidTransform): Vec3 {
  const q = transform.rotation;
  const tx = 2 * (q.y * vector.z - q.z * vector.y);
  const ty = 2 * (q.z * vector.x - q.x * vector.z);
  const tz = 2 * (q.x * vector.y - q.y * vector.x);
  return {
    x: vector.x + q.w * tx + (q.y * tz - q.z * ty),
    y: vector.y + q.w * ty + (q.z * tx - q.x * tz),
    z: vector.z + q.w * tz + (q.x * ty - q.y * tx)
  };
}

export function transformTechnicalPoint(point: Vec3, transform: RigidTransform): Vec3 {
  const rotated = rotateTechnicalVector(point, transform);
  return {
    x: rotated.x + transform.translationMm.x,
    y: rotated.y + transform.translationMm.y,
    z: rotated.z + transform.translationMm.z
  };
}

export function technicalPrimitiveTopology(primitive: GeometryPrimitive): TechnicalPrimitiveTopology {
  if (primitive.primitive === "box") {
    const { width, height, depth } = primitive.sizeMm;
    const local = [
      { x: 0, y: 0, z: 0 },
      { x: width, y: 0, z: 0 },
      { x: width, y: depth, z: 0 },
      { x: 0, y: depth, z: 0 },
      { x: 0, y: 0, z: height },
      { x: width, y: 0, z: height },
      { x: width, y: depth, z: height },
      { x: 0, y: depth, z: height }
    ];
    return {
      vertices: local.map(point => transformTechnicalPoint(point, primitive.localTransform)),
      edges: BOX_EDGES,
      faces: BOX_FACES
    };
  }

  const [uMm, vMm] = primitive.sizeMm;
  const local = [
    { x: 0, y: 0, z: 0 },
    {
      x: primitive.uAxis.x * uMm,
      y: primitive.uAxis.y * uMm,
      z: primitive.uAxis.z * uMm
    },
    {
      x: primitive.uAxis.x * uMm + primitive.vAxis.x * vMm,
      y: primitive.uAxis.y * uMm + primitive.vAxis.y * vMm,
      z: primitive.uAxis.z * uMm + primitive.vAxis.z * vMm
    },
    {
      x: primitive.vAxis.x * vMm,
      y: primitive.vAxis.y * vMm,
      z: primitive.vAxis.z * vMm
    }
  ];
  return {
    vertices: local.map(point => transformTechnicalPoint(point, primitive.localTransform)),
    edges: FACE_EDGES,
    faces: FACE_FACES
  };
}

export function technicalPrimitivePoints3d(primitive: GeometryPrimitive): readonly Vec3[] {
  return technicalPrimitiveTopology(primitive).vertices;
}

function quantized(value: number): string {
  const normalized = Math.abs(value) < EPSILON ? 0 : value;
  return normalized.toFixed(6);
}

function pointKey(point: Vec3): string {
  return `${quantized(point.x)},${quantized(point.y)},${quantized(point.z)}`;
}

function edgeKey(a: Vec3, b: Vec3): string {
  const ak = pointKey(a);
  const bk = pointKey(b);
  return ak < bk ? `${ak}|${bk}` : `${bk}|${ak}`;
}

function samePoint(a: TechnicalPoint2Mm, b: TechnicalPoint2Mm): boolean {
  return (
    Math.abs(a.horizontalMm - b.horizontalMm) < EPSILON &&
    Math.abs(a.verticalMm - b.verticalMm) < EPSILON
  );
}

function cross(origin: TechnicalPoint2Mm, a: TechnicalPoint2Mm, b: TechnicalPoint2Mm): number {
  return (
    (a.horizontalMm - origin.horizontalMm) * (b.verticalMm - origin.verticalMm) -
    (a.verticalMm - origin.verticalMm) * (b.horizontalMm - origin.horizontalMm)
  );
}

function uniqueProjectedPoints(points: readonly TechnicalPoint2Mm[]): TechnicalPoint2Mm[] {
  const result: TechnicalPoint2Mm[] = [];
  for (const point of points) {
    if (!result.some(existing => samePoint(existing, point))) result.push(point);
  }
  return result;
}

function convexHull(points: readonly TechnicalPoint2Mm[]): TechnicalPoint2Mm[] {
  const sorted = uniqueProjectedPoints(points).sort(
    (a, b) => a.horizontalMm - b.horizontalMm || a.verticalMm - b.verticalMm
  );
  if (sorted.length <= 2) return sorted;

  const lower: TechnicalPoint2Mm[] = [];
  for (const point of sorted) {
    while (
      lower.length >= 2 &&
      cross(lower[lower.length - 2]!, lower[lower.length - 1]!, point) <= EPSILON
    ) lower.pop();
    lower.push(point);
  }

  const upper: TechnicalPoint2Mm[] = [];
  for (let index = sorted.length - 1; index >= 0; index -= 1) {
    const point = sorted[index]!;
    while (
      upper.length >= 2 &&
      cross(upper[upper.length - 2]!, upper[upper.length - 1]!, point) <= EPSILON
    ) upper.pop();
    upper.push(point);
  }

  lower.pop();
  upper.pop();
  return [...lower, ...upper];
}

function pointOnSegment(
  point: TechnicalPoint2Mm,
  start: TechnicalPoint2Mm,
  end: TechnicalPoint2Mm
): boolean {
  if (Math.abs(cross(start, end, point)) > EPSILON) return false;
  return (
    point.horizontalMm >= Math.min(start.horizontalMm, end.horizontalMm) - EPSILON &&
    point.horizontalMm <= Math.max(start.horizontalMm, end.horizontalMm) + EPSILON &&
    point.verticalMm >= Math.min(start.verticalMm, end.verticalMm) - EPSILON &&
    point.verticalMm <= Math.max(start.verticalMm, end.verticalMm) + EPSILON
  );
}

function edgeOnHull(
  start: TechnicalPoint2Mm,
  end: TechnicalPoint2Mm,
  hull: readonly TechnicalPoint2Mm[]
): boolean {
  if (hull.length < 2) return false;
  for (let index = 0; index < hull.length; index += 1) {
    const a = hull[index]!;
    const b = hull[(index + 1) % hull.length]!;
    if (pointOnSegment(start, a, b) && pointOnSegment(end, a, b)) return true;
  }
  return false;
}

function near(value: number, target: number): boolean {
  return Math.abs(value - target) < EPSILON;
}

interface EdgeAccumulator {
  readonly key: string;
  readonly start3d: Vec3;
  readonly end3d: Vec3;
  readonly sourcePrimitiveIds: Set<string>;
  readonly sourcePrimitiveRoles: Set<string>;
}

function classifyEdge(input: {
  readonly edge: EdgeAccumulator;
  readonly projectedStart: TechnicalPoint2Mm;
  readonly projectedEnd: TechnicalPoint2Mm;
  readonly hull: readonly TechnicalPoint2Mm[];
  readonly minDepth: number;
  readonly maxDepth: number;
}): TechnicalProjectedEdgeClass {
  const { edge, projectedStart, projectedEnd, hull, minDepth, maxDepth } = input;
  if (edgeOnHull(projectedStart, projectedEnd, hull)) return "silhouette";
  if (near(edge.start3d.y, minDepth) && near(edge.end3d.y, minDepth)) return "front";
  if (near(edge.start3d.y, maxDepth) && near(edge.end3d.y, maxDepth)) return "back";
  if (!near(edge.start3d.y, edge.end3d.y)) return "depth";
  if (edge.sourcePrimitiveIds.size > 1) return "shared";
  return "internal";
}

export function buildProjectedTechnicalEdgeGraph(
  primitives: readonly GeometryPrimitive[],
  project: (point: Vec3) => TechnicalPoint2Mm,
  viewDepth: (point: Vec3) => number = () => 0
): readonly TechnicalProjectedEdge[] {
  const accumulators = new Map<string, EdgeAccumulator>();
  const allVertices: Vec3[] = [];

  for (const primitive of primitives) {
    const topology = technicalPrimitiveTopology(primitive);
    allVertices.push(...topology.vertices);
    for (const [startIndex, endIndex] of topology.edges) {
      const start3d = topology.vertices[startIndex]!;
      const end3d = topology.vertices[endIndex]!;
      const key = edgeKey(start3d, end3d);
      const existing = accumulators.get(key);
      if (existing) {
        existing.sourcePrimitiveIds.add(primitive.id);
        existing.sourcePrimitiveRoles.add(primitive.role);
        continue;
      }
      accumulators.set(key, {
        key,
        start3d,
        end3d,
        sourcePrimitiveIds: new Set([primitive.id]),
        sourcePrimitiveRoles: new Set([primitive.role])
      });
    }
  }

  if (allVertices.length === 0) return [];
  const minDepth = Math.min(...allVertices.map(point => point.y));
  const maxDepth = Math.max(...allVertices.map(point => point.y));
  const hull = convexHull(allVertices.map(point => project(point)));

  return [...accumulators.values()]
    .sort((a, b) => a.key.localeCompare(b.key))
    .map((edge, index) => {
      const projectedStart = project(edge.start3d);
      const projectedEnd = project(edge.end3d);
      return {
        id: `edge-${String(index + 1).padStart(3, "0")}`,
        classification: classifyEdge({
          edge,
          projectedStart,
          projectedEnd,
          hull,
          minDepth,
          maxDepth
        }),
        startMm: projectedStart,
        endMm: projectedEnd,
        startViewDepth: viewDepth(edge.start3d),
        endViewDepth: viewDepth(edge.end3d),
        visibleIntervals: [{ startT: 0, endT: 1 }],
        sourcePrimitiveIds: [...edge.sourcePrimitiveIds].sort(),
        sourcePrimitiveRoles: [...edge.sourcePrimitiveRoles].sort()
      };
    });
}
