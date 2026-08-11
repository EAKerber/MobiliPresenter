import { module03WithSink, sceneGeometryDigest, type BoxGeometry, type ScenePackage } from "@mobilipresenter/scene-core";
import {
  BoxGeometry as ThreeBoxGeometry,
  Group,
  Mesh,
  MeshStandardMaterial
} from "three";
import { RoundedBoxGeometry } from "three/examples/jsm/geometries/RoundedBoxGeometry.js";
import { applyCabinetFrontEdgeResponse } from "./cabinet-front-edge.js";
import type { ThreeMaterialRegistry } from "./materials.js";
import type { ThreeSceneAdapter } from "./scene-adapter.js";

const DRAWER_PREFIX = "scene/traditional/module/lower-sink/front/drawer-";
const REVEAL_GROUP_NAME = "fh06-s8/module03-drawer-reveals";
const BEVEL_MM = 1.25;
const REVEAL_DEPTH_MM = 1;
const REVEAL_BEHIND_FRONT_MM = 2;
const EXPECTED_GAP_MM = 2;

interface DrawerPrimitive extends BoxGeometry {
  readonly primitive: "box";
}

interface DrawerSeam {
  readonly xMm: number;
  readonly widthMm: number;
  readonly zMm: number;
  readonly heightMm: number;
  readonly yMm: number;
}

function drawerPrimitives(): readonly DrawerPrimitive[] {
  return module03WithSink.geometry
    .filter((primitive): primitive is DrawerPrimitive =>
      primitive.primitive === "box" && primitive.id.startsWith(DRAWER_PREFIX)
    )
    .sort((a, b) => b.localTransform.translationMm.z - a.localTransform.translationMm.z);
}

function drawerSeams(drawers: readonly DrawerPrimitive[]): readonly DrawerSeam[] {
  const seams: DrawerSeam[] = [];
  for (let index = 0; index < drawers.length - 1; index++) {
    const upper = drawers[index]!;
    const lower = drawers[index + 1]!;
    const upperBottom = upper.localTransform.translationMm.z;
    const lowerTop = lower.localTransform.translationMm.z + lower.sizeMm.height;
    const gap = upperBottom - lowerTop;
    const x0 = Math.max(upper.localTransform.translationMm.x, lower.localTransform.translationMm.x);
    const x1 = Math.min(
      upper.localTransform.translationMm.x + upper.sizeMm.width,
      lower.localTransform.translationMm.x + lower.sizeMm.width
    );
    seams.push({
      xMm: x0,
      widthMm: x1 - x0,
      zMm: lowerTop,
      heightMm: gap,
      yMm: upper.localTransform.translationMm.y + REVEAL_BEHIND_FRONT_MM
    });
  }
  return seams;
}

function disposeGeometryTree(group: Group): void {
  group.traverse(object => {
    if (object instanceof Mesh) object.geometry.dispose();
  });
}

function replaceDrawerGeometry(adapter: ThreeSceneAdapter, drawers: readonly DrawerPrimitive[]): void {
  const moduleGroup = adapter.entityGroups.get(module03WithSink.id);
  if (!moduleGroup) throw new Error("S8_MODULE03_GROUP_MISSING");
  for (const primitive of drawers) {
    const primitiveGroup = moduleGroup.getObjectByName(primitive.id);
    if (!(primitiveGroup instanceof Group)) throw new Error(`S8_DRAWER_GROUP_MISSING:${primitive.id}`);
    const mesh = primitiveGroup.getObjectByName(`${primitive.id}/mesh`);
    if (!(mesh instanceof Mesh)) throw new Error(`S8_DRAWER_MESH_MISSING:${primitive.id}`);
    mesh.geometry.dispose();
    const geometry = new RoundedBoxGeometry(
      primitive.sizeMm.width,
      primitive.sizeMm.height,
      primitive.sizeMm.depth,
      3,
      BEVEL_MM
    );
    geometry.userData.visualRefinement = "fh06-s8-front-bevel-v1";
    geometry.userData.bevelMm = BEVEL_MM;
    geometry.userData.authoritativeSizeMm = { ...primitive.sizeMm };
    mesh.geometry = geometry;
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    mesh.userData.visualRefinement = "fh06-s8-front-bevel-v1";
  }
}

