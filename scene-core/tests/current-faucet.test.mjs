import assert from "node:assert/strict";
import test from "node:test";
import {
  STONE03_ID,
  composeTransforms,
  currentFaucetAnchor,
  currentSceneBase,
  resolveWorldTransforms
} from "../dist/src/index.js";

function assertVecAlmost(actual, expected, epsilon = 1e-9) {
  assert.ok(actual);
  for (const key of ["x", "y", "z"]) {
    assert.ok(Math.abs(actual[key] - expected[key]) <= epsilon, `${key}: ${actual[key]} != ${expected[key]}`);
  }
}

test("kitchen faucet anchor is a stable inferred deck anchor hosted by stone-03", () => {
  assert.equal(currentFaucetAnchor.definitionId, "FAUCET-HIGH-ARC-01");
  assert.equal(currentFaucetAnchor.hostEntityId, STONE03_ID);
  assert.equal(currentFaucetAnchor.placementStatus, "inferred");
  assert.deepEqual(currentFaucetAnchor.localTransform.translationMm, {
    x: 608.3385,
    y: 482.387475,
    z: 30
  });
  assert.ok(currentFaucetAnchor.evidenceRefs.some(ref => ref.includes("centered-behind-sink")));
  assert.ok(currentFaucetAnchor.evidenceRefs.some(ref => ref.includes("45mm-from-sink-rear-edge")));
});

test("faucet anchor resolves to the stone top and preserves clearance before the 100mm rear upstand", () => {
  const world = resolveWorldTransforms(currentSceneBase);
  const stoneWorld = world.get(STONE03_ID);
  assert.ok(stoneWorld);
  const faucetWorld = composeTransforms(stoneWorld, currentFaucetAnchor.localTransform);
  assertVecAlmost(faucetWorld.translationMm, {
    x: 4471.0875,
    y: 8582.825475,
    z: 889
  });
  const upstandFrontLocalY = 530;
  const clearanceMm = upstandFrontLocalY - currentFaucetAnchor.localTransform.translationMm.y;
  assert.ok(clearanceMm > 45 && clearanceMm < 50, `clearance=${clearanceMm}`);
});
