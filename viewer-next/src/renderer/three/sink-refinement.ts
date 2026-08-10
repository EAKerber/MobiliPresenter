import type { SceneItem, ScenePackage } from "@mobilipresenter/scene-core";
import {
  Box3,
  BoxGeometry,
  CatmullRomCurve3,
  Group,
  Mesh,
  MeshStandardMaterial,
  TubeGeometry,
  Vector3,
  type Material
} from "three";
import { RoundedBoxGeometry } from "three/examples/jsm/geometries/RoundedBoxGeometry.js";
import type { ThreeSceneAdapter } from "./scene-adapter.js";
import type { ThreeMaterialRegistry } from "./materials.js";

const SINK_ITEM_ID = "scene/traditional/fixture/kitchen-sink";
const SINK_STONE_ID = "scene/traditional/accessory/sink-countertop";
const SINK_STONE_PRIMITIVE_ID = "scene/traditional/accessory/sink-countertop/slab";
const RENDER_AABB_TOLERANCE_MM = 0.001;

interface FitData {
  readonly fittedMm: { readonly width: number; readonly height: number; readonly depth: number };
  readonly offsetMm: readonly [number, number, number];
}

function part(
  width: number,
  height: number,
  depth: number,
  material: Material,
  x: number,
  y: number,
  z: number,
  rounded = 0
): Mesh {
  const geometry = rounded > 0
    ? new RoundedBoxGeometry(width, height, depth, 3, Math.min(rounded, width / 4, height / 4, depth / 4))
    : new BoxGeometry(width, height, depth);
  const mesh = new Mesh(geometry, material);
  mesh.position.set(x + width / 2, z + height / 2, -(y + depth / 2));
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  return mesh;
}

function itemById(scene: ScenePackage, id: string): SceneItem {
  const item = scene.items.find(candidate => candidate.id === id);
  if (!item) throw new Error(`SINK_REFINEMENT_ITEM_MISSING:${id}`);
  return item;
}

function splitCountertopAroundSink(
  adapter: ThreeSceneAdapter,
  scene: ScenePackage
): { outerBefore: Box3; outerAfter: Box3; openingMm: readonly [number, number, number, number] } {
  const stoneItem = itemById(scene, SINK_STONE_ID);
  const sinkItem = itemById(scene, SINK_ITEM_ID);
  if (!stoneItem.geometry?.length) throw new Error("SINK_COUNTERTOP_GEOMETRY_MISSING");
  if (!sinkItem.hostId || !sinkItem.slotId) throw new Error("SINK_SLOT_REFERENCE_MISSING");
  const host = scene.modules.find(module => module.id === sinkItem.hostId);
  if (!host) throw new Error("SINK_HOST_MODULE_MISSING");
  const slot = host.applianceSlots.find(candidate => candidate.id === sinkItem.slotId);
  if (!slot) throw new Error("SINK_SLOT_MISSING");

  const primitive = stoneItem.geometry.find(candidate => candidate.id === SINK_STONE_PRIMITIVE_ID);
  if (!primitive || primitive.primitive !== "box") throw new Error("SINK_COUNTERTOP_BOX_MISSING");
  const group = adapter.entityGroups.get(stoneItem.id);
  if (!group) throw new Error("SINK_COUNTERTOP_GROUP_MISSING");
  const primitiveGroup = group.getObjectByName(primitive.id);
  if (!(primitiveGroup instanceof Group)) throw new Error("SINK_COUNTERTOP_PRIMITIVE_GROUP_MISSING");
  const original = primitiveGroup.getObjectByName(`${primitive.id}/mesh`);
  if (!(original instanceof Mesh)) throw new Error("SINK_COUNTERTOP_MESH_MISSING");
  primitiveGroup.updateWorldMatrix(true, true);
  const outerBefore = new Box3().setFromObject(primitiveGroup);
  const stoneMaterial = original.material as Material;

  const openingX = slot.localTransform.translationMm.x - stoneItem.transform.translationMm.x;
  const openingY = slot.localTransform.translationMm.y - stoneItem.transform.translationMm.y;
  const openingWidth = slot.clearSizeMm.width;
  const openingDepth = slot.clearSizeMm.depth;
  const slabWidth = primitive.sizeMm.width;
  const slabDepth = primitive.sizeMm.depth;
  const slabHeight = primitive.sizeMm.height;
  const rightStart = openingX + openingWidth;
  const backStart = openingY + openingDepth;
  if (openingX < 0 || openingY < 0 || rightStart > slabWidth || backStart > slabDepth) {
    throw new Error("SINK_CUTOUT_OUTSIDE_COUNTERTOP");
  }

  group.remove(primitiveGroup);
  original.geometry.dispose();

  const cutout = new Group();
  cutout.name = `${stoneItem.id}/visual-cutout`;
  cutout.userData.visualRefinement = "fh06-stone-cutout-v1";
  cutout.userData.openingMm = [openingX, openingY, openingWidth, openingDepth];
  // Interim FH-06 cutout preserves the authoritative local dimensions exactly.
  // Rounded stone edges return in S2-S4. GPU BufferGeometry uses float attributes,
  // so world-space AABB comparison is measured and gated rather than assumed exact.
  if (openingX > 0) cutout.add(part(openingX, slabHeight, slabDepth, stoneMaterial, 0, 0, 0));
  if (slabWidth - rightStart > 0) cutout.add(part(slabWidth - rightStart, slabHeight, slabDepth, stoneMaterial, rightStart, 0, 0));
  if (openingY > 0) cutout.add(part(openingWidth, slabHeight, openingY, stoneMaterial, openingX, 0, 0));
  if (slabDepth - backStart > 0) cutout.add(part(openingWidth, slabHeight, slabDepth - backStart, stoneMaterial, openingX, backStart, 0));
  group.add(cutout);
  group.updateWorldMatrix(true, true);
  const outerAfter = new Box3().setFromObject(cutout);
  return { outerBefore, outerAfter, openingMm: [openingX, openingY, openingWidth, openingDepth] };
}

