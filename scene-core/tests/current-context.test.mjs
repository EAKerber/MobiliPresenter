import assert from "node:assert/strict";
import test from "node:test";
import { validateScenePackage } from "../dist/src/contracts/invariants.js";
import { currentAppearance } from "../dist/src/fixtures/current-appearance.js";
import { currentSceneBase } from "../dist/src/fixtures/current-scene.js";
import { glassDivider, module03WithSink, module04, module05, module07 } from "../dist/src/fixtures/current-context.js";
import { module02, module06 } from "../dist/src/fixtures/current-geometry.js";
import { module01 } from "../dist/src/fixtures/current-laundry.js";
import { resolveEffectiveVisibility, resolveItemPlacementTransform, resolveWorldTransforms, setVisibilityIntent } from "../dist/src/state/scene-state.js";

function assertVecAlmost(actual, expected, epsilon = 1e-9) {
  assert.ok(actual);
  for (const key of ["x", "y", "z"]) {
    assert.ok(Math.abs(actual[key] - expected[key]) <= epsilon, `${key}: ${actual[key]} != ${expected[key]}`);
  }
}

test("current scene includes full validated context without provisional 600mm depth", () => {
  assert.deepEqual(validateScenePackage(currentSceneBase), []);
  const moduleIds = currentSceneBase.modules.map(module => module.id);
  assert.deepEqual(moduleIds, [
    "scene/traditional/module/upper-laundry",
    "scene/traditional/module/lower-stove",
    "scene/traditional/module/lower-sink",
    "scene/traditional/module/fridge-side",
    "scene/traditional/module/upper-stove",
    "scene/traditional/module/upper-sink-microwave",
    "scene/traditional/module/upper-fridge"
  ]);
  assert.deepEqual(module01.dimensions.geometryMm, { width: 763.25, height: 700, depth: 350 });
  assert.deepEqual(module05.dimensions.geometryMm, { width: 800, height: 700, depth: 400 });
  assert.deepEqual(module07.dimensions.geometryMm, { width: 800, height: 484, depth: 350 });
  assert.equal(currentSceneBase.modules.find(module => module.id.endsWith("upper-sink-microwave"))?.dimensions.geometryMm.depth, 400);
});

test("module 01 preserves Promob nominal/property evidence and DXF geometry", () => {
  assert.deepEqual(module01.dimensions.nominalMm, { width: 763.3, height: 700, depth: 350 });
  assert.deepEqual(module01.transform.translationMm, { x: 1568.684, y: 8288.827, z: 1697.064 });
  assert.equal(module01.geometry.filter(primitive => primitive.role === "front").length, 2);
});

test("glass divider is cross-source metric geometry", () => {
  assert.equal(currentSceneBase.environment.includes(glassDivider), true);
  const panel = glassDivider.geometry[0];
  assert.equal(panel?.primitive, "box");
  if (panel?.primitive !== "box") throw new Error("glass panel must be box geometry");
  assert.deepEqual(panel.sizeMm, { width: 8, height: 2601.63, depth: 400 });
  assert.equal(panel.materialSlot, "glass");
  assert.deepEqual(glassDivider.transform.translationMm, { x: 3063.739, y: 8032.528, z: 0 });
});

test("module 04 preserves nominal 600 depth while geometry uses DXF 610", () => {
  assert.equal(module04.dimensions.nominalMm?.depth, 600);
  assert.equal(module04.dimensions.geometryMm.depth, 610);
});

test("sink is promoted from DXF geometry as hosted default fixture", () => {
  const sinkSlot = module03WithSink.applianceSlots.find(slot => slot.role === "kitchen-sink");
  assert.ok(sinkSlot);
  assert.equal(sinkSlot.status, "confirmed");
  assert.deepEqual(sinkSlot.clearSizeMm, { width: 382.087, height: 178.1241, depth: 382.085 });
  assert.deepEqual(sinkSlot.localTransform.translationMm, { x: 417.295, y: 63.956, z: 580.8759 });
  const sink = currentSceneBase.items.find(item => item.definitionId === "FX-SINK-01");
  assert.equal(sink?.kind, "fixture");
  assert.equal(sink?.hostId, module03WithSink.id);
  assert.equal(sink?.slotId, sinkSlot.id);
  if (!sink) throw new Error("sink fixture missing");
  assertVecAlmost(resolveItemPlacementTransform(currentSceneBase, sink).translationMm, {
    x: 4280.044,
    y: 8184.396,
    z: 680.8759
  });
});

