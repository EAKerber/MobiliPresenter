import assert from "node:assert/strict";
import test from "node:test";
import { currentSceneBase, sceneGeometryDigest } from "@mobilipresenter/scene-core";
import { attachParametricAppliances } from "../dist-ts/src/renderer/three/appliances.js";
import { applyFh06CooktopContact } from "../dist-ts/src/renderer/three/cooktop-contact.js";
import { styleAnchorAppearance } from "../dist-ts/src/fixtures/style-anchor.js";
import { ThreeMaterialRegistry } from "../dist-ts/src/renderer/three/materials.js";
import { buildThreeScene } from "../dist-ts/src/renderer/three/scene-adapter.js";

function setup() {
  const materials = new ThreeMaterialRegistry(styleAnchorAppearance);
  const adapter = buildThreeScene(currentSceneBase, (entityId, slot) => materials.resolve(entityId, slot));
  attachParametricAppliances(adapter, currentSceneBase, styleAnchorAppearance, materials);
  return { materials, adapter };
}

test("S10 cooktop contact removes hover while preserving Scene Core geometry", () => {
  const before = sceneGeometryDigest(currentSceneBase);
  const { materials, adapter } = setup();
  const result = applyFh06CooktopContact(adapter, currentSceneBase);
  assert.equal(result.refinementId, "fh06-s10-cooktop-stone-contact-v1");
  assert.equal(result.contactClearanceMm, 1);
  assert.ok(result.beforeGapMm > 40, `expected previous hover >40mm, got ${result.beforeGapMm}`);
  assert.ok(Math.abs(result.afterGapMm - 1) <= 0.001, `expected 1mm contact clearance, got ${result.afterGapMm}`);
  assert.ok(result.correctionMm < -40, `expected downward visual correction, got ${result.correctionMm}`);
  assert.equal(result.geometryDigestUnchanged, true);
  assert.equal(sceneGeometryDigest(currentSceneBase), before);
  materials.dispose();
});