function createRevealGroup(
  adapter: ThreeSceneAdapter,
  registry: ThreeMaterialRegistry,
  seams: readonly DrawerSeam[]
): Group {
  const moduleGroup = adapter.entityGroups.get(module03WithSink.id);
  if (!moduleGroup) throw new Error("S8_MODULE03_GROUP_MISSING");
  const old = moduleGroup.getObjectByName(REVEAL_GROUP_NAME);
  if (old instanceof Group) {
    disposeGeometryTree(old);
    moduleGroup.remove(old);
  }

  const frontMaterial = registry.resolve(module03WithSink.id, "front") as MeshStandardMaterial;
  const revealMaterial = frontMaterial.clone();
  revealMaterial.name = "fh06-s8/module03-reveal-shadow";
  revealMaterial.color.multiplyScalar(0.28);
  revealMaterial.roughness = 0.95;
  revealMaterial.metalness = 0;

  const group = new Group();
  group.name = REVEAL_GROUP_NAME;
  group.userData.appearanceOnly = true;
  group.userData.physicalGapPreserved = true;
  group.userData.revealBehindFrontMm = REVEAL_BEHIND_FRONT_MM;

  seams.forEach((seam, index) => {
    const mesh = new Mesh(
      new ThreeBoxGeometry(seam.widthMm, seam.heightMm, REVEAL_DEPTH_MM),
      revealMaterial
    );
    mesh.name = `${REVEAL_GROUP_NAME}/${index + 1}`;
    mesh.position.set(
      seam.xMm + seam.widthMm / 2,
      seam.zMm + seam.heightMm / 2,
      -(seam.yMm + REVEAL_DEPTH_MM / 2)
    );
    mesh.receiveShadow = true;
    mesh.userData.physicalGapMm = seam.heightMm;
    mesh.userData.recessBehindFrontMm = REVEAL_BEHIND_FRONT_MM;
    group.add(mesh);
  });
  moduleGroup.add(group);
  return group;
}

export interface FrontReadabilityResult {
  readonly refinementId: "module03-drawer-bevel-recess-v1";
  readonly drawerCount: number;
  readonly seamCount: number;
  readonly bevelMm: number;
  readonly physicalGapMm: readonly number[];
  readonly revealBehindFrontMm: number;
  readonly geometryDigestUnchanged: boolean;
}

export function applyFh06FrontReadability(
  adapter: ThreeSceneAdapter,
  registry: ThreeMaterialRegistry,
  scene: ScenePackage
): FrontReadabilityResult {
  const before = sceneGeometryDigest(scene);
  const drawers = drawerPrimitives();
  if (drawers.length !== 4) throw new Error(`S8_DRAWER_COUNT:${drawers.length}`);
  const seams = drawerSeams(drawers);
  if (seams.some(seam => Math.abs(seam.heightMm - EXPECTED_GAP_MM) > 1e-9)) {
    throw new Error(`S8_PHYSICAL_GAP_CHANGED:${seams.map(seam => seam.heightMm).join(",")}`);
  }
  replaceDrawerGeometry(adapter, drawers);
  createRevealGroup(adapter, registry, seams);
  applyCabinetFrontEdgeResponse(adapter, scene);
  const unchanged = sceneGeometryDigest(scene) === before;
  if (!unchanged) throw new Error("S8_MUTATED_SCENE_CORE_GEOMETRY");
  return {
    refinementId: "module03-drawer-bevel-recess-v1",
    drawerCount: drawers.length,
    seamCount: seams.length,
    bevelMm: BEVEL_MM,
    physicalGapMm: seams.map(seam => seam.heightMm),
    revealBehindFrontMm: REVEAL_BEHIND_FRONT_MM,
    geometryDigestUnchanged: unchanged
  };
}
