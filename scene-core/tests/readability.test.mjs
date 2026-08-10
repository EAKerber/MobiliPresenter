import assert from "node:assert/strict";
import test from "node:test";
import {
  currentProjectedReadabilityProbes,
  currentReadabilityProbes
} from "../dist/src/fidelity/readability.js";

test("current readability probe set is deterministic and semantic", () => {
  const a = currentProjectedReadabilityProbes();
  const b = currentProjectedReadabilityProbes();
  assert.deepEqual(a, b);
  assert.equal(a.length, 10);
  assert.equal(new Set(a.map(probe => probe.id)).size, a.length);
  const oven = a.filter(probe => probe.role === "oven-surround");
  assert.equal(oven.length, 4);
  assert.deepEqual(new Set(oven.map(probe => probe.id)), new Set([
    "module02/oven-opening-left",
    "module02/oven-opening-right",
    "module02/oven-opening-bottom",
    "module02/oven-opening-top"
  ]));
  assert.ok(a.some(probe => probe.id.startsWith("module01/")));
});

test("all projected probes are finite and use 4x search bands", () => {
  for (const probe of currentProjectedReadabilityProbes()) {
    for (const value of [...probe.aPx4x, ...probe.bPx4x, ...probe.aCanonicalPx, ...probe.bCanonicalPx]) {
      assert.ok(Number.isFinite(value));
    }
    assert.equal(probe.searchBandPx4x, probe.searchBandCanonicalPx * 4);
  }
});

test("metric probes preserve physical world endpoints as authority", () => {
  const projected = currentProjectedReadabilityProbes();
  for (let i = 0; i < currentReadabilityProbes.length; i += 1) {
    assert.deepEqual(projected[i].aMm, currentReadabilityProbes[i].aMm);
    assert.deepEqual(projected[i].bMm, currentReadabilityProbes[i].bMm);
  }
});

test("module02 probes follow the real 600x600 front opening rather than the old cavity edges", () => {
  const byId = new Map(currentReadabilityProbes.map(probe => [probe.id, probe]));
  assert.deepEqual(byId.get("module02/oven-opening-left")?.aMm, { x: 3167.244, y: 8102.44, z: 179 });
  assert.deepEqual(byId.get("module02/oven-opening-left")?.bMm, { x: 3167.244, y: 8102.44, z: 779 });
  assert.deepEqual(byId.get("module02/oven-opening-right")?.aMm, { x: 3767.244, y: 8102.44, z: 179 });
  assert.deepEqual(byId.get("module02/oven-opening-bottom")?.bMm, { x: 3767.244, y: 8102.44, z: 179 });
  assert.deepEqual(byId.get("module02/oven-opening-top")?.bMm, { x: 3767.244, y: 8102.44, z: 779 });
});
