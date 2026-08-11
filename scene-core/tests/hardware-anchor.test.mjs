import assert from "node:assert/strict";
import test from "node:test";
import { projectPoint } from "../dist/src/core/camera.js";
import { currentFixedCamera } from "../dist/src/fixtures/current-camera.js";
import { currentHardwareAnchors } from "../dist/src/fixtures/current-hardware.js";
import { currentSceneBase } from "../dist/src/fixtures/current-scene.js";
import { resolveHardwareAnchors } from "../dist/src/hardware/anchors.js";

const resolved = () => resolveHardwareAnchors(currentSceneBase, currentHardwareAnchors);

test("all current hardware anchors resolve inside their current front faces", () => {
  const values = resolved();
  assert.equal(values.length, 6);
  assert.equal(new Set(values.map(value => value.anchorId)).size, 6);
});

test("drawer anchors preserve centered policy on 396x187 current fronts", () => {
  const drawer = resolved().find(value => value.anchorId.endsWith("drawer-1"));
  assert.deepEqual(drawer?.uvMm, [198, 93.5]);
});

test("door edge policy preserves V7 43.5 mm lateral and 97 mm top offsets", () => {
  const center = resolved().find(value => value.anchorId.endsWith("door-center"));
  const right = resolved().find(value => value.anchorId.endsWith("door-right"));
  assert.ok(Math.abs(center.uvMm[0] - (405.339 - 43.5)) < 1e-9);
  assert.ok(Math.abs(center.uvMm[1] - 657) < 1e-9);
  assert.ok(Math.abs(right.uvMm[0] - 43.5) < 1e-9);
  assert.ok(Math.abs(right.uvMm[1] - 657) < 1e-9);
});

test("hardware anchor projection is stable at canonical and 4x viewports", () => {
  const point = resolved()[0].worldMm;
  const one = projectPoint(currentFixedCamera, { widthPx: 1865, heightPx: 967 }, point);
  const four = projectPoint(currentFixedCamera, { widthPx: 7460, heightPx: 3868 }, point);
  assert.ok(Math.abs(four.xPx / 4 - one.xPx) < 1e-9);
  assert.ok(Math.abs(four.yPx / 4 - one.yPx) < 1e-9);
});
