import assert from "node:assert/strict";
import test from "node:test";
import { currentEnvironment, module02, module03, module06 } from "../dist/src/fixtures/current-geometry.js";

test("Layer 0 white wall and column are explicit geometry", () => {
  assert.equal(currentEnvironment.geometry.length, 3);
  assert.equal(currentEnvironment.geometry.every(item => item.materialSlot === "wall-white"), true);
  const columnFront = currentEnvironment.geometry.find(item => item.id.endsWith("column-front"));
  const columnReturn = currentEnvironment.geometry.find(item => item.id.endsWith("column-return"));
  assert.deepEqual(columnFront?.sizeMm, [739.805, 2601.63]);
  assert.deepEqual(columnReturn?.sizeMm, [206.3, 2601.63]);
});

test("module 02 preserves nominal and geometric width plus oven slot", () => {
  assert.equal(module02.dimensions.nominalMm?.width, 790);
  assert.equal(module02.dimensions.geometryMm.width, 791.01);
  assert.deepEqual(module02.applianceSlots[0]?.clearSizeMm, {
    width: 755.01,
    height: 724,
    depth: 525
  });
});

test("module 03 preserves 1200 nominal and 1216.678 geometric width", () => {
  assert.equal(module03.dimensions.nominalMm?.width, 1200);
  assert.equal(module03.dimensions.geometryMm.width, 1216.678);
  const fronts = module03.geometry.filter(item => item.role === "front");
  assert.equal(fronts.length, 6);
});

test("module 06 is 1200x800x400 and carries microwave slot", () => {
  assert.deepEqual(module06.dimensions.geometryMm, {
    width: 1200,
    height: 800,
    depth: 400
  });
  assert.deepEqual(module06.applianceSlots[0]?.clearSizeMm, {
    width: 550,
    height: 406,
    depth: 394
  });
  const fronts = module06.geometry.filter(item => item.role === "front");
  assert.equal(fronts.length, 3);
});
