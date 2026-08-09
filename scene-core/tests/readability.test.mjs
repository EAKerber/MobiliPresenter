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
  assert.equal(a.length, 8);
  assert.equal(new Set(a.map(probe => probe.id)).size, a.length);
  assert.ok(a.some(probe => probe.role === "oven-surround"));
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
