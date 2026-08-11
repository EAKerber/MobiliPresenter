import assert from "node:assert/strict";
import test from "node:test";
import { renderConditioning } from "../dist/src/conditioning/conditioning.js";
import { STONE03_ID, currentSceneBase } from "../dist/src/fixtures/current-scene.js";
import { module03 } from "../dist/src/fixtures/current-geometry.js";
import { setVisibilityIntent } from "../dist/src/state/scene-state.js";

function countNonZero(array) {
  let count = 0;
  for (const value of array) if (value !== 0) count++;
  return count;
}

test("conditioning is byte-deterministic for same scene", () => {
  const a = renderConditioning(currentSceneBase, 320, 166);
  const b = renderConditioning(currentSceneBase, 320, 166);
  assert.deepEqual(a.entityIds, b.entityIds);
  assert.deepEqual(a.materialSlots, b.materialSlots);
  assert.deepEqual(a.entityMask, b.entityMask);
  assert.deepEqual(a.materialMask, b.materialMask);
  assert.deepEqual(a.edgeMask, b.edgeMask);
  assert.deepEqual(a.depthMm, b.depthMm);
  assert.deepEqual(a.normalXyz, b.normalXyz);
});

test("conditioning contains depth, normals, entity, material and edge information", () => {
  const output = renderConditioning(currentSceneBase, 320, 166);
  assert.ok(countNonZero(output.entityMask) > 1000);
  assert.ok(countNonZero(output.materialMask) > 1000);
  assert.ok(countNonZero(output.edgeMask) > 100);
  assert.ok(output.materialSlots.includes("front"));
  assert.ok(output.materialSlots.includes("wall"));
  assert.ok(output.materialSlots.includes("stone"));
  assert.ok(output.materialSlots.includes("emissive"));
  assert.ok(Array.from(output.depthMm).some(Number.isFinite));
  assert.ok(Array.from(output.normalXyz).some(value => Math.abs(value) > 0.5));
});

test("hiding a module removes it and hosted accessories from conditioning without mutating geometry", () => {
  const visible = renderConditioning(currentSceneBase, 320, 166);
  assert.ok(visible.entityIds.includes(module03.id));
  assert.ok(visible.entityIds.includes(STONE03_ID));
  const hiddenScene = setVisibilityIntent(currentSceneBase, module03.id, "off");
  const hidden = renderConditioning(hiddenScene, 320, 166);
  assert.equal(hidden.entityIds.includes(module03.id), false);
  assert.equal(hidden.entityIds.includes(STONE03_ID), false);
  assert.notDeepEqual(hidden.entityMask, visible.entityMask);
});
