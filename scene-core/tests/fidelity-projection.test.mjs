import assert from "node:assert/strict";
import test from "node:test";
import {
  createScreenMetricProfile,
  normalizeSupersampledError,
  projectMetricSegment,
  projectedPixelsPerMm
} from "../dist/src/fidelity/projection.js";
import { currentFixedCamera } from "../dist/src/fixtures/current-camera.js";

const canonical = { widthPx: 1865, heightPx: 967 };

test("4x fidelity profile renders at exactly four times canonical resolution", () => {
  const profile = createScreenMetricProfile(canonical, 4);
  assert.deepEqual(profile.renderViewport, { widthPx: 7460, heightPx: 3868 });
});

test("module 02 + 03 combined span is preserved in mm and projected pixels", () => {
  const profile = createScreenMetricProfile(canonical, 4);
  const segment = projectMetricSegment(
    currentFixedCamera,
    profile,
    { x: 3071.739, y: 8102.44, z: 100 },
    { x: 5079.427, y: 8102.44, z: 100 }
  );
  assert.ok(Math.abs(segment.physicalLengthMm - 2007.688) < 1e-9);
  assert.ok(Math.abs(segment.canonicalLengthPx - 595.6223325672106) < 1e-9);
  assert.ok(Math.abs(segment.renderedLengthPx - segment.canonicalLengthPx * 4) < 1e-9);
});

test("supersampling changes raster resolution but not normalized metric projection", () => {
  const a = { x: 3862.749, y: 8102.44, z: 100 };
  const b = { x: 4262.749, y: 8102.44, z: 100 };
  const one = projectMetricSegment(currentFixedCamera, createScreenMetricProfile(canonical, 1), a, b);
  const four = projectMetricSegment(currentFixedCamera, createScreenMetricProfile(canonical, 4), a, b);
  const eight = projectMetricSegment(currentFixedCamera, createScreenMetricProfile(canonical, 8), a, b);
  assert.ok(Math.abs(one.canonicalLengthPx - four.canonicalLengthPx) < 1e-9);
  assert.ok(Math.abs(one.canonicalLengthPx - eight.canonicalLengthPx) < 1e-9);
});

test("perspective scale is depth-local rather than global", () => {
  const profile = createScreenMetricProfile(canonical, 4);
  const lower = projectedPixelsPerMm(currentFixedCamera, profile, { x: 4000, y: 8102.44, z: 500 }, { x: 1, y: 0, z: 0 });
  const upper = projectedPixelsPerMm(currentFixedCamera, profile, { x: 4000, y: 8232.44, z: 1800 }, { x: 1, y: 0, z: 0 });
  assert.ok(lower > upper);
  assert.ok(lower > 0.29 && lower < 0.30, `lower scale ${lower}`);
  assert.ok(upper > 0.28 && upper < 0.29, `upper scale ${upper}`);
});

test("supersampled pixel error normalizes back to canonical pixels", () => {
  assert.equal(normalizeSupersampledError(4, 4), 1);
  assert.equal(normalizeSupersampledError(8, 8), 1);
});
