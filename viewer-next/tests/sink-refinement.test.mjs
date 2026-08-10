import assert from "node:assert/strict";
import test from "node:test";
import {
  STONE03_ID,
  currentSceneBase,
  module03WithSink,
  sceneGeometryDigest
} from "@mobilipresenter/scene-core";
import { Mesh } from "three";
import { styleAnchorAppearance } from "../dist-ts/src/fixtures/style-anchor.js";
import { withStonePreset } from "../dist-ts/src/fixtures/stone-presets.js";
import { attachParametricAppliances } from "../dist-ts/src/renderer/three/appliances.js";
import { ThreeMaterialRegistry } from "../dist-ts/src/renderer/three/materials.js";
import { buildThreeScene } from "../dist-ts/src/renderer/three/scene-adapter.js";
import { applyFh06SinkRefinement } from "../dist-ts/src/renderer/three/sink-refinement.js";

function setup(appearance = styleAnchorAppearance) {
  const materials = new ThreeMaterialRegistry(appearance);
  const adapter = buildThreeScene(currentSceneBase, (entityId, slot) => materials.resolve(entityId, slot));
  attachParametricAppliances(adapter, currentSceneBase, appearance, materials);
  return { materials, adapter };
}

function round3(value) {
  return Math.round(value * 1000) / 1000;
}

test("S4 replaces stone-03 slab with one extruded mesh containing one rounded sink hole", () => {
  const before = sceneGeometryDigest(currentSceneBase);
  const { materials, adapter } = setup();
  const result = applyFh06SinkRefinement(adapter, materials, currentSceneBase);

  assert.equal(result.sinkFamilyId, "SINK-UNDERMOUNT-40X34-01");
  assert.equal(result.stoneHoleGeometry, "extruded-shape-with-rounded-hole");
  assert.equal(result.continuousBowl, true);
  assert.equal(result.faucetSeparatedToS5, true);
  assert.equal(result.countertopOuterEnvelopeToleranceMm, 0.001);
  assert.ok(result.countertopOuterEnvelopeDriftMm <= result.countertopOuterEnvelopeToleranceMm,
    `countertop render AABB drift ${result.countertopOuterEnvelopeDriftMm}mm exceeds ${result.countertopOuterEnvelopeToleranceMm}mm`);
  assert.equal(result.countertopOuterEnvelopePreserved, true);
  assert.deepEqual(result.openingMm.map(round3), [431.623, 126.942, 353.43, 296.117]);
  assert.equal(sceneGeometryDigest(currentSceneBase), before);

  const primitiveId = `${STONE03_ID}/slab`;
  const primitiveGroup = adapter.entityGroups.get(STONE03_ID)?.getObjectByName(primitiveId);
  assert.ok(primitiveGroup);
  const meshes = primitiveGroup.children.filter(child => child instanceof Mesh);
  assert.equal(meshes.length, 1);
  const slab = meshes[0];
  assert.equal(slab.name, `${primitiveId}/mesh`);
  assert.equal(slab.geometry.type, "ExtrudeGeometry");
  assert.equal(slab.geometry.userData.holeCount, 1);
  assert.equal(slab.geometry.userData.visualRefinement, "fh06-1-s4-stone-hole-v1");
  assert.equal(adapter.entityGroups.get(STONE03_ID)?.getObjectByName(`${STONE03_ID}/visual-cutout`), undefined);
  materials.dispose();
});

test("S4 sink is a continuous rounded undermount bowl top-aligned to the confirmed slot", () => {
  const { materials, adapter } = setup();
  const result = applyFh06SinkRefinement(adapter, materials, currentSceneBase);
  const sinkId = "scene/traditional/fixture/kitchen-sink";
  const proxy = adapter.entityGroups.get(sinkId)?.getObjectByName(`${sinkId}/parametric`);
  assert.ok(proxy);
  assert.equal(proxy.userData.visualRefinement, "fh06-1-s4-undermount-sink-v1");
  assert.equal(proxy.userData.sinkFamilyId, "SINK-UNDERMOUNT-40X34-01");
  assert.equal(proxy.userData.faucetSeparatedToS5, true);

  const visual = proxy.getObjectByName(`${sinkId}/visual`);
  const rim = proxy.getObjectByName(`${sinkId}/rim`);
  const bowlSide = proxy.getObjectByName(`${sinkId}/bowl-side`);
  const bowlBottom = proxy.getObjectByName(`${sinkId}/bowl-bottom`);
  const drain = proxy.getObjectByName(`${sinkId}/drain`);
  assert.ok(visual && rim && bowlSide && bowlBottom && drain);
  assert.equal(rim.geometry.type, "ExtrudeGeometry");
  assert.equal(bowlSide.geometry.userData.continuousLoft, true);
  assert.equal(bowlSide.geometry.userData.loopSamples, 32);
  assert.equal(proxy.getObjectByName(`${sinkId}/faucet`), undefined);

  const slot = module03WithSink.applianceSlots.find(candidate => candidate.role === "kitchen-sink");
  assert.ok(slot);
  assert.ok(Math.abs(result.topAlignedOffsetZMm + result.fittedOuterMm.height - slot.clearSizeMm.height) <= 1e-9);
  assert.deepEqual(
    [round3(result.fittedOuterMm.width), round3(result.fittedOuterMm.depth)],
    [382.087, 324.774]
  );
  assert.equal(round3(result.bowlDepthMm), 162.387);
  assert.ok(result.openingRadiusMm > 20 && result.openingRadiusMm < 30);
  assert.ok(result.flangeMm > 13 && result.flangeMm < 15);
  materials.dispose();
});

test("changing the stone preset does not change the S4 sink cutout or placement contract", () => {
  const light = setup(withStonePreset(styleAnchorAppearance, "light-speckled"));
  const graphite = setup(withStonePreset(styleAnchorAppearance, "graphite-speckled"));
  const lightResult = applyFh06SinkRefinement(light.adapter, light.materials, currentSceneBase);
  const graphiteResult = applyFh06SinkRefinement(graphite.adapter, graphite.materials, currentSceneBase);
  assert.deepEqual(graphiteResult.openingMm, lightResult.openingMm);
  assert.equal(graphiteResult.topAlignedOffsetZMm, lightResult.topAlignedOffsetZMm);
  assert.deepEqual(graphiteResult.fittedOuterMm, lightResult.fittedOuterMm);
  light.materials.dispose();
  graphite.materials.dispose();
});
