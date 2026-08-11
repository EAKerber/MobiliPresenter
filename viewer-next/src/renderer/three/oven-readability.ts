import {
  module02,
  sceneGeometryDigest,
  type AppearancePackage,
  type ScenePackage
} from "@mobilipresenter/scene-core";
import {
  BoxGeometry,
  Group,
  Mesh,
  MeshStandardMaterial
} from "three";
import { resolveApplianceFit } from "./appliances.js";
import type { ThreeMaterialRegistry } from "./materials.js";
import type { ThreeSceneAdapter } from "./scene-adapter.js";

const REVEAL_GROUP_NAME = "fh06-s10/module02-oven-reveals";
const REVEAL_DEPTH_MM = 1;
const REVEAL_BEHIND_FRONT_MM = 2;

interface RevealStrip {
  readonly id: "left" | "right" | "bottom" | "top";
  readonly xMm: number;
  readonly zMm: number;
  readonly widthMm: number;
  readonly heightMm: number;
}

function disposeGeometryTree(group: Group): void {
  group.traverse(object => {
    if (object instanceof Mesh) object.geometry.dispose();
  });
}

function ovenRevealStrips(scene: ScenePackage, appearance: AppearancePackage): readonly RevealStrip[] {
  const slot = module02.applianceSlots.find(candidate => candidate.role === "built-in-oven");
  if (!slot?.frontOpening) throw new Error("S10_OVEN_FRONT_OPENING_MISSING");
  const oven = scene.items.find(item => item.definitionId === slot.defaultApplianceId);
  if (!oven) throw new Error("S10_OVEN_ITEM_MISSING");
  const definition = appearance.applianceDefinitions.find(candidate => candidate.id === oven.definitionId);
  if (!definition) throw new Error("S10_OVEN_DEFINITION_MISSING");
  const fit = resolveApplianceFit(scene, oven, definition);

  const opening = slot.frontOpening;
  const slotToOpeningX = slot.localTransform.translationMm.x - opening.localTransform.translationMm.x;
  const slotToOpeningZ = slot.localTransform.translationMm.z - opening.localTransform.translationMm.z;
  const visualX = slotToOpeningX + fit.offsetMm[0];
  const visualZ = slotToOpeningZ + fit.offsetMm[2];
  const left = visualX;
  const right = opening.sizeMm.width - visualX - fit.fittedMm.width;
  const bottom = visualZ;
  const top = opening.sizeMm.height - visualZ - fit.fittedMm.height;
  const epsilon = 1e-9;
  if ([left, right, bottom, top].some(value => value < -epsilon)) {
    throw new Error(`S10_OVEN_REVEAL_NEGATIVE:${left},${right},${bottom},${top}`);
  }

  const ox = opening.localTransform.translationMm.x;
  const oz = opening.localTransform.translationMm.z;
  return [
    { id: "left", xMm: ox, zMm: oz, widthMm: left, heightMm: opening.sizeMm.height },
    { id: "right", xMm: ox + opening.sizeMm.width - right, zMm: oz, widthMm: right, heightMm: opening.sizeMm.height },
    { id: "bottom", xMm: ox + left, zMm: oz, widthMm: fit.fittedMm.width, heightMm: bottom },
    { id: "top", xMm: ox + left, zMm: oz + opening.sizeMm.height - top, widthMm: fit.fittedMm.width, heightMm: top }
  ];
}

export interface OvenReadabilityResult {
  readonly refinementId: "fh06-s10-oven-physical-reveal-v1";
  readonly physicalClearanceMm: readonly [number, number, number, number];
  readonly revealBehindFrontMm: number;
  readonly geometryDigestUnchanged: boolean;
}

export function applyFh06OvenReadability(
  adapter: ThreeSceneAdapter,
  registry: ThreeMaterialRegistry,
  scene: ScenePackage,
  appearance: AppearancePackage
): OvenReadabilityResult {
  const before = sceneGeometryDigest(scene);
  const moduleGroup = adapter.entityGroups.get(module02.id);
  if (!moduleGroup) throw new Error("S10_MODULE02_GROUP_MISSING");
  const old = moduleGroup.getObjectByName(REVEAL_GROUP_NAME);
  if (old instanceof Group) {
    disposeGeometryTree(old);
    moduleGroup.remove(old);
  }

  const frontMaterial = registry.resolve(module02.id, "front") as MeshStandardMaterial;
  const revealMaterial = frontMaterial.clone();
  revealMaterial.name = "fh06-s10/module02-oven-reveal-shadow";
  revealMaterial.color.multiplyScalar(0.22);
  revealMaterial.roughness = 0.96;
  revealMaterial.metalness = 0;

  const strips = ovenRevealStrips(scene, appearance);
  const group = new Group();
  group.name = REVEAL_GROUP_NAME;
  group.userData.appearanceOnly = true;
  group.userData.physicalClearancePreserved = true;
  group.userData.revealBehindFrontMm = REVEAL_BEHIND_FRONT_MM;

  const opening = module02.applianceSlots.find(candidate => candidate.role === "built-in-oven")!.frontOpening!;
  const yMm = opening.localTransform.translationMm.y + REVEAL_BEHIND_FRONT_MM;
  for (const strip of strips) {
    const mesh = new Mesh(
      new BoxGeometry(strip.widthMm, strip.heightMm, REVEAL_DEPTH_MM),
      revealMaterial
    );
    mesh.name = `${REVEAL_GROUP_NAME}/${strip.id}`;
    mesh.position.set(
      strip.xMm + strip.widthMm / 2,
      strip.zMm + strip.heightMm / 2,
      -(yMm + REVEAL_DEPTH_MM / 2)
    );
    mesh.receiveShadow = true;
    mesh.userData.physicalClearanceMm = strip.id === "left" || strip.id === "right" ? strip.widthMm : strip.heightMm;
    mesh.userData.recessBehindFrontMm = REVEAL_BEHIND_FRONT_MM;
    group.add(mesh);
  }
  moduleGroup.add(group);

  const clearance = [
    strips.find(strip => strip.id === "left")!.widthMm,
    strips.find(strip => strip.id === "right")!.widthMm,
    strips.find(strip => strip.id === "bottom")!.heightMm,
    strips.find(strip => strip.id === "top")!.heightMm
  ] as const;
  const unchanged = sceneGeometryDigest(scene) === before;
  if (!unchanged) throw new Error("S10_OVEN_REVEAL_MUTATED_SCENE_CORE");
  return {
    refinementId: "fh06-s10-oven-physical-reveal-v1",
    physicalClearanceMm: clearance,
    revealBehindFrontMm: REVEAL_BEHIND_FRONT_MM,
    geometryDigestUnchanged: unchanged
  };
}
