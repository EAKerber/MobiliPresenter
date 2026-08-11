import assert from "node:assert/strict";
import test from "node:test";
import {
  currentAppearance,
  currentSceneBase,
  currentUnderCabLightContract,
  module06,
  setVisibilityIntent
} from "@mobilipresenter/scene-core";
import { Layers, Mesh, RectAreaLight } from "three";
import { styleAnchorAppearance } from "../dist-ts/src/fixtures/style-anchor.js";
import { BLOOM_LAYER, buildThreeLighting } from "../dist-ts/src/renderer/three/lighting.js";
import { ThreeMaterialRegistry } from "../dist-ts/src/renderer/three/materials.js";
import { buildThreeScene } from "../dist-ts/src/renderer/three/scene-adapter.js";
import { applyFh06UnderCabProfile } from "../dist-ts/src/renderer/three/under-cab-profile.js";

function setup(scene = currentSceneBase) {
  const materials = new ThreeMaterialRegistry(styleAnchorAppearance);
  const adapter = buildThreeScene(scene, (entityId, slot) => materials.resolve(entityId, slot));
  return { materials, adapter };
}

function almost(actual, expected, epsilon = 1e-6) {
  assert.ok(Math.abs(actual - expected) <= epsilon, `${actual} != ${expected}`);
}

test("S7 replaces the legacy LAYER115 box with an 18mm triangular rear-corner profile and opal diffuser", () => {
  const { materials, adapter } = setup();
  const result = applyFh06UnderCabProfile(adapter, materials, currentSceneBase, currentUnderCabLightContract);
  assert.equal(result.profileDefinitionId, "UNDER-CAB-CORNER-18-45-01");
  assert.equal(result.mount, "rear-corner-surface-45deg");
  assert.equal(result.profileAngleDeg, 45);
  assert.deepEqual(result.visualSizeMm, { width: 1200, height: 18, depth: 18 });
  assert.equal(result.colorTemperatureK, 3000);
  assert.equal(result.hasActualAreaLight, true);
  assert.equal(result.bloomIsSupplementary, true);
  assert.deepEqual(result.worldOriginMm, { x: 3879.427, y: 8632.44, z: 1582 });
  almost(result.worldRearTopMm.x, 5079.427);
  almost(result.worldRearTopMm.y, 8650.44);
  almost(result.worldRearTopMm.z, 1600);

  const root = adapter.entityGroups.get(currentUnderCabLightContract.itemId);
  assert.ok(root);
  assert.equal(root.children.length, 3);
  assert.deepEqual(root.userData.legacyEnvelopeMm, { width: 1200, height: 40.91, depth: 32.02 });
  const housing = root.getObjectByName("UNDER-CAB-CORNER-18-45-01/housing");
  const diffuser = root.getObjectByName("UNDER-CAB-CORNER-18-45-01/diffuser");
  const light = root.getObjectByName("UNDER-CAB-CORNER-18-45-01/area-light");
  assert.ok(housing instanceof Mesh);
  assert.equal(housing.geometry.userData.profileCrossSection, "right-triangle-18x18");
  assert.ok(diffuser instanceof Mesh);
  assert.equal(diffuser.geometry.userData.diffuser, "opal-hypotenuse");
  assert.equal(diffuser.geometry.userData.angleDeg, 45);
  assert.ok(light instanceof RectAreaLight);
  assert.equal(light.userData.colorTemperatureK, 3000);
  assert.deepEqual(light.userData.localDirection, currentUnderCabLightContract.emitter.localDirection);
  materials.dispose();
});

test("S7 diffuser may bloom, but an actual RectAreaLight remains the lighting authority", () => {
  const { materials, adapter } = setup();
  applyFh06UnderCabProfile(adapter, materials, currentSceneBase, currentUnderCabLightContract);
  const root = adapter.entityGroups.get(currentUnderCabLightContract.itemId);
  const diffuser = root?.getObjectByName("UNDER-CAB-CORNER-18-45-01/diffuser");
  const light = root?.getObjectByName("UNDER-CAB-CORNER-18-45-01/area-light");
  assert.ok(diffuser && light instanceof RectAreaLight);
  const bloom = new Layers();
  bloom.set(BLOOM_LAYER);
  assert.equal(diffuser.layers.test(bloom), true);
  assert.equal(diffuser.userData.bloomSupplementary, true);
  assert.equal(light.userData.bloomIndependent, true);
  materials.dispose();
});

test("S7 runtime suppresses the legacy under-cab semantic emitter while keeping hood lighting independent", () => {
  const legacy = buildThreeLighting(currentSceneBase, currentAppearance);
  assert.equal(legacy.semanticGroups.size, 2);
  assert.ok([...legacy.semanticGroups.keys()].some(id => id.includes("under-cab-led-06")));

  const runtime = buildThreeLighting(currentSceneBase, styleAnchorAppearance);
  assert.equal(runtime.semanticGroups.size, 1);
  assert.ok([...runtime.semanticGroups.keys()][0].includes("appliance/hood"));
});

test("S7 profile and area light inherit module06 visibility", () => {
  const hiddenScene = setVisibilityIntent(currentSceneBase, module06.id, "off");
  const { materials, adapter } = setup(hiddenScene);
  applyFh06UnderCabProfile(adapter, materials, hiddenScene, currentUnderCabLightContract);
  const root = adapter.entityGroups.get(currentUnderCabLightContract.itemId);
  assert.ok(root);
  assert.equal(root.visible, false);
  assert.ok(root.getObjectByName("UNDER-CAB-CORNER-18-45-01/area-light") instanceof RectAreaLight);
  materials.dispose();
});
