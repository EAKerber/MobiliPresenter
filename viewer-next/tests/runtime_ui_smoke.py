import assert from "node:assert/strict";
import test from "node:test";
import { currentFixedCamera, currentSceneBase } from "@mobilipresenter/scene-core";
import { resolvePresentationFrame } from "../dist-ts/src/renderer/presentation-frame.js";
import {
  createThreeCamera,
  projectScenePointWithThree,
  updateThreeCameraAspect
} from "../dist-ts/src/renderer/three/camera.js";

const frame = currentSceneBase.presentationFrame;
assert.ok(frame);

const HOSTS = [
  { widthPx: 1366, heightPx: 768 },
  { widthPx: 1024, heightPx: 768 },
  { widthPx: 768, heightPx: 1024 },
  { widthPx: 390, heightPx: 844 }
];

function normalizedProjection(camera, point) {
  const viewport = { widthPx: 1000, heightPx: 1000 };
  const [x, y] = projectScenePointWithThree(camera, viewport, point);
  return [x / viewport.widthPx, y / viewport.heightPx];
}

test("contain uses the complete host when the host already matches the preferred aspect", () => {
  const resolved = resolvePresentationFrame(
    { widthPx: frame.preferredAspectRatio * 500, heightPx: 500 },
    frame
  );
  assert.equal(resolved.active, true);
  assert.equal(resolved.fit, "contain");
  assert.equal(resolved.cropped, false);
  assert.equal(resolved.rasterRect.xPx, 0);
  assert.equal(resolved.rasterRect.yPx, 0);
  assert.equal(resolved.rasterRect.heightPx, 500);
  assert.ok(Math.abs(resolved.rasterRect.widthPx / resolved.rasterRect.heightPx - frame.preferredAspectRatio) < 0.002);
});

test("contain centers pillarbox and letterbox without escaping the host", () => {
  const wide = resolvePresentationFrame({ widthPx: 1600, heightPx: 600 }, frame);
  assert.ok(wide.rasterRect.xPx > 0);
  assert.equal(wide.rasterRect.yPx, 0);

  const tall = resolvePresentationFrame({ widthPx: 600, heightPx: 1000 }, frame);
  assert.equal(tall.rasterRect.xPx, 0);
  assert.ok(tall.rasterRect.yPx > 0);

  for (const resolved of [wide, tall]) {
    const { rasterRect, hostViewport } = resolved;
    assert.ok(rasterRect.xPx >= 0 && rasterRect.yPx >= 0);
    assert.ok(rasterRect.xPx + rasterRect.widthPx <= hostViewport.widthPx);
    assert.ok(rasterRect.yPx + rasterRect.heightPx <= hostViewport.heightPx);
    assert.ok(Math.abs((hostViewport.widthPx - rasterRect.widthPx) - 2 * rasterRect.xPx) <= 1);
    assert.ok(Math.abs((hostViewport.heightPx - rasterRect.heightPx) - 2 * rasterRect.yPx) <= 1);
  }
});

test("projection aspect is exact and independent from raster rounding", () => {
  for (const host of HOSTS) {
    const resolved = resolvePresentationFrame(host, frame);
    assert.equal(resolved.projectionAspectRatio, frame.preferredAspectRatio);
    assert.equal(resolved.cropped, false);
  }
});

test("same fixed camera and PresentationFrame preserve normalized composition across hosts", () => {
  const camera = createThreeCamera(currentFixedCamera, { widthPx: 1, heightPx: 1 });
  const points = [
    currentFixedCamera.targetMm,
    { x: currentFixedCamera.targetMm.x - 900, y: currentFixedCamera.targetMm.y + 1800, z: 700 },
    { x: currentFixedCamera.targetMm.x + 1050, y: currentFixedCamera.targetMm.y + 2400, z: 1650 }
  ];
  let baseline = null;
  for (const host of HOSTS) {
    const resolved = resolvePresentationFrame(host, frame);
    updateThreeCameraAspect(camera, currentFixedCamera, resolved.projectionAspectRatio);
    const projected = points.map(point => normalizedProjection(camera, point));
    if (baseline === null) baseline = projected;
    else {
      projected.forEach((value, index) => {
        assert.ok(Math.abs(value[0] - baseline[index][0]) < 1e-12);
        assert.ok(Math.abs(value[1] - baseline[index][1]) < 1e-12);
      });
    }
  }
});

test("scene without PresentationFrame retains legacy full-host projection", () => {
  const resolved = resolvePresentationFrame({ widthPx: 800, heightPx: 500 });
  assert.equal(resolved.active, false);
  assert.equal(resolved.fit, "legacy");
  assert.deepEqual(resolved.rasterRect, { xPx: 0, yPx: 0, widthPx: 800, heightPx: 500 });
  assert.equal(resolved.projectionAspectRatio, 1.6);
});

test("unsupported present policies and invalid inputs fail closed", () => {
  assert.throws(() => resolvePresentationFrame({ widthPx: 0, heightPx: 500 }, frame), /PRESENTATION_HOST_WIDTH_INVALID/);
  assert.throws(
    () => resolvePresentationFrame({ widthPx: 800, heightPx: 500 }, { ...frame, preferredAspectRatio: 0 }),
    /PRESENTATION_FRAME_ASPECT_INVALID/
  );
  assert.throws(
    () => resolvePresentationFrame({ widthPx: 800, heightPx: 500 }, { ...frame, fit: "cover" }),
    /PRESENTATION_FRAME_POLICY_UNSUPPORTED/
  );
});
