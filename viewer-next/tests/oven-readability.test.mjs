import assert from "node:assert/strict";
import test from "node:test";
import {
  currentSceneBase,
  module02,
  sceneGeometryDigest
} from "@mobilipresenter/scene-core";
import { styleAnchorAppearance } from "../dist-ts/src/fixtures/style-anchor.js";
import { attachParametricAppliances } from "../dist-ts/src/renderer/three/appliances.js";
import { ThreeMaterialRegistry } from "../dist-ts/src/renderer/three/materials.js";
import { applyFh06OvenReadability } from "../dist-ts/src/renderer/three/oven-readability.js";
import { buildThreeScene } from "../dist-ts/src/renderer/three/scene-adapter.js";

test("S10 oven reveal uses only the real 2mm clearance around 596x596 appliance inside 600x600 opening", () => {
  const registry = new ThreeMaterialRegistry(styleAnchorAppearance);
  const adapter = buildThreeScene(currentSceneBase, (entityId, slot) => registry.resolve(entityId, slot));
  attachParametricAppliances(adapter, currentSceneBase, styleAnchorAppearance, registry);
  const before = sceneGeometryDigest(currentSceneBase);
  const result = applyFh06OvenReadability(adapter, registry, currentSceneBase, styleAnchorAppearance);
  assert.equal(result.refinementId, "fh06-s10-oven-physical-reveal-v1");
  assert.deepEqual(result.physicalClearanceMm, [2, 2, 2, 2]);
  assert.equal(result.revealBehindFrontMm, 2);
  assert.equal(result.geometryDigestUnchanged, true);
  assert.equal(sceneGeometryDigest(currentSceneBase), before);

  const moduleGroup = adapter.entityGroups.get(module02.id);
  const reveal = moduleGroup?.getObjectByName("fh06-s10/module02-oven-reveals");
  assert.ok(reveal);
  assert.equal(reveal.children.length, 4);
  for (const child of reveal.children) {
    assert.equal(child.userData.physicalClearanceMm, 2);
    assert.equal(child.userData.recessBehindFrontMm, 2);
  }
  registry.dispose();
});

test("S10 oven reveal refinement is idempotent", () => {
  const registry = new ThreeMaterialRegistry(styleAnchorAppearance);
  const adapter = buildThreeScene(currentSceneBase, (entityId, slot) => registry.resolve(entityId, slot));
  attachParametricAppliances(adapter, currentSceneBase, styleAnchorAppearance, registry);
  applyFh06OvenReadability(adapter, registry, currentSceneBase, styleAnchorAppearance);
  applyFh06OvenReadability(adapter, registry, currentSceneBase, styleAnchorAppearance);
  const moduleGroup = adapter.entityGroups.get(module02.id);
  const matches = moduleGroup?.children.filter(child => child.name === "fh06-s10/module02-oven-reveals") ?? [];
  assert.equal(matches.length, 1);
  assert.equal(matches[0]?.children.length, 4);
  registry.dispose();
});