test("hood and cooktop slots remain explicit inferred geometry, never masquerading as confirmed Promob facts", () => {
  const hoodSlot = module05.applianceSlots.find(slot => slot.role === "hood");
  const cooktopSlot = module02.applianceSlots.find(slot => slot.role === "cooktop");
  assert.equal(hoodSlot?.status, "inferred");
  assert.equal(cooktopSlot?.status, "inferred");
  assert.ok(hoodSlot?.evidenceRefs?.some(ref => ref.startsWith("style-anchor:")));
  assert.ok(cooktopSlot?.evidenceRefs?.some(ref => ref.startsWith("style-anchor:")));
});

test("standalone washer and fridge use confirmed Promob placement while tank/range remain explicit inferred placements", () => {
  const washer = currentSceneBase.items.find(item => item.definitionId === "AP-WASHER-01");
  const fridge = currentSceneBase.items.find(item => item.definitionId === "AP-FRIDGE-01");
  const tank = currentSceneBase.items.find(item => item.definitionId === "AP-TANK-01");
  const range = currentSceneBase.items.find(item => item.definitionId === "AP-RANGE-01");
  assert.deepEqual(washer?.transform.translationMm, { x: 1641.934, y: 7908.81, z: 0 });
  assert.deepEqual(fridge?.transform.translationMm, { x: 5097.427, y: 7900.44, z: 0 });
  assert.equal(washer?.placementStatus, "confirmed");
  assert.equal(fridge?.placementStatus, "confirmed");
  assert.equal(tank?.placementStatus, "inferred");
  assert.equal(range?.placementStatus, "inferred");
  assert.ok(tank?.evidenceRefs?.some(ref => ref.startsWith("inference:")));
  assert.ok(range?.evidenceRefs?.some(ref => ref.startsWith("inference:")));
});

test("module02 and freestanding range form a reversible substitution group", () => {
  const baseline = resolveEffectiveVisibility(currentSceneBase);
  assert.equal(baseline.get(module02.id)?.effectiveVisible, true);
  assert.equal(baseline.get("scene/traditional/appliance/freestanding-range")?.effectiveVisible, false);
  const moduleHidden = setVisibilityIntent(currentSceneBase, module02.id, "off");
  const replacement = resolveEffectiveVisibility(moduleHidden);
  assert.equal(replacement.get("scene/traditional/appliance/freestanding-range")?.effectiveVisible, true);
});

test("hosted accessory geometry resolves to audited DXF world coordinates within floating tolerance", () => {
  const world = resolveWorldTransforms(currentSceneBase);
  const stoveStone = currentSceneBase.items.find(item => item.id.endsWith("stove-countertop"));
  const sinkStone = currentSceneBase.items.find(item => item.id.endsWith("sink-countertop"));
  const led = currentSceneBase.items.find(item => item.id.endsWith("under-cab-led-06"));
  assert.ok(stoveStone && sinkStone && led);
  assertVecAlmost(world.get(stoveStone.id)?.translationMm, { x: 3071.739, y: 8100.44, z: 858.9999 });
  assertVecAlmost(world.get(sinkStone.id)?.translationMm, { x: 3862.749, y: 8100.438, z: 859 });
  assertVecAlmost(world.get(led.id)?.translationMm, { x: 3879.427, y: 8250.44, z: 1559.09 });
});

test("washer fantasy language fits source envelope rather than enforcing reference dimensions", () => {
  const washerDefinition = currentAppearance.applianceDefinitions.find(definition => definition.id === "AP-WASHER-01");
  assert.equal(washerDefinition?.fitPolicy, "fit-to-source-envelope-preserve-front-proportions");
});
