import assert from "node:assert/strict";
import test from "node:test";
import {
  STONE03_ID,
  currentAppearance,
  currentSceneBase,
  sceneGeometryDigest,
  setEntityMaterialOverride,
  module03WithSink
} from "@mobilipresenter/scene-core";
import { attachParametricAppliances } from "../dist-ts/src/renderer/three/appliances.js";
import { ThreeMaterialRegistry } from "../dist-ts/src/renderer/three/materials.js";
import { buildThreeScene } from "../dist-ts/src/renderer/three/scene-adapter.js";
import { applyFh06SinkRefinement } from "../dist-ts/src/renderer/three/sink-refinement.js";

function setup() {
  const appearance = setEntityMaterialOverride(currentAppearance, module03WithSink.id, "front", "front-wood");
  const materials = new ThreeMaterialRegistry(appearance);
  const adapter = buildThreeScene(currentSceneBase, (entityId, slot) => materials.resolve(entityId, slot));
  attachParametricAppliances(adapter, currentSceneBase, appearance, materials);
  return { materials, adapter };
}

test("stone-03 cutout preserves authoritative envelope within explicit render precision", () => {
  const before = sceneGeometryDigest(currentSceneBase);
  const { materials, adapter } = setup();
  const result = applyFh06SinkRefinement(adapter, materials, currentSceneBase);
  assert.equal(result.countertopOuterEnvelopeToleranceMm, 0.001);
  assert.ok(result.countertopOuterEnvelopeDriftMm <= result.countertopOuterEnvelopeToleranceMm,
    `countertop render AABB drift ${result.countertopOuterEnvelopeDriftMm}mm exceeds ${result.countertopOuterEnvelopeToleranceMm}mm`);
  assert.equal(result.countertopOuterEnvelopePreserved, true);
  assert.deepEqual(result.openingMm.map(value => Math.round(value * 1000) / 1000), [417.295, 83.958, 382.087, 382.085]);
  assert.equal(sceneGeometryDigest(currentSceneBase), before);
  const stoneGroup = adapter.entityGroups.get(STONE03_ID);
  assert.ok(stoneGroup?.getObjectByName(`${STONE03_ID}/upstand`));
  const cutout = stoneGroup?.getObjectByName(`${STONE03_ID}/visual-cutout`);
  assert.ok(cutout);
  assert.equal(cutout.children.length, 4);
  materials.dispose();
});

test("sink proxy gains an actual curved faucet while preserving its hosted fit contract", () => {
  const { materials, adapter } = setup();
  const result = applyFh06SinkRefinement(adapter, materials, currentSceneBase);
  assert.equal(result.faucetHeightMm, 220);
  const sinkId = "scene/traditional/fixture/kitchen-sink";
  const proxy = adapter.entityGroups.get(sinkId)?.getObjectByName(`${sinkId}/parametric`);
  assert.ok(proxy);
  assert.equal(proxy.userData.visualRefinement, "fh06-sink-and-faucet-v1");
  assert.equal(proxy.children.length, 1);
  assert.ok(proxy.children[0].children.length >= 10);
  assert.ok(proxy.userData.fit?.fittedMm.width > 0);
  materials.dispose();
});
