import assert from "node:assert/strict";
import test from "node:test";
import {
  buildCurrentFidelityReport,
  compareFidelityReports
} from "../dist/src/fidelity/report.js";

test("current candidate report has green F0-F4 hard gates and pending readability/appearance work", () => {
  const first = buildCurrentFidelityReport();
  const second = buildCurrentFidelityReport();
  assert.deepEqual(second, first);
  assert.equal(first.schemaVersion, "FidelityReport 1.0");
  assert.equal(first.hardGatesPass, true);

  const byId = new Map(first.checks.map(item => [item.id, item]));
  assert.equal(byId.get("required-entity:scene/traditional/module/upper-laundry")?.status, "pass");
  assert.equal(byId.get("required-entity:scene/traditional/fixture/laundry-tank")?.status, "pass");
  assert.equal(byId.get("required-entity:scene/traditional/appliance/freestanding-range")?.status, "pass");
  assert.equal(byId.get("topology:module02-oven-surround")?.status, "pass");
  assert.equal(byId.get("metric:module02-plus-module03-span")?.status, "pass");
  assert.equal(byId.get("projection:module02-plus-module03-span")?.status, "pass");
  assert.equal(byId.get("hardware:anchors-defined")?.status, "pass");
  assert.equal(byId.get("readability:semantic-edge-baseline")?.status, "pending");
});

test("hard-gate comparison reports pass-to-fail regressions only", () => {
  const candidate = buildCurrentFidelityReport();
  const regressed = {
    ...candidate,
    checks: candidate.checks.map(item =>
      item.id === "metric:module02-plus-module03-span"
        ? { ...item, status: "fail" }
        : item
    )
  };
  const regressions = compareFidelityReports(candidate, regressed);
  assert.equal(regressions.length, 1);
  assert.equal(regressions[0].id, "metric:module02-plus-module03-span");
});