function rebuildSink(
  adapter: ThreeSceneAdapter,
  registry: ThreeMaterialRegistry
): { proxy: Group; faucetHeightMm: number } {
  const entity = adapter.entityGroups.get(SINK_ITEM_ID);
  if (!entity) throw new Error("SINK_ENTITY_GROUP_MISSING");
  const proxy = entity.getObjectByName(`${SINK_ITEM_ID}/parametric`) as Group | undefined;
  if (!proxy) throw new Error("SINK_PROXY_MISSING");
  const fit = proxy.userData.fit as FitData | undefined;
  if (!fit) throw new Error("SINK_FIT_MISSING");

  const { width, height, depth } = fit.fittedMm;
  const inox = registry.materialByDefinitionId("inox-brushed") as MeshStandardMaterial;
  const chrome = registry.materialByDefinitionId("chrome") as MeshStandardMaterial;
  proxy.clear();

  const visual = new Group();
  visual.name = `${SINK_ITEM_ID}/visual`;
  visual.position.set(fit.offsetMm[0], fit.offsetMm[2], -fit.offsetMm[1]);
  const rim = 9;
  const bowlInset = 18;
  const topZ = height - rim;
  visual.add(part(width, rim, rim, inox, 0, 0, topZ, 3));
  visual.add(part(width, rim, rim, inox, 0, depth - rim, topZ, 3));
  visual.add(part(rim, rim, depth - 2 * rim, inox, 0, rim, topZ, 3));
  visual.add(part(rim, rim, depth - 2 * rim, inox, width - rim, rim, topZ, 3));

  const wallHeight = Math.max(40, height * 0.68);
  visual.add(part(7, wallHeight, depth - 2 * bowlInset, inox, bowlInset, bowlInset, topZ - wallHeight, 2));
  visual.add(part(7, wallHeight, depth - 2 * bowlInset, inox, width - bowlInset - 7, bowlInset, topZ - wallHeight, 2));
  visual.add(part(width - 2 * bowlInset, wallHeight, 7, inox, bowlInset, depth - bowlInset - 7, topZ - wallHeight, 2));
  visual.add(part(width - 2 * bowlInset, 8, depth - 2 * bowlInset, inox, bowlInset, bowlInset, Math.max(4, topZ - wallHeight), 10));

  const faucetX = width * 0.78;
  const faucetBack = -depth * 0.91;
  const baseY = height + 2;
  const faucetRise = 220;
  const curve = new CatmullRomCurve3([
    new Vector3(faucetX, baseY, faucetBack),
    new Vector3(faucetX, baseY + 90, faucetBack),
    new Vector3(faucetX, baseY + 180, faucetBack + 18),
    new Vector3(faucetX, baseY + faucetRise, faucetBack + 92),
    new Vector3(faucetX, baseY + 185, faucetBack + 165)
  ]);
  const faucet = new Mesh(new TubeGeometry(curve, 32, 6, 12, false), chrome);
  faucet.castShadow = true;
  visual.add(faucet);
  visual.add(part(26, 18, 22, chrome, faucetX - 13, depth * 0.77, height - 6, 5));

  proxy.add(visual);
  proxy.userData.visualRefinement = "fh06-sink-and-faucet-v1";
  proxy.userData.faucetRiseMm = faucetRise;
  return { proxy, faucetHeightMm: faucetRise };
}

function maxAabbDriftMm(before: Box3, after: Box3): number {
  return Math.max(
    Math.abs(before.min.x - after.min.x),
    Math.abs(before.min.y - after.min.y),
    Math.abs(before.min.z - after.min.z),
    Math.abs(before.max.x - after.max.x),
    Math.abs(before.max.y - after.max.y),
    Math.abs(before.max.z - after.max.z)
  );
}

export interface SinkRefinementResult {
  readonly openingMm: readonly [number, number, number, number];
  readonly countertopOuterEnvelopePreserved: boolean;
  readonly countertopOuterEnvelopeDriftMm: number;
  readonly countertopOuterEnvelopeToleranceMm: number;
  readonly faucetHeightMm: number;
}

export function applyFh06SinkRefinement(
  adapter: ThreeSceneAdapter,
  registry: ThreeMaterialRegistry,
  scene: ScenePackage
): SinkRefinementResult {
  const stone = splitCountertopAroundSink(adapter, scene);
  const sink = rebuildSink(adapter, registry);
  const driftMm = maxAabbDriftMm(stone.outerBefore, stone.outerAfter);
  return {
    openingMm: stone.openingMm,
    countertopOuterEnvelopePreserved: driftMm <= RENDER_AABB_TOLERANCE_MM,
    countertopOuterEnvelopeDriftMm: driftMm,
    countertopOuterEnvelopeToleranceMm: RENDER_AABB_TOLERANCE_MM,
    faucetHeightMm: sink.faucetHeightMm
  };
}
