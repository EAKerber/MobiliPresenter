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
  assert.equal(a.length, 14);
  assert.equal(new Set(a.map(probe => probe.id)).size, a.length);
  const oven = a.filter(probe => probe.role === "oven-surround");
  assert.equal(oven.length, 4);
  assert.deepEqual(new Set(oven.map(probe => probe.id)), new Set([
    "module02/oven-opening-left",
    "module02/oven-opening-right",
    "module02/oven-opening-bottom",
    "module02/oven-opening-top"
  ]));
  const sink = a.filter(probe => probe.role === "sink-opening");
  assert.equal(sink.length, 4);
  assert.deepEqual(new Set(sink.map(probe => probe.id)), new Set([
    "sink/opening/front",
    "sink/opening/back",
    "sink/opening/left",
    "sink/opening/right"
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

test("sink probes follow the true rounded stone opening at the 30mm stone top", () => {
  const byId = new Map(currentReadabilityProbes.map(probe => [probe.id, probe]));
  const x0 = 4294.3722625;
  const x1 = 4647.8027375;
  const y0 = 8227.3797875;
  const y1 = 8523.4972125;
  const z = 889;
  assert.deepEqual(byId.get("sink/opening/front")?.aMm, { x: x0, y: y0, z });
  assert.deepEqual(byId.get("sink/opening/front")?.bMm, { x: x1, y: y0, z });
  assert.deepEqual(byId.get("sink/opening/back")?.aMm, { x: x0, y: y1, z });
  assert.deepEqual(byId.get("sink/opening/back")?.bMm, { x: x1, y: y1, z });
  assert.deepEqual(byId.get("sink/opening/left")?.bMm, { x: x0, y: y1, z });
  assert.deepEqual(byId.get("sink/opening/right")?.bMm, { x: x1, y: y1, z });
  for (const id of ["sink/opening/front", "sink/opening/back", "sink/opening/left", "sink/opening/right"]) {
    assert.equal(byId.get(id)?.contrastThreshold, 0.02);
    assert.equal(byId.get(id)?.searchBandCanonicalPx, 4);
  }
});
