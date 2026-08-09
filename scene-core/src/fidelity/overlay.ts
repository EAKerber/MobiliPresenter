import type { Aabb3, RigidTransform, Vec3 } from "../core/math.js";
import { add, applyTransform, composeTransforms, mul } from "../core/math.js";
import type {
  EnvironmentGeometry,
  GeometryPrimitive,
  ModuleGeometry,
  SceneItem,
  ScenePackage
} from "../contracts/model.js";
import {
  allSceneEntities,
  resolveItemPlacementTransform,
  resolveWorldTransforms
} from "../state/scene-state.js";

export type FidelityLineRole =
  | "grid-minor"
  | "grid-major"
  | "aabb"
  | "axis-x"
  | "axis-y"
  | "axis-z"
  | "wireframe"
  | "dimension"
  | "landmark";

export interface FidelityLine3 {
  readonly id: string;
  readonly role: FidelityLineRole;
  readonly aMm: Vec3;
  readonly bMm: Vec3;
  readonly entityId?: string;
  readonly geometryId?: string;
  readonly metricMm?: number;
  readonly status?: "confirmed" | "inferred" | "nominal-only";
}

export interface PlanarMetricGridSpec {
  readonly id: string;
  readonly originMm: Vec3;
  readonly uAxis: Vec3;
  readonly vAxis: Vec3;
  readonly uLengthMm: number;
  readonly vLengthMm: number;
  readonly minorStepMm?: number;
  readonly majorStepMm?: number;
}

const p = (origin: Vec3, uAxis: Vec3, vAxis: Vec3, u: number, v: number): Vec3 =>
  add(origin, add(mul(uAxis, u), mul(vAxis, v)));

export function createPlanarMetricGrid(spec: PlanarMetricGridSpec): readonly FidelityLine3[] {
  const minor = spec.minorStepMm ?? 100;
  const major = spec.majorStepMm ?? 500;
  if (!(spec.uLengthMm > 0 && spec.vLengthMm > 0 && minor > 0 && major > 0)) {
    throw new Error("FIDELITY_GRID_INVALID");
  }
  const lines: FidelityLine3[] = [];
  const uCount = Math.floor(spec.uLengthMm / minor + 1e-9);
  const vCount = Math.floor(spec.vLengthMm / minor + 1e-9);
  const majorEvery = Math.max(1, Math.round(major / minor));

  for (let i = 0; i <= uCount; i += 1) {
    const u = Math.min(i * minor, spec.uLengthMm);
    lines.push({
      id: `${spec.id}/u/${i}`,
      role: i % majorEvery === 0 ? "grid-major" : "grid-minor",
      aMm: p(spec.originMm, spec.uAxis, spec.vAxis, u, 0),
      bMm: p(spec.originMm, spec.uAxis, spec.vAxis, u, spec.vLengthMm)
    });
  }
  if (uCount * minor < spec.uLengthMm - 1e-9) {
    lines.push({
      id: `${spec.id}/u/end`, role: "grid-major",
      aMm: p(spec.originMm, spec.uAxis, spec.vAxis, spec.uLengthMm, 0),
      bMm: p(spec.originMm, spec.uAxis, spec.vAxis, spec.uLengthMm, spec.vLengthMm)
    });
  }

  for (let i = 0; i <= vCount; i += 1) {
    const v = Math.min(i * minor, spec.vLengthMm);
    lines.push({
      id: `${spec.id}/v/${i}`,
      role: i % majorEvery === 0 ? "grid-major" : "grid-minor",
      aMm: p(spec.originMm, spec.uAxis, spec.vAxis, 0, v),
      bMm: p(spec.originMm, spec.uAxis, spec.vAxis, spec.uLengthMm, v)
    });
  }
  if (vCount * minor < spec.vLengthMm - 1e-9) {
    lines.push({
      id: `${spec.id}/v/end`, role: "grid-major",
      aMm: p(spec.originMm, spec.uAxis, spec.vAxis, 0, spec.vLengthMm),
      bMm: p(spec.originMm, spec.uAxis, spec.vAxis, spec.uLengthMm, spec.vLengthMm)
    });
  }
  return lines;
}

function aabbCorners(box: Aabb3): readonly Vec3[] {
  const { min, max } = box;
  return [
    { x: min.x, y: min.y, z: min.z }, { x: max.x, y: min.y, z: min.z },
    { x: max.x, y: max.y, z: min.z }, { x: min.x, y: max.y, z: min.z },
    { x: min.x, y: min.y, z: max.z }, { x: max.x, y: min.y, z: max.z },
    { x: max.x, y: max.y, z: max.z }, { x: min.x, y: max.y, z: max.z }
  ];
}

const EDGE_INDICES = [
  [0, 1], [1, 2], [2, 3], [3, 0],
  [4, 5], [5, 6], [6, 7], [7, 4],
  [0, 4], [1, 5], [2, 6], [3, 7]
] as const;

