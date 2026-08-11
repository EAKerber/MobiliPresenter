import assert from "node:assert/strict";
import test from "node:test";
import {
  STONE03_ID,
  currentFaucetAnchor,
  currentSceneBase
} from "@mobilipresenter/scene-core";
import { Box3 } from "three";
import { styleAnchorAppearance } from "../dist-ts/src/fixtures/style-anchor.js";
import { FAUCET_HIGH_ARC_01 } from "../dist-ts/src/fixtures/faucet-presets.js";
import { attachParametricAppliances } from "../dist-ts/src/renderer/three/appliances.js";
import { applyFh06FaucetRefinement } from "../dist-ts/src/renderer/three/faucet-refinement.js";
import { ThreeMaterialRegistry } from "../dist-ts/src/renderer/three/materials.js";
import { buildThreeScene } from "../dist-ts/src/renderer/three/scene-adapter.js";

function setup() {
  const materials = new ThreeMaterialRegistry(styleAnchorAppearance);
  const adapter = buildThreeScene(currentSceneBase, (entityId, slot) => materials.resolve(entityId, slot));
  attachParametricAppliances(adapter, currentSceneBase, styleAnchorAppearance, materials);
  return { materials, adapter };
}

test("S5 high-arc faucet is a separate hosted visual with stable 340mm height and 255mm reach", () => {
  const { materials, adapter } = setup();
  const result = applyFh06FaucetRefinement(adapter, materials, currentFaucetAnchor);
  assert.equal(result.presetId, "FAUCET-HIGH-ARC-01");
  assert.equal(result.hostEntityId, STONE03_ID);
  assert.equal(result.heightMm, 340);
  assert.equal(result.centerlineReachMm, 255);
  assert.deepEqual(result.anchorLocalMm, [608.3385, 482.387475, 30]);
  assert.ok(result.childCount >= 7);

  const host = adapter.entityGroups.get(STONE03_ID);
  const root = host?.getObjectByName(currentFaucetAnchor.id);
  assert.ok(host && root);
  assert.equal(root.parent, host);
  assert.equal(root.userData.faucetPresetId, FAUCET_HIGH_ARC_01.id);
  assert.equal(root.getObjectByName(`${FAUCET_HIGH_ARC_01.id}/spout`)?.geometry.type, "TubeGeometry");
  assert.equal(root.getObjectByName(`${FAUCET_HIGH_ARC_01.id}/nozzle`)?.geometry.type, "CylinderGeometry");
  assert.ok(root.getObjectByName(`${FAUCET_HIGH_ARC_01.id}/aerator`));
  assert.ok(root.getObjectByName(`${FAUCET_HIGH_ARC_01.id}/lever`));

  root.updateWorldMatrix(true, true);
  const bounds = new Box3().setFromObject(root);
  const renderedHeight = bounds.max.y - bounds.min.y;
  assert.ok(renderedHeight >= 338 && renderedHeight <= 342, `renderedHeight=${renderedHeight}`);
  materials.dispose();
});

test("S5 faucet inherits stone-03 visibility and repeated refinement is idempotent", () => {
  const { materials, adapter } = setup();
  applyFh06FaucetRefinement(adapter, materials, currentFaucetAnchor);
  applyFh06FaucetRefinement(adapter, materials, currentFaucetAnchor);
  const host = adapter.entityGroups.get(STONE03_ID);
  assert.ok(host);
  const roots = host.children.filter(child => child.name === currentFaucetAnchor.id);
  assert.equal(roots.length, 1);
  host.visible = false;
  assert.equal(roots[0].visible, true);
  assert.equal(roots[0].parent?.visible, false);
  materials.dispose();
});
