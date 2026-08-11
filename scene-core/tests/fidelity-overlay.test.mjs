import assert from "node:assert/strict";
import test from "node:test";
import {
  createAabbOverlay,
  createDimensionLine,
  createPlanarMetricGrid,
  createSceneAabbs,
  createSceneWireframe
} from "../dist/src/fidelity/overlay.js";
import { identityTransform } from "../dist/src/contracts/model.js";
import { currentSceneBase } from "../dist/src/fixtures/current-scene.js";

test("100/500 mm planar grid is world-space and marks major intervals", () => {
  const lines = createPlanarMetricGrid({
    id: "test-grid",
    originMm: { x: 0, y: 0, z: 0 },
    uAxis: { x: 1, y: 0, z: 0 },
    vAxis: { x: 0, y: 0, z: 1 },
    uLengthMm: 1000,
    vLengthMm: 500,
    minorStepMm: 100,
    majorStepMm: 500
  });
  assert.equal(lines.length, 17);
  const major = lines.filter(line => line.role === "grid-major");
  assert.equal(major.length, 5);
  assert.deepEqual(lines[0].aMm, { x: 0, y: 0, z: 0 });
  assert.deepEqual(lines[0].bMm, { x: 0, y: 0, z: 500 });
});

test("AABB overlay always has twelve physical edges", () => {
  const lines = createAabbOverlay(
    "box",
    { min: { x: 0, y: 0, z: 0 }, max: { x: 10, y: 20, z: 30 } },
    identityTransform(),
    "entity"
  );
  assert.equal(lines.length, 12);
  assert.ok(lines.every(line => line.entityId === "entity"));
});

test("current scene produces deterministic finite wireframe lines", () => {
  const first = createSceneWireframe(currentSceneBase);
  const second = createSceneWireframe(currentSceneBase);
  assert.deepEqual(second, first);
  assert.ok(first.length > 100);
  for (const line of first) {
    for (const value of [line.aMm.x, line.aMm.y, line.aMm.z, line.bMm.x, line.bMm.y, line.bMm.z]) {
      assert.ok(Number.isFinite(value));
    }
  }
});

test("scene module/environment AABBs remain separate from render wireframe", () => {
  const lines = createSceneAabbs(currentSceneBase);
  assert.equal(lines.length, (currentSceneBase.environment.length + currentSceneBase.modules.length) * 12);
  assert.ok(lines.every(line => line.role === "aabb"));
});

test("dimension line preserves physical metric independent of rendering", () => {
  const line = createDimensionLine(
    "span-02-03",
    { x: 3071.739, y: 8102.44, z: 100 },
    { x: 5079.427, y: 8102.44, z: 100 },
    2007.688
  );
  assert.equal(line.metricMm, 2007.688);
  assert.equal(line.role, "dimension");
});
