import assert from "node:assert/strict";
import test from "node:test";
import { projectPoint } from "../dist/src/core/camera.js";
import { currentFixedCamera } from "../dist/src/fixtures/current-camera.js";

const viewport = { widthPx: 1865, heightPx: 967 };

const observations = [
  { id: "m02-front", face: { x: 3073.7, y: 8102.4, z: 102.0, width: 787.0, height: 754.0 }, box: { x: 526, y: 554, width: 236, height: 225 } },
  { id: "m03-drawer-top", face: { x: 3864.7, y: 8102.4, z: 670.0, width: 396.0, height: 187.0 }, box: { x: 764, y: 553, width: 117, height: 55 } },
  { id: "m03-drawer-2", face: { x: 3864.7, y: 8102.4, z: 481.0, width: 396.0, height: 187.0 }, box: { x: 764, y: 610, width: 117, height: 55 } },
  { id: "m03-door1", face: { x: 4264.7, y: 8102.4, z: 103.0, width: 405.3, height: 754.0 }, box: { x: 884, y: 553, width: 120, height: 225 } },
  { id: "m05-door1", face: { x: 3082.4, y: 8232.4, z: 1704.0, width: 395.5, height: 693.0 }, box: { x: 543, y: 105, width: 113, height: 200 } },
  { id: "m05-door2", face: { x: 3480.9, y: 8232.4, z: 1704.0, width: 395.5, height: 693.0 }, box: { x: 658, y: 105, width: 114, height: 200 } },
  { id: "m06-door1", face: { x: 3882.4, y: 8232.4, z: 1604.0, width: 307.5, height: 793.0 }, box: { x: 774, y: 105, width: 88, height: 229 } },
  { id: "m06-door2", face: { x: 4192.9, y: 8232.4, z: 1604.0, width: 307.5, height: 793.0 }, box: { x: 864, y: 105, width: 88, height: 229 } },
  { id: "m07-door1", face: { x: 5100.4, y: 8040.4, z: 1920.0, width: 395.5, height: 477.0 }, box: { x: 1137, y: 86, width: 119, height: 144 } },
  { id: "m07-door2", face: { x: 5498.9, y: 8040.4, z: 1920.0, width: 395.5, height: 477.0 }, box: { x: 1258, y: 86, width: 120, height: 143 } }
];

function projectedBox(face) {
  const points = [
    projectPoint(currentFixedCamera, viewport, { x: face.x, y: face.y, z: face.z }),
    projectPoint(currentFixedCamera, viewport, { x: face.x + face.width, y: face.y, z: face.z }),
    projectPoint(currentFixedCamera, viewport, { x: face.x, y: face.y, z: face.z + face.height }),
    projectPoint(currentFixedCamera, viewport, { x: face.x + face.width, y: face.y, z: face.z + face.height })
  ];
  const xs = points.map(p => p.xPx);
  const ys = points.map(p => p.yPx);
  const x = Math.min(...xs);
  const y = Math.min(...ys);
  return { x, y, width: Math.max(...xs) - x, height: Math.max(...ys) - y };
}

test("calibrated fixed camera keeps landmark centers within five pixels", () => {
  const errors = observations.map(observation => {
    const predicted = projectedBox(observation.face);
    const predictedCenter = [predicted.x + predicted.width / 2, predicted.y + predicted.height / 2];
    const observedCenter = [observation.box.x + observation.box.width / 2, observation.box.y + observation.box.height / 2];
    return Math.hypot(predictedCenter[0] - observedCenter[0], predictedCenter[1] - observedCenter[1]);
  });
  assert.ok(Math.max(...errors) <= 5, `max center error ${Math.max(...errors)}`);
});

test("calibrated perspective size fit stays near prior baseline", () => {
  const squared = [];
  for (const observation of observations) {
    const predicted = projectedBox(observation.face);
    squared.push((predicted.width - observation.box.width) ** 2);
    squared.push((predicted.height - observation.box.height) ** 2);
  }
  const rms = Math.sqrt(squared.reduce((sum, value) => sum + value, 0) / squared.length);
  assert.ok(rms <= 1.2, `size RMS ${rms}`);
});

test("doubling viewport resolution preserves normalized projection", () => {
  const point = { x: 4264.7, y: 8102.4, z: 103.0 };
  const a = projectPoint(currentFixedCamera, viewport, point);
  const b = projectPoint(currentFixedCamera, { widthPx: viewport.widthPx * 2, heightPx: viewport.heightPx * 2 }, point);
  assert.ok(Math.abs(b.xPx - a.xPx * 2) < 1e-9);
  assert.ok(Math.abs(b.yPx - a.yPx * 2) < 1e-9);
});
