import { STONE02_ID, sceneGeometryDigest, type ScenePackage } from "@mobilipresenter/scene-core";
import { Box3, Group, Mesh, Object3D } from "three";
import type { ThreeSceneAdapter } from "./scene-adapter.js";

const COOKTOP_ID = "scene/traditional/appliance/cooktop";
const STONE_SLAB_MESH_NAME = `${STONE02_ID}/slab/mesh`;
const CONTACT_CLEARANCE_MM = 1;
const EPSILON_MM = 0.001;

function requireObject<T extends Object3D>(value: Object3D | undefined, ctor: new (...args: any[]) => T, code: string): T {
  if (!(value instanceof ctor)) throw new Error(code);
  return value;
}

export interface CooktopContactResult {
  readonly refinementId: "fh06-s10-cooktop-stone-contact-v1";
  readonly contactClearanceMm: number;
  readonly correctionMm: number;
  readonly beforeGapMm: number;
  readonly afterGapMm: number;
  readonly geometryDigestUnchanged: boolean;
}

export function applyFh06CooktopContact(
  adapter: ThreeSceneAdapter,
  scene: ScenePackage
): CooktopContactResult {
  const beforeDigest = sceneGeometryDigest(scene);
  const cooktopGroup = adapter.entityGroups.get(COOKTOP_ID);
  if (!cooktopGroup) throw new Error("S10_COOKTOP_GROUP_MISSING");
  const parametric = requireObject(
    cooktopGroup.getObjectByName(`${COOKTOP_ID}/parametric`),
    Group,
    "S10_COOKTOP_PARAMETRIC_MISSING"
  );
  const visual = parametric.children[0];
  if (!visual) throw new Error("S10_COOKTOP_VISUAL_MISSING");
  const plate = requireObject(visual.children[0], Mesh, "S10_COOKTOP_PLATE_MISSING");

  const stoneGroup = adapter.entityGroups.get(STONE02_ID);
  if (!stoneGroup) throw new Error("S10_STONE02_GROUP_MISSING");
  const slab = requireObject(stoneGroup.getObjectByName(STONE_SLAB_MESH_NAME), Mesh, "S10_STONE02_SLAB_MISSING");

  adapter.scene.updateMatrixWorld(true);
  const slabBounds = new Box3().setFromObject(slab);
  const plateBefore = new Box3().setFromObject(plate);
  const beforeGapMm = plateBefore.min.y - slabBounds.max.y;
  const correctionMm = CONTACT_CLEARANCE_MM - beforeGapMm;
  visual.position.y += correctionMm;
  visual.userData.visualRefinement = "fh06-s10-cooktop-stone-contact-v1";
  visual.userData.contactClearanceMm = CONTACT_CLEARANCE_MM;
  visual.userData.contactCorrectionMm = correctionMm;

  adapter.scene.updateMatrixWorld(true);
  const plateAfter = new Box3().setFromObject(plate);
  const afterGapMm = plateAfter.min.y - slabBounds.max.y;
  if (Math.abs(afterGapMm - CONTACT_CLEARANCE_MM) > EPSILON_MM) {
    throw new Error(`S10_COOKTOP_CONTACT_MISMATCH:${afterGapMm}`);
  }

  const unchanged = sceneGeometryDigest(scene) === beforeDigest;
  if (!unchanged) throw new Error("S10_COOKTOP_MUTATED_SCENE_CORE");
  return {
    refinementId: "fh06-s10-cooktop-stone-contact-v1",
    contactClearanceMm: CONTACT_CLEARANCE_MM,
    correctionMm,
    beforeGapMm,
    afterGapMm,
    geometryDigestUnchanged: unchanged
  };
}
