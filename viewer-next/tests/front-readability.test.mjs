import assert from "node:assert/strict";
import test from "node:test";
import {
  currentSceneBase,
  module03WithSink,
  sceneGeometryDigest
} from "@mobilipresenter/scene-core";
import { Box3, Mesh, Vector3 } from "three";
import { styleAnchorAppearance } from "../dist-ts/src/fixtures/style-anchor.js";
import { applyFh06FrontReadability } from "../dist-ts/src/renderer/three/front-readability.js";
import { ThreeMaterialRegistry } from "../dist-ts/src/renderer/three/materials.js";
import { buildThreeScene } from "../dist-ts/src/renderer/three/scene-adapter.js";

function setup() {
  const materials = new ThreeMaterialRegistry(styleAnchorAppearance);
  const adapter = buildThreeScene(currentSceneBase, (entityId, slot) => materials.resolve(entityId, slot));
  return { materials, adapter };
}

function almost(actual, expected, epsilon = 0.001) {
  assert.ok(Math.abs(actual - expected) <= epsilon, `${actual} != ${expected}`);
}

test("S8 preserves all three physical 2mm drawer gaps while adding only bevel and recessed shadow", () => {
  const before = sceneGeometryDigest(currentSceneBase);
  const { materials, adapter } = setup();
  const result = applyFh06FrontReadability(adapter, materials, currentSceneBase);
  assert.equal(result.refinementId, "module03-drawer-bevel-recess-v1");
  assert.equal(result.drawerCount, 4);
  assert.equal(result.seamCount, 3);
  assert.equal(result.bevelMm, 1.25);
  assert.deepEqual(result.physicalGapMm, [2, 2, 2]);
  assert.equal(result.revealBehindFrontMm, 2);
  assert.equal(result.geometryDigestUnchanged, true);
  assert.equal(sceneGeometryDigest(currentSceneBase), before);
  materials.dispose();
});

test("S8 beveled drawer meshes preserve authoritative 396x187x18 envelopes", () => {
  const { materials, adapter } = setup();
  applyFh06FrontReadability(adapter, materials, currentSceneBase);
  const moduleGroup = adapter.entityGroups.get(module03WithSink.id);
  assert.ok(moduleGroup);
  for (let index = 1; index <= 4; index++) {
    const id = `scene/traditional/module/lower-sink/front/drawer-${index}`;
    const mesh = moduleGroup.getObjectByName(`${id}/mesh`);
    assert.ok(mesh instanceof Mesh);
    assert.equal(mesh.geometry.userData.visualRefinement, "fh06-s8-front-bevel-v1");
    assert.equal(mesh.geometry.userData.bevelMm, 1.25);
    mesh.geometry.computeBoundingBox();
    const size = mesh.geometry.boundingBox.getSize(new Vector3());
    almost(size.x, 396);
    almost(size.y, 187);
    almost(size.z, 18);
    assert.equal(mesh.castShadow, true);
    assert.equal(mesh.receiveShadow, true);
  }
  materials.dispose();
});

test("S8 reveal surfaces occupy only the existing 2mm gaps and remain recessed from the front plane", () => {
  const { materials, adapter } = setup();
  applyFh06FrontReadability(adapter, materials, currentSceneBase);
  const moduleGroup = adapter.entityGroups.get(module03WithSink.id);
  const reveal = moduleGroup?.getObjectByName("fh06-s8/module03-drawer-reveals");
  assert.ok(reveal);
  assert.equal(reveal.children.length, 3);
  assert.equal(reveal.userData.physicalGapPreserved, true);
  assert.equal(reveal.userData.revealBehindFrontMm, 2);
  for (const child of reveal.children) {
    assert.ok(child instanceof Mesh);
    assert.equal(child.userData.physicalGapMm, 2);
    assert.equal(child.userData.recessBehindFrontMm, 2);
    child.geometry.computeBoundingBox();
    const size = child.geometry.boundingBox.getSize(new Vector3());
    almost(size.x, 396);
    almost(size.y, 2);
    almost(size.z, 1);
  }
  materials.dispose();
});

test("S8 does not replace the already-readable module03 door geometry", () => {
  const { materials, adapter } = setup();
  applyFh06FrontReadability(adapter, materials, currentSceneBase);
  const doorId = "scene/traditional/module/lower-sink/front/door-center";
  const door = adapter.entityGroups.get(module03WithSink.id)?.getObjectByName(`${doorId}/mesh`);
  assert.ok(door instanceof Mesh);
  assert.equal(door.geometry.userData.visualRefinement, undefined);
  materials.dispose();
});
