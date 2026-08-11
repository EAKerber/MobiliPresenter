import type { BoxGeometry, ModuleGeometry, ScenePackage } from "../contracts/model.js";
import type { HardwareAnchor } from "../contracts/hardware.js";
import type { Vec3 } from "../core/math.js";
import { applyTransform, composeTransforms } from "../core/math.js";
import { resolveWorldTransforms } from "../state/scene-state.js";

export interface ResolvedHardwareAnchor {
  readonly anchorId: string;
  readonly hostEntityId: string;
  readonly hostGeometryId: string;
  readonly uvMm: readonly [number, number];
  readonly worldMm: Vec3;
  readonly orientation: HardwareAnchor["orientation"];
  readonly hardwareDefinitionId: string;
}

function findFrontBox(scene: ScenePackage, anchor: HardwareAnchor): { module: ModuleGeometry; primitive: BoxGeometry } {
  const module = scene.modules.find(candidate => candidate.id === anchor.hostEntityId);
  if (!module) throw new Error(`HARDWARE_HOST_NOT_FOUND:${anchor.hostEntityId}`);
  const primitive = module.geometry.find(candidate => candidate.id === anchor.hostGeometryId);
  if (!primitive) throw new Error(`HARDWARE_GEOMETRY_NOT_FOUND:${anchor.hostGeometryId}`);
  if (primitive.primitive !== "box" || primitive.role !== "front") {
    throw new Error(`HARDWARE_HOST_MUST_BE_FRONT_BOX:${anchor.hostGeometryId}`);
  }
  return { module, primitive };
}

export function hardwareAnchorUvMm(primitive: BoxGeometry, anchor: HardwareAnchor): readonly [number, number] {
  const width = primitive.sizeMm.width;
  const height = primitive.sizeMm.height;
  let u: number;
  let v: number;
  switch (anchor.placement.type) {
    case "absolute-uv-mm":
      u = anchor.placement.uMm;
      v = anchor.placement.vMm;
      break;
    case "centered":
      u = width / 2;
      v = height / 2;
      break;
    case "edge-offset-mm":
      u = anchor.placement.horizontal.from === "left"
        ? anchor.placement.horizontal.mm
        : width - anchor.placement.horizontal.mm;
      v = anchor.placement.vertical.from === "bottom"
        ? anchor.placement.vertical.mm
        : height - anchor.placement.vertical.mm;
      break;
  }
  if (!(u >= 0 && u <= width && v >= 0 && v <= height)) {
    throw new Error(`HARDWARE_ANCHOR_OUTSIDE_FACE:${anchor.id}`);
  }
  return [u, v];
}

export function resolveHardwareAnchor(scene: ScenePackage, anchor: HardwareAnchor): ResolvedHardwareAnchor {
  const { module, primitive } = findFrontBox(scene, anchor);
  const world = resolveWorldTransforms(scene).get(module.id);
  if (!world) throw new Error(`WORLD_TRANSFORM_NOT_FOUND:${module.id}`);
  const primitiveWorld = composeTransforms(world, primitive.localTransform);
  const [u, v] = hardwareAnchorUvMm(primitive, anchor);
  const worldMm = applyTransform(primitiveWorld, { x: u, y: -anchor.normalOffsetMm, z: v });
  return {
    anchorId: anchor.id,
    hostEntityId: anchor.hostEntityId,
    hostGeometryId: anchor.hostGeometryId,
    uvMm: [u, v],
    worldMm,
    orientation: anchor.orientation,
    hardwareDefinitionId: anchor.hardwareDefinitionId
  };
}

export function resolveHardwareAnchors(
  scene: ScenePackage,
  anchors: readonly HardwareAnchor[]
): readonly ResolvedHardwareAnchor[] {
  const ids = new Set<string>();
  return anchors.map(anchor => {
    if (ids.has(anchor.id)) throw new Error(`HARDWARE_ANCHOR_ID_DUPLICATE:${anchor.id}`);
    ids.add(anchor.id);
    return resolveHardwareAnchor(scene, anchor);
  });
}
