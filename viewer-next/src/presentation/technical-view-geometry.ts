import type {
  GeometryPrimitive,
  ModuleGeometry,
  Vec3
} from "@mobilipresenter/scene-core";
import type {
  CompiledTechnicalViewGeometry,
  TechnicalPoint2Mm,
  TechnicalProjectedDimensionGuide,
  TechnicalProjectedEdge,
  TechnicalProjectedOpening,
  TechnicalProjectedPrimitive,
  TechnicalViewProjection,
  TechnicalViewRequest
} from "./contracts.js";
import {
  buildProjectedTechnicalEdgeGraph,
  technicalPrimitivePoints3d,
  transformTechnicalPoint
} from "./technical-edge-graph.js";
import { projectIsometricPoint } from "./technical-isometric.js";

const EPSILON = 1e-6;

type Point2 = readonly [number, number];

function projectionForView(view: TechnicalViewRequest): TechnicalViewProjection {
  if (view.kind === "isometric") return "isometric";
  if (!view.plane) throw new Error(`TECHNICAL_VIEW_GEOMETRY_PLANE_REQUIRED:${view.id}`);
  return view.plane;
}

function projectPoint(point: Vec3, projection: TechnicalViewProjection): Point2 {
  switch (projection) {
    case "width-height": return [point.x, point.z];
    case "depth-height": return [point.y, point.z];
    case "width-depth": return [point.x, point.y];
    case "isometric": {
      const projected = projectIsometricPoint(point);
      return [projected.horizontalMm, projected.verticalMm];
    }
  }
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

function projectPrimitive(
  primitive: GeometryPrimitive,
  projection: TechnicalViewProjection
): TechnicalProjectedPrimitive | null {
  const hull = convexHull(technicalPrimitivePoints3d(primitive).map(point => projectPoint(point, projection)));
  if (hull.length < 3) return null;
  return {
    id: primitive.id,
    role: primitive.role,
    pointsMm: hull.map(toTechnicalPoint),
    sourceBindingIds: primitive.sourceBindingIds
  };
}

function openingPoints3d(module: ModuleGeometry): readonly {
  readonly id: string;
  readonly slotId: string;
  readonly role: string;
  readonly status: "confirmed" | "inferred";
  readonly evidenceRefs: readonly string[];
  readonly points: readonly Vec3[];
}[] {
  return module.applianceSlots.flatMap(slot => {
    const opening = slot.frontOpening;
    if (!opening) return [];
    const { width, height } = opening.sizeMm;
    const points = [
      { x: 0, y: 0, z: 0 },
      { x: width, y: 0, z: 0 },
      { x: width, y: 0, z: height },
      { x: 0, y: 0, z: height }
    ].map(point => transformTechnicalPoint(point, opening.localTransform));
    return [{
      id: `${slot.id}/front-opening`,
      slotId: slot.id,
      role: slot.role,
      status: opening.status ?? slot.status ?? "inferred",
      evidenceRefs: opening.evidenceRefs ?? slot.evidenceRefs ?? [],
      points
    }];
  });
}

function projectOpenings(
  module: ModuleGeometry,
  projection: TechnicalViewProjection
): readonly TechnicalProjectedOpening[] {
  return openingPoints3d(module).flatMap(opening => {
    const hull = convexHull(opening.points.map(point => projectPoint(point, projection)));
    if (hull.length < 3) return [];
    return [{
      id: opening.id,
      slotId: opening.slotId,
      role: opening.role,
      pointsMm: hull.map(toTechnicalPoint),
      status: opening.status,
      evidenceRefs: opening.evidenceRefs
    } satisfies TechnicalProjectedOpening];
  });
}

function projectDimensionGuides(
  module: ModuleGeometry,
  projection: TechnicalViewProjection
): readonly TechnicalProjectedDimensionGuide[] {
  if (projection !== "isometric") return [];
  const { width, height, depth } = module.dimensions.geometryMm;
  const frames = [
    { axis: "width" as const, start: { x: 0, y: 0, z: 0 }, end: { x: width, y: 0, z: 0 } },
    { axis: "depth" as const, start: { x: width, y: 0, z: 0 }, end: { x: width, y: depth, z: 0 } },
    { axis: "height" as const, start: { x: 0, y: 0, z: 0 }, end: { x: 0, y: 0, z: height } }
  ];
  return frames.map(frame => ({
    axis: frame.axis,
    startMm: toTechnicalPoint(projectPoint(frame.start, projection)),
    endMm: toTechnicalPoint(projectPoint(frame.end, projection))
  }));
}

function canDeriveGeometry(view: TechnicalViewRequest): boolean {
  if (view.source === "scene-geometry") return true;
  if (view.source !== "scene-envelope") return false;
  return view.kind === "orthographic" || view.kind === "isometric";
}

function primitiveSet(
  module: ModuleGeometry,
  view: TechnicalViewRequest,
  projection: TechnicalViewProjection
): readonly GeometryPrimitive[] {
  if (projection === "width-height" && view.source === "scene-geometry") {
    return module.geometry.filter(primitive => primitive.role === "front");
  }
  return module.geometry;
}

function projectionExtents(
  primitives: readonly TechnicalProjectedPrimitive[],
  openings: readonly TechnicalProjectedOpening[]
): { readonly minHorizontal: number; readonly maxHorizontal: number; readonly minVertical: number; readonly maxVertical: number } {
  const points = [
    ...primitives.flatMap(primitive => primitive.pointsMm),
    ...openings.flatMap(opening => opening.pointsMm)
  ];
  if (points.length === 0) throw new Error("TECHNICAL_VIEW_GEOMETRY_EMPTY");
  return {
    minHorizontal: Math.min(...points.map(point => point.horizontalMm)),
    maxHorizontal: Math.max(...points.map(point => point.horizontalMm)),
    minVertical: Math.min(...points.map(point => point.verticalMm)),
    maxVertical: Math.max(...points.map(point => point.verticalMm))
  };
}

function translatePoint(point: TechnicalPoint2Mm, dx: number, dy: number): TechnicalPoint2Mm {
  return {
    horizontalMm: point.horizontalMm + dx,
    verticalMm: point.verticalMm + dy
  };
}

function translatePoints(
  points: readonly TechnicalPoint2Mm[],
  dx: number,
  dy: number
): readonly TechnicalPoint2Mm[] {
  return points.map(point => translatePoint(point, dx, dy));
}

function normalizeProjection(
  primitives: readonly TechnicalProjectedPrimitive[],
  openings: readonly TechnicalProjectedOpening[],
  dimensionGuides: readonly TechnicalProjectedDimensionGuide[],
  edges: readonly TechnicalProjectedEdge[],
  extents: ReturnType<typeof projectionExtents>
): {
  readonly primitives: readonly TechnicalProjectedPrimitive[];
  readonly openings: readonly TechnicalProjectedOpening[];
  readonly dimensionGuides: readonly TechnicalProjectedDimensionGuide[];
  readonly edges: readonly TechnicalProjectedEdge[];
} {
  const dx = -extents.minHorizontal;
  const dy = -extents.minVertical;
  return {
    primitives: primitives.map(primitive => ({
      ...primitive,
      pointsMm: translatePoints(primitive.pointsMm, dx, dy)
    })),
    openings: openings.map(opening => ({
      ...opening,
      pointsMm: translatePoints(opening.pointsMm, dx, dy)
    })),
    dimensionGuides: dimensionGuides.map(guide => ({
      ...guide,
      startMm: translatePoint(guide.startMm, dx, dy),
      endMm: translatePoint(guide.endMm, dx, dy)
    })),
    edges: edges.map(edge => ({
      ...edge,
      startMm: translatePoint(edge.startMm, dx, dy),
      endMm: translatePoint(edge.endMm, dx, dy)
    }))
  };
}

export function compileGeometryDerivedTechnicalView(
  module: ModuleGeometry,
  view: TechnicalViewRequest
): CompiledTechnicalViewGeometry {
  if (!canDeriveGeometry(view)) throw new Error(`TECHNICAL_VIEW_NOT_GEOMETRY_DERIVABLE:${view.id}:${view.source}`);
  const projection = projectionForView(view);
  const sourcePrimitives = primitiveSet(module, view, projection);
  const rawPrimitives = sourcePrimitives
    .map(primitive => projectPrimitive(primitive, projection))
    .filter((primitive): primitive is TechnicalProjectedPrimitive => primitive !== null);
  const rawOpenings = projectOpenings(module, projection);
  const rawDimensionGuides = projectDimensionGuides(module, projection);
  const rawEdges = projection === "isometric"
    ? buildProjectedTechnicalEdgeGraph(sourcePrimitives, projectIsometricPoint)
    : [];
  const extents = projectionExtents(rawPrimitives, rawOpenings);

  const preserveFrontDatum = projection === "width-height";
  const projected = preserveFrontDatum
    ? {
        primitives: rawPrimitives,
        openings: rawOpenings,
        dimensionGuides: rawDimensionGuides,
        edges: rawEdges
      }
    : normalizeProjection(rawPrimitives, rawOpenings, rawDimensionGuides, rawEdges, extents);
  const boundsMm = preserveFrontDatum
    ? {
        horizontal: module.dimensions.geometryMm.width,
        vertical: module.dimensions.geometryMm.height
      }
    : {
        horizontal: extents.maxHorizontal - extents.minHorizontal,
        vertical: extents.maxVertical - extents.minVertical
      };

  const frontOnly = projection === "width-height" && view.source === "scene-geometry";
  return {
    viewId: view.id,
    projection,
    coordinateUnit: "mm",
    boundsMm,
    primitives: projected.primitives,
    openings: projected.openings,
    dimensionGuides: projected.dimensionGuides,
    edges: projected.edges,
    coverage: [
      frontOnly ? "module-front-primitives" : "module-geometry-primitives",
      ...(projected.openings.length > 0 ? ["appliance-front-openings" as const] : [])
    ],
    omitted: frontOnly
      ? ["hardware", "hidden-geometry"]
      : ["hardware", "hidden-line-removal"]
  };
}

export function compileGeometryDerivedTechnicalViews(
  module: ModuleGeometry,
  views: readonly TechnicalViewRequest[]
): readonly CompiledTechnicalViewGeometry[] {
  return views
    .filter(canDeriveGeometry)
    .map(view => compileGeometryDerivedTechnicalView(module, view));
}
