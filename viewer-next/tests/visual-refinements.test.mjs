import assert from "node:assert/strict";
import test from "node:test";
import {
  currentAppearance,
  currentSceneBase,
  sceneGeometryDigest,
  setEntityMaterialOverride,
  module03WithSink
} from "@mobilipresenter/scene-core";
import { attachParametricAppliances } from "../dist-ts/src/renderer/three/appliances.js";
import { ThreeMaterialRegistry } from "../dist-ts/src/renderer/three/materials.js";
import { buildThreeScene } from "../dist-ts/src/renderer/three/scene-adapter.js";
import { applyFh06VisualRefinements } from "../dist-ts/src/renderer/three/visual-refinements.js";

function setup() {
  const appearance = setEntityMaterialOverride(currentAppearance, module03WithSink.id, "front", "front-wood");
  const materials = new ThreeMaterialRegistry(appearance);
  const adapter = buildThreeScene(currentSceneBase, (entityId, slot) => materials.resolve(entityId, slot));
  attachParametricAppliances(adapter, currentSceneBase, appearance, materials);
  return { appearance, materials, adapter };
}

test("FH-06 hood refinement never mutates Scene Core geometry", () => {
  const before = sceneGeometryDigest(currentSceneBase);
  const { materials, adapter } = setup();
  applyFh06VisualRefinements(adapter, materials);
  assert.equal(sceneGeometryDigest(currentSceneBase), before);
  materials.dispose();
});

test("hood refinement replaces box proxy with recognizable slim/retractable feature groups", () => {
  const { materials, adapter } = setup();
  applyFh06VisualRefinements(adapter, materials);
  const hoodId = "scene/traditional/appliance/hood";
  const proxy = adapter.entityGroups.get(hoodId)?.getObjectByName(`${hoodId}/parametric`);
  assert.ok(proxy);
  assert.equal(proxy.userData.visualRefinement, "fh06-slim-retractable-hood-v1");
  assert.equal(proxy.children.length, 7);
  const fit = proxy.userData.fit;
  assert.ok(fit?.fittedMm.width > 0);
  assert.ok(fit?.fittedMm.height > 0);
  assert.ok(fit?.fittedMm.depth > 0);
  materials.dispose();
});
