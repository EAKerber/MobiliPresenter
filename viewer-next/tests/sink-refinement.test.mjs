import assert from "node:assert/strict";
import test from "node:test";
import {
  STONE03_ID,
  currentSceneBase,
  module03WithSink,
  sceneGeometryDigest
} from "@mobilipresenter/scene-core";
import { Mesh, MeshStandardMaterial } from "three";
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

function rgbEnergy(material) {
  return material.color.r + material.color.g + material.color.b;
}

test("S9 keeps one true rounded hole while assigning a darker physical material to cutout sidewalls", () => {
  const before = sceneGeometryDigest(currentSceneBase);
  const { materials, adapter } = setup();
  const result = applyFh06SinkRefinement(adapter, materials, currentSceneBase);

  assert.equal(result.sinkFamilyId, "SINK-UNDERMOUNT-40X34-01");
  assert.equal(result.stoneHoleGeometry, "extruded-shape-with-rounded-hole");
  assert.equal(result.continuousBowl, true);
  assert.equal(result.faucetSeparatedToS5, true);
  assert.equal(result.readabilityPolicy, "physical-surface-response-no-screen-outline");
  assert.equal(result.stoneCutoutSideDarkening, 0.62);
  assert.equal(result.countertopOuterEnvelopeToleranceMm, 0.001);
  assert.ok(result.countertopOuterEnvelopeDriftMm <= result.countertopOuterEnvelopeToleranceMm,
    `countertop render AABB drift ${result.countertopOuterEnvelopeDriftMm}mm exceeds ${result.countertopOuterEnvelopeToleranceMm}mm`);
  assert.equal(result.countertopOuterEnvelopePreserved, true);
  assert.deepEqual(result.openingMm.map(round3), [431.623, 126.942, 353.43, 296.117]);
  assert.equal(sceneGeometryDigest(currentSceneBase), before);

  const primitiveId = `${STONE03_ID}/slab`;
  const primitiveGroup = adapter.entityGroups.get(STONE03_ID)?.getObjectByName(primitiveId);
  assert.ok(primitiveGroup);
  const slab = primitiveGroup.getObjectByName(`${primitiveId}/mesh`);
  assert.ok(slab instanceof Mesh);
  assert.equal(slab.geometry.type, "ExtrudeGeometry");
  assert.equal(slab.geometry.userData.holeCount, 1);
  assert.equal(slab.geometry.userData.visualRefinement, "fh06-1-s9-stone-hole-readability-v1");
  assert.equal(slab.geometry.userData.capMaterialIndex, 0);
  assert.equal(slab.geometry.userData.sideMaterialIndex, 1);
  assert.ok(Array.isArray(slab.material));
  assert.equal(slab.material.length, 2);
  const cap = slab.material[0];
  const cutoutSide = slab.material[1];
  assert.ok(cap instanceof MeshStandardMaterial && cutoutSide instanceof MeshStandardMaterial);
  assert.equal(cutoutSide.userData.sinkCutoutSide, true);
  assert.ok(rgbEnergy(cutoutSide) < rgbEnergy(cap) * 0.7);
  assert.ok(cutoutSide.roughness > cap.roughness);
  materials.dispose();
});

test("S9 sink remains continuous and top-aligned while bowl side and bottom have distinct occluded inox response", () => {
  const { materials, adapter } = setup();
  const result = applyFh06SinkRefinement(adapter, materials, currentSceneBase);
  const sinkId = "scene/traditional/fixture/kitchen-sink";
  const proxy = adapter.entityGroups.get(sinkId)?.getObjectByName(`${sinkId}/parametric`);
  assert.ok(proxy);
  assert.equal(proxy.userData.visualRefinement, "fh06-1-s9-undermount-sink-readability-v1");
  assert.equal(proxy.userData.sinkFamilyId, "SINK-UNDERMOUNT-40X34-01");
  assert.equal(proxy.userData.faucetSeparatedToS5, true);
  assert.equal(proxy.userData.readabilityPolicy, "physical-surface-response-no-screen-outline");

  const rim = proxy.getObjectByName(`${sinkId}/rim`);
  const bowlSide = proxy.getObjectByName(`${sinkId}/bowl-side`);
  const bowlBottom = proxy.getObjectByName(`${sinkId}/bowl-bottom`);
  const drain = proxy.getObjectByName(`${sinkId}/drain`);
  assert.ok(rim instanceof Mesh && bowlSide instanceof Mesh && bowlBottom instanceof Mesh && drain instanceof Mesh);
  assert.equal(rim.geometry.type, "ExtrudeGeometry");
  assert.equal(bowlSide.geometry.userData.continuousLoft, true);
  assert.equal(bowlSide.geometry.userData.loopSamples, 32);
  assert.ok(rim.material instanceof MeshStandardMaterial);
  assert.ok(bowlSide.material instanceof MeshStandardMaterial);
  assert.ok(bowlBottom.material instanceof MeshStandardMaterial);
  assert.equal(bowlSide.material.userData.sinkBowlSide, true);
  assert.equal(bowlBottom.material.userData.sinkBowlBottom, true);
  assert.ok(rgbEnergy(bowlSide.material) < rgbEnergy(rim.material) * 0.7);
  assert.ok(rgbEnergy(bowlBottom.material) < rgbEnergy(bowlSide.material));
  assert.equal(result.bowlSideDarkening, 0.58);
  assert.equal(result.bowlBottomDarkening, 0.46);

  const slot = module03WithSink.applianceSlots.find(candidate => candidate.role === "kitchen-sink");
  assert.ok(slot);
  assert.ok(Math.abs(result.topAlignedOffsetZMm + result.fittedOuterMm.height - slot.clearSizeMm.height) <= 1e-9);
  assert.deepEqual([round3(result.fittedOuterMm.width), round3(result.fittedOuterMm.depth)], [382.087, 324.774]);
  assert.equal(round3(result.bowlDepthMm), 162.387);
  assert.equal(proxy.getObjectByName(`${sinkId}/faucet`), undefined);
  materials.dispose();
});

test("changing stone preset never changes S9 sink cutout, placement, or physical readability policy", () => {
  const light = setup(withStonePreset(styleAnchorAppearance, "light-speckled"));
  const graphite = setup(withStonePreset(styleAnchorAppearance, "graphite-speckled"));
  const lightResult = applyFh06SinkRefinement(light.adapter, light.materials, currentSceneBase);
  const graphiteResult = applyFh06SinkRefinement(graphite.adapter, graphite.materials, currentSceneBase);
  assert.deepEqual(graphiteResult.openingMm, lightResult.openingMm);
  assert.equal(graphiteResult.topAlignedOffsetZMm, lightResult.topAlignedOffsetZMm);
  assert.deepEqual(graphiteResult.fittedOuterMm, lightResult.fittedOuterMm);
  assert.equal(graphiteResult.readabilityPolicy, lightResult.readabilityPolicy);
  light.materials.dispose();
  graphite.materials.dispose();
});
