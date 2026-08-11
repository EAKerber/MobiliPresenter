import assert from "node:assert/strict";
import test from "node:test";
import { currentEnvironment, module02, module03, module06 } from "../dist/src/fixtures/current-geometry.js";

test("Layer 0 white wall and column are explicit semantic wall geometry", () => {
  assert.equal(currentEnvironment.geometry.length, 3);
  assert.equal(currentEnvironment.geometry.every(item => item.materialSlot === "wall"), true);
  const columnFront = currentEnvironment.geometry.find(item => item.id.endsWith("column-front"));
  const columnReturn = currentEnvironment.geometry.find(item => item.id.endsWith("column-return"));
  assert.deepEqual(columnFront?.sizeMm, [739.805, 2601.63]);
  assert.deepEqual(columnReturn?.sizeMm, [206.3, 2601.63]);
});

test("module 02 separates confirmed oven cavity from stable 600x600 front opening", () => {
  assert.equal(module02.dimensions.nominalMm?.width, 790);
  assert.equal(module02.dimensions.geometryMm.width, 791.01);
  const ovenSlot = module02.applianceSlots[0];
  assert.ok(ovenSlot);
  assert.deepEqual(ovenSlot.clearSizeMm, {
    width: 600,
    height: 600,
    depth: 525
  });
  assert.deepEqual(ovenSlot.cavitySizeMm, {
    width: 755.01,
    height: 724,
    depth: 525
  });
  assert.deepEqual(ovenSlot.frontOpening?.sizeMm, { width: 600, height: 600 });
  assert.equal(ovenSlot.frontOpening?.localTransform.translationMm.z, 80);
  assert.equal(ovenSlot.localTransform.translationMm.z, 82);
  assert.equal(ovenSlot.status, "inferred");
  assert.deepEqual(module02.applianceSlots[1]?.clearSizeMm, {
    width: 600,
    height: 60,
    depth: 520
  });
  assert.equal(module02.applianceSlots[1]?.status, "inferred");
});

test("module 02 front MDF surround is explicit and preserves 95/95/80/80 fields", () => {
  const fronts = new Map(module02.geometry.filter(item => item.role === "front").map(item => [item.id, item]));
  const left = fronts.get("scene/traditional/module/lower-stove/front/oven-left-stile");
  const right = fronts.get("scene/traditional/module/lower-stove/front/oven-right-stile");
  const bottom = fronts.get("scene/traditional/module/lower-stove/front/oven-bottom-rail");
  const top = fronts.get("scene/traditional/module/lower-stove/front/oven-top-rail");
  assert.ok(left && right && bottom && top);
  assert.deepEqual(left.sizeMm, { width: 95, height: 760, depth: 18 });
  assert.deepEqual(right.sizeMm, { width: 95, height: 760, depth: 18 });
  assert.deepEqual(bottom.sizeMm, { width: 600, height: 80, depth: 18 });
  assert.deepEqual(top.sizeMm, { width: 600, height: 80, depth: 18 });
  assert.equal(left.materialSlot, "front");
  assert.equal(right.materialSlot, "front");
  assert.equal(bottom.materialSlot, "front");
  assert.equal(top.materialSlot, "front");
});

test("module 03 preserves 1200 nominal and 1216.678 geometric width", () => {
  assert.equal(module03.dimensions.nominalMm?.width, 1200);
  assert.equal(module03.dimensions.geometryMm.width, 1216.678);
  const fronts = module03.geometry.filter(item => item.role === "front");
  assert.equal(fronts.length, 6);
  assert.equal(fronts.every(item => item.materialSlot === "front"), true);
});

test("module 06 is 1200x800x400 and carries confirmed microwave slot", () => {
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
  assert.equal(module06.applianceSlots[0]?.status, "confirmed");
  const fronts = module06.geometry.filter(item => item.role === "front");
  assert.equal(fronts.length, 3);
  assert.equal(fronts.every(item => item.materialSlot === "front"), true);
});
