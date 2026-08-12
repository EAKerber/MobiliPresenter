import type {
  GeometryPrimitive,
  ModuleGeometry,
  RigidTransform,
  Vec3
} from "@mobilipresenter/scene-core";
import type {
  CompiledTechnicalViewGeometry,
  TechnicalPoint2Mm,
  TechnicalProjectedOpening,
  TechnicalProjectedPrimitive,
  TechnicalViewRequest
} from "./contracts.js";

const EPSILON = 1e-6;

type Point2 = readonly [number, number];

function rotateVector(vector: Vec3, transform: RigidTransform): Vec3 {
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

function transformPoint(point: Vec3, transform: RigidTransform): Vec3 {
  const rotated = rotateVector(point, transform);
  return {
    x: rotated.x + transform.translationMm.x,
    y: rotated.y + transform.translationMm.y,
    z: rotated.z + transform.translationMm.z
  };
}

function uniquePoints(points: readonly Point2[]): Point2[] {
  const result: Point2[] = [];
  for (const point of points) {
    if (!result.some(existing => Math.abs(existing[0] - point[0]) < EPSILON && Math.abs(existing[1] - point[1]) < EPSILON)) {
      result.push(point);
    }
  }
  return result;
}

function cross(origin: Point2, a: Point2, b: Point2): number {
  return (a[0] - origin[0]) * (b[1] - origin[1]) - (a[1] - origin[1]) * (b[0] - origin[0]);
}

function convexHull(points: readonly Point2[]): Point2[] {
  const sorted = uniquePoints(points).sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  if (sorted.length <= 2) return sorted;

  const lower: Point2[] = [];
  for (const point of sorted) {
    while (lower.length >= 2 && cross(lower[lower.length - 2]!, lower[lower.length - 1]!, point) <= EPSILON) lower.pop();
    lower.push(point);
  }

  const upper: Point2[] = [];
  for (let index = sorted.length - 1; index >= 0; index -= 1) {
    const point = sorted[index]!;
    while (upper.length >= 2 && cross(upper[upper.length - 2]!, upper[upper.length - 1]!, point) <= EPSILON) upper.pop();
    upper.push(point);
  }

  lower.pop();
  upper.pop();
  return [...lower, ...upper];
}

function toTechnicalPoint(point: Point2): TechnicalPoint2Mm {
  return { horizontalMm: point[0], verticalMm: point[1] };
}

function projectPrimitive(primitive: GeometryPrimitive): TechnicalProjectedPrimitive | null {
  const points3d: Vec3[] = [];
  if (primitive.primitive === "box") {
    const { width, height, depth } = primitive.sizeMm;
    for (const x of [0, width]) {
      for (const y of [0, depth]) {
        for (const z of [0, height]) points3d.push(transformPoint({ x, y, z }, primitive.localTransform));
      }
    }
  } else {
    const [uMm, vMm] = primitive.sizeMm;
    for (const u of [0, uMm]) {
      for (const v of [0, vMm]) {
        points3d.push(transformPoint({
          x: primitive.uAxis.x * u + primitive.vAxis.x * v,
          y: primitive.uAxis.y * u + primitive.vAxis.y * v,
          z: primitive.uAxis.z * u + primitive.vAxis.z * v
        }, primitive.localTransform));
      }
    }
  }

  const hull = convexHull(points3d.map(point => [point.x, point.z] as const));
  if (hull.length < 3) return null;
  return {
    id: primitive.id,
    role: primitive.role,
    pointsMm: hull.map(toTechnicalPoint),
    sourceBindingIds: primitive.sourceBindingIds
  };
}

function projectOpenings(module: ModuleGeometry): readonly TechnicalProjectedOpening[] {
  return module.applianceSlots.flatMap(slot => {
    const opening = slot.frontOpening;
    if (!opening) return [];
    const { width, height } = opening.sizeMm;
    const points = [
      { x: 0, y: 0, z: 0 },
      { x: width, y: 0, z: 0 },
      { x: width, y: 0, z: height },
      { x: 0, y: 0, z: height }
    ].map(point => transformPoint(point, opening.localTransform));
    return [{
      id: `${slot.id}/front-opening`,
      slotId: slot.id,
      role: slot.role,
      pointsMm: convexHull(points.map(point => [point.x, point.z] as const)).map(toTechnicalPoint),
      status: opening.status ?? slot.status ?? "inferred",
      evidenceRefs: opening.evidenceRefs ?? slot.evidenceRefs ?? []
    } satisfies TechnicalProjectedOpening];
  });
}

export function compileGeometryDerivedTechnicalView(
  module: ModuleGeometry,
  view: TechnicalViewRequest
): CompiledTechnicalViewGeometry {
  if (view.source !== "scene-geometry") throw new Error(`TECHNICAL_VIEW_NOT_GEOMETRY_DERIVED:${view.id}`);
  if (view.plane !== "width-height") throw new Error(`TECHNICAL_VIEW_GEOMETRY_PLANE_UNSUPPORTED:${view.id}:${view.plane ?? "none"}`);

  const primitives = module.geometry
    .filter(primitive => primitive.role === "front")
    .map(projectPrimitive)
    .filter((primitive): primitive is TechnicalProjectedPrimitive => primitive !== null);

  return {
    viewId: view.id,
    plane: view.plane,
    coordinateUnit: "mm",
    boundsMm: {
      horizontal: module.dimensions.geometryMm.width,
      vertical: module.dimensions.geometryMm.height
    },
    primitives,
    openings: projectOpenings(module),
    coverage: ["module-front-primitives", "appliance-front-openings"],
    omitted: ["hardware", "hidden-geometry"]
  };
}

export function compileGeometryDerivedTechnicalViews(
  module: ModuleGeometry,
  views: readonly TechnicalViewRequest[]
): readonly CompiledTechnicalViewGeometry[] {
  return views
    .filter(view => view.source === "scene-geometry")
    .map(view => compileGeometryDerivedTechnicalView(module, view));
}
