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
const FACING_EPSILON = 1e-9;

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
const BOX_FACE_NORMALS: readonly Vec3[] = [
  { x: 0, y: 0, z: -1 },
  { x: 0, y: 0, z: 1 },
  { x: 0, y: -1, z: 0 },
  { x: 1, y: 0, z: 0 },
  { x: 0, y: 1, z: 0 },
  { x: -1, y: 0, z: 0 }
];
const FACE_EDGES: readonly (readonly [number, number])[] = [
  [0, 1], [1, 2], [2, 3], [3, 0]
];
const FACE_FACES: readonly (readonly number[])[] = [[0, 1, 2, 3]];

export interface TechnicalPrimitiveTopology {
  readonly vertices: readonly Vec3[];
  readonly edges: readonly (readonly [number, number])[];
  readonly faces: readonly (readonly number[])[];
  readonly faceNormals: readonly Vec3[];
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
      faces: BOX_FACES,
      faceNormals: BOX_FACE_NORMALS.map(normal => rotateTechnicalVector(normal, primitive.localTransform))
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
    faces: FACE_FACES,
    faceNormals: [rotateTechnicalVector(primitive.normal, primitive.localTransform)]
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

function localEdgeKey(a: number, b: number): string {
  return a < b ? `${a}|${b}` : `${b}|${a}`;
}

function dot3(a: Vec3, b: Vec3): number {
  return a.x * b.x + a.y * b.y + a.z * b.z;
}

function length3(vector: Vec3): number {
  return Math.hypot(vector.x, vector.y, vector.z);
}

function normalized(vector: Vec3): Vec3 {
  const length = length3(vector);
  if (length <= FACING_EPSILON) {
    throw new Error("TECHNICAL_EDGE_GRAPH_VIEW_DEPTH_DIRECTION_REQUIRED");
  }
  return {
    x: vector.x / length,
    y: vector.y / length,
    z: vector.z / length
  };
}

/**
 * The isometric view-depth function is affine/linear. Sampling the three world
 * basis vectors recovers its camera-facing gradient without coupling this
 * generic topology module to the isometric projection implementation.
 */
function viewDepthDirection(viewDepth: (point: Vec3) => number): Vec3 {
  const origin = viewDepth({ x: 0, y: 0, z: 0 });
  return normalized({
    x: viewDepth({ x: 1, y: 0, z: 0 }) - origin,
    y: viewDepth({ x: 0, y: 1, z: 0 }) - origin,
    z: viewDepth({ x: 0, y: 0, z: 1 }) - origin
  });
}

function incidentFaceNormals(topology: TechnicalPrimitiveTopology): ReadonlyMap<string, readonly Vec3[]> {
  const byEdge = new Map<string, Vec3[]>();
  for (let faceIndex = 0; faceIndex < topology.faces.length; faceIndex += 1) {
    const face = topology.faces[faceIndex]!;
    const normal = topology.faceNormals[faceIndex]!;
    for (let index = 0; index < face.length; index += 1) {
      const a = face[index]!;
      const b = face[(index + 1) % face.length]!;
      const key = localEdgeKey(a, b);
      const normals = byEdge.get(key);
      if (normals) normals.push(normal);
      else byEdge.set(key, [normal]);
    }
  }
  return byEdge;
}

interface EdgeAccumulator {
  readonly key: string;
  readonly start3d: Vec3;
  readonly end3d: Vec3;
  readonly sourcePrimitiveIds: Set<string>;
  readonly sourcePrimitiveRoles: Set<string>;
  readonly incidentFaceNormals: Vec3[];
}

function classifyEdge(edge: EdgeAccumulator, cameraDirection: Vec3): TechnicalProjectedEdgeClass {
  if (edge.incidentFaceNormals.length === 0) return "boundary";

  let facingCount = 0;
  let awayCount = 0;
  let edgeOnCount = 0;

  for (const normal of edge.incidentFaceNormals) {
    const facing = dot3(normal, cameraDirection);
    if (facing > FACING_EPSILON) facingCount += 1;
    else if (facing < -FACING_EPSILON) awayCount += 1;
    else edgeOnCount += 1;
  }

  // An edge with no incident camera-facing surface cannot contribute to the
  // visible technical representation. This is a topology/view statement, not
  // an occlusion decision.
  if (facingCount === 0) return "back-facing";

  // A transition between a camera-facing face and an away/edge-on face is a
  // true primitive silhouette regardless of the world axis of the edge.
  if (awayCount > 0 || edgeOnCount > 0) return "silhouette";

  if (edge.sourcePrimitiveIds.size > 1) return "shared";
  if (edge.incidentFaceNormals.length === 1) return "boundary";
  return "crease";
}

export function buildProjectedTechnicalEdgeGraph(
  primitives: readonly GeometryPrimitive[],
  project: (point: Vec3) => TechnicalPoint2Mm,
  viewDepth: (point: Vec3) => number
): readonly TechnicalProjectedEdge[] {
  const accumulators = new Map<string, EdgeAccumulator>();
  const cameraDirection = viewDepthDirection(viewDepth);

  for (const primitive of primitives) {
    const topology = technicalPrimitiveTopology(primitive);
    const normalsByLocalEdge = incidentFaceNormals(topology);

    for (const [startIndex, endIndex] of topology.edges) {
      const start3d = topology.vertices[startIndex]!;
      const end3d = topology.vertices[endIndex]!;
      const key = edgeKey(start3d, end3d);
      const normals = normalsByLocalEdge.get(localEdgeKey(startIndex, endIndex)) ?? [];
      const existing = accumulators.get(key);

      if (existing) {
        existing.sourcePrimitiveIds.add(primitive.id);
        existing.sourcePrimitiveRoles.add(primitive.role);
        existing.incidentFaceNormals.push(...normals);
        continue;
      }

      accumulators.set(key, {
        key,
        start3d,
        end3d,
        sourcePrimitiveIds: new Set([primitive.id]),
        sourcePrimitiveRoles: new Set([primitive.role]),
        incidentFaceNormals: [...normals]
      });
    }
  }

  return [...accumulators.values()]
    .sort((a, b) => a.key.localeCompare(b.key))
    .map((edge, index) => {
      const projectedStart = project(edge.start3d);
      const projectedEnd = project(edge.end3d);
      return {
        id: `edge-${String(index + 1).padStart(3, "0")}`,
        classification: classifyEdge(edge, cameraDirection),
        startMm: projectedStart,
        endMm: projectedEnd,
        startViewDepth: viewDepth(edge.start3d),
        endViewDepth: viewDepth(edge.end3d),
        sourcePrimitiveIds: [...edge.sourcePrimitiveIds].sort(),
        sourcePrimitiveRoles: [...edge.sourcePrimitiveRoles].sort()
      };
    });
}
