import assert from "node:assert/strict";
import test from "node:test";
import {
  composeTransforms,
  currentAppearance,
  currentSceneBase,
  currentUnderCabLightContract,
  module06,
  resolveWorldTransforms
} from "../dist/src/index.js";

function almost(actual, expected, epsilon = 1e-9) {
  assert.ok(Math.abs(actual - expected) <= epsilon, `${actual} != ${expected}`);
}

test("S7 under-cab contract preserves LAYER115 provenance while defining a stable 18mm rear-corner profile", () => {
  const contract = currentUnderCabLightContract;
  assert.equal(contract.itemId, "scene/traditional/accessory/under-cab-led-06");
  assert.equal(contract.hostModuleId, module06.id);
  assert.equal(contract.profileDefinitionId, "UNDER-CAB-CORNER-18-45-01");
  assert.deepEqual(contract.visualSizeMm, { width: 1200, height: 18, depth: 18 });
  assert.deepEqual(contract.localTransform.translationMm, { x: 0, y: 382, z: -18 });
  assert.equal(contract.mount, "rear-corner-surface-45deg");
  assert.equal(contract.profileAngleDeg, 45);
  assert.equal(contract.diffuser, "opal");
  assert.deepEqual(contract.provenance.legacyEnvelopeMm, { width: 1200, height: 40.91, depth: 32.02 });
  assert.deepEqual(contract.provenance.legacyLocalTransform.translationMm, { x: 0, y: 0, z: -40.91 });
});

test("S7 profile reaches the module06 underside/back corner exactly and emits front/down", () => {
  const contract = currentUnderCabLightContract;
  const hostWorld = resolveWorldTransforms(currentSceneBase).get(module06.id);
  assert.ok(hostWorld);
  const profileWorld = composeTransforms(hostWorld, contract.localTransform);
  assert.deepEqual(profileWorld.translationMm, { x: 3879.427, y: 8632.44, z: 1582 });
  almost(profileWorld.translationMm.y + contract.visualSizeMm.depth, 8650.44);
  almost(profileWorld.translationMm.z + contract.visualSizeMm.height, 1600);
  almost(profileWorld.translationMm.x + contract.visualSizeMm.width, 5079.427);

  const direction = contract.emitter.localDirection;
  almost(Math.hypot(direction.x, direction.y, direction.z), 1);
  assert.equal(direction.x, 0);
  assert.ok(direction.y < 0, "emitter must point toward room/front (-Y)");
  assert.ok(direction.z < 0, "emitter must point downward (-Z)");
  assert.equal(contract.emitter.colorTemperatureK, 3000);
  assert.equal(contract.emitter.emittingWidthMm, 1180);
});

test("current appearance exposes the same 3000K 45-degree semantic contract", () => {
  const definition = currentAppearance.accessoryDefinitions.find(item => item.id === "ACC-UNDERCAB-LED-01");
  assert.ok(definition);
  assert.equal(definition.emitters.length, 1);
  const emitter = definition.emitters[0];
  assert.equal(emitter.colorTemperatureK, currentUnderCabLightContract.emitter.colorTemperatureK);
  assert.equal(emitter.relativeIntensity, currentUnderCabLightContract.emitter.relativeIntensity);
  assert.deepEqual(emitter.localPositionNormalized, currentUnderCabLightContract.emitter.localPositionNormalized);
  assert.deepEqual(emitter.localDirection, currentUnderCabLightContract.emitter.localDirection);
  assert.ok(currentAppearance.materials.some(material => material.id === "under-cab-opal-3000k"));
});