export function createAabbOverlay(
  id: string,
  box: Aabb3,
  transform: RigidTransform,
  entityId?: string,
  status?: FidelityLine3["status"]
): readonly FidelityLine3[] {
  const corners = aabbCorners(box).map(point => applyTransform(transform, point));
  return EDGE_INDICES.map(([a, b], index) => ({
    id: `${id}/edge/${index}`,
    role: "aabb" as const,
    aMm: corners[a]!,
    bMm: corners[b]!,
    entityId,
    status
  }));
}

export function createAxesOverlay(
  id: string,
  transform: RigidTransform,
  lengthMm = 250,
  entityId?: string
): readonly FidelityLine3[] {
  const origin = applyTransform(transform, { x: 0, y: 0, z: 0 });
  const endpoint = (local: Vec3) => applyTransform(transform, local);
  return [
    { id: `${id}/x`, role: "axis-x", aMm: origin, bMm: endpoint({ x: lengthMm, y: 0, z: 0 }), entityId },
    { id: `${id}/y`, role: "axis-y", aMm: origin, bMm: endpoint({ x: 0, y: lengthMm, z: 0 }), entityId },
    { id: `${id}/z`, role: "axis-z", aMm: origin, bMm: endpoint({ x: 0, y: 0, z: lengthMm }), entityId }
  ];
}

function boxWireframe(
  entityId: string,
  primitive: Extract<GeometryPrimitive, { primitive: "box" }>,
  entityTransform: RigidTransform
): readonly FidelityLine3[] {
  const primitiveWorld = composeTransforms(entityTransform, primitive.localTransform);
  const box: Aabb3 = {
    min: { x: 0, y: 0, z: 0 },
    max: { x: primitive.sizeMm.width, y: primitive.sizeMm.depth, z: primitive.sizeMm.height }
  };
  return createAabbOverlay(`${primitive.id}/wire`, box, primitiveWorld, entityId, "confirmed")
    .map(line => ({ ...line, role: "wireframe" as const, geometryId: primitive.id }));
}

function faceWireframe(
  entityId: string,
  primitive: Extract<GeometryPrimitive, { primitive: "face" }>,
  entityTransform: RigidTransform
): readonly FidelityLine3[] {
  const primitiveWorld = composeTransforms(entityTransform, primitive.localTransform);
  const [uMm, vMm] = primitive.sizeMm;
  const local = [
    { x: 0, y: 0, z: 0 },
    mul(primitive.uAxis, uMm),
    add(mul(primitive.uAxis, uMm), mul(primitive.vAxis, vMm)),
    mul(primitive.vAxis, vMm)
  ];
  const points = local.map(point => applyTransform(primitiveWorld, point));
  return [[0, 1], [1, 2], [2, 3], [3, 0]].map(([a, b], index) => ({
    id: `${primitive.id}/wire/${index}`,
    role: "wireframe" as const,
    aMm: points[a]!, bMm: points[b]!, entityId, geometryId: primitive.id,
    status: "confirmed" as const
  }));
}

function geometryOf(entity: EnvironmentGeometry | ModuleGeometry | SceneItem): readonly GeometryPrimitive[] {
  if (entity.kind === "environment" || entity.kind === "module") return entity.geometry;
  return entity.geometry ?? [];
}

export function createSceneWireframe(scene: ScenePackage): readonly FidelityLine3[] {
  const world = resolveWorldTransforms(scene);
  const lines: FidelityLine3[] = [];
  for (const entity of allSceneEntities(scene)) {
    const entityTransform = entity.kind === "appliance" || entity.kind === "fixture" || entity.kind === "accessory"
      ? resolveItemPlacementTransform(scene, entity)
      : world.get(entity.id);
    if (!entityTransform) throw new Error(`WORLD_TRANSFORM_NOT_FOUND:${entity.id}`);
    for (const primitive of geometryOf(entity)) {
      lines.push(...(primitive.primitive === "box"
        ? boxWireframe(entity.id, primitive, entityTransform)
        : faceWireframe(entity.id, primitive, entityTransform)));
    }
  }
  return lines;
}

export function createSceneAabbs(scene: ScenePackage): readonly FidelityLine3[] {
  const world = resolveWorldTransforms(scene);
  const lines: FidelityLine3[] = [];
  for (const entity of [...scene.environment, ...scene.modules]) {
    const transform = world.get(entity.id);
    if (!transform) throw new Error(`WORLD_TRANSFORM_NOT_FOUND:${entity.id}`);
    lines.push(...createAabbOverlay(`${entity.id}/aabb`, entity.structuralEnvelope, transform, entity.id, "confirmed"));
  }
  return lines;
}

export function createDimensionLine(
  id: string,
  aMm: Vec3,
  bMm: Vec3,
  metricMm: number,
  entityId?: string
): FidelityLine3 {
  return { id, role: "dimension", aMm, bMm, metricMm, entityId, status: "confirmed" };
}
