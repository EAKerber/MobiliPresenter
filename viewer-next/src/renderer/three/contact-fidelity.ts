import { STONE02_ID, type ScenePackage } from "@mobilipresenter/scene-core";
import { Box3, Object3D } from "three";
import type { ThreeSceneAdapter } from "./scene-adapter.js";

export interface ContactMeasurement {
  readonly id: string;
  readonly lowerEntityId: string;
  readonly upperEntityId: string;
  readonly axis: "three-y-scene-z";
  readonly measuredGapMm: number;
  readonly expectedGapMm: number;
  readonly toleranceMm: number;
  readonly pass: boolean;
}

function bounds(object: Object3D): Box3 {
  object.updateWorldMatrix(true, true);
  const result = new Box3().setFromObject(object);
  if (result.isEmpty()) throw new Error(`CONTACT_FIDELITY_EMPTY_BOUNDS:${object.name}`);
  return result;
}

export function measureVerticalContactGap(
  id: string,
  lowerEntityId: string,
  lowerObject: Object3D,
  upperEntityId: string,
  upperObject: Object3D,
  expectedGapMm: number,
  toleranceMm = 0.01
): ContactMeasurement {
  const lower = bounds(lowerObject);
  const upper = bounds(upperObject);
  const measuredGapMm = upper.min.y - lower.max.y;
  return {
    id,
    lowerEntityId,
    upperEntityId,
    axis: "three-y-scene-z",
    measuredGapMm,
    expectedGapMm,
    toleranceMm,
    pass: Math.abs(measuredGapMm - expectedGapMm) <= toleranceMm
  };
}

export function measureCurrentCooktopStoneContact(
  adapter: ThreeSceneAdapter,
  scene: ScenePackage,
  expectedGapMm = 1
): ContactMeasurement {
  const cooktop = scene.items.find(item => item.definitionId === "AP-COOKTOP-01");
  if (!cooktop) throw new Error("CONTACT_FIDELITY_COOKTOP_ITEM_MISSING");
  const stoneGroup = adapter.entityGroups.get(STONE02_ID);
  const cooktopGroup = adapter.entityGroups.get(cooktop.id);
  if (!stoneGroup || !cooktopGroup) throw new Error("CONTACT_FIDELITY_ENTITY_GROUP_MISSING");
  const slab = stoneGroup.getObjectByName(`${STONE02_ID}/slab`);
  const visual = cooktopGroup.getObjectByName(`${cooktop.id}/parametric`);
  if (!slab || !visual) throw new Error("CONTACT_FIDELITY_RENDER_OBJECT_MISSING");
  return measureVerticalContactGap(
    "contact/cooktop/stone-02",
    STONE02_ID,
    slab,
    cooktop.id,
    visual,
    expectedGapMm,
    0.01
  );
}
