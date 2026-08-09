import assert from "node:assert/strict";
import test from "node:test";
import { validateScenePackage } from "../dist/src/contracts/invariants.js";
import { currentAppearance } from "../dist/src/fixtures/current-appearance.js";
import { currentSceneBase } from "../dist/src/fixtures/current-scene.js";
import { glassDivider, module03WithSink, module04, module05, module07 } from "../dist/src/fixtures/current-context.js";

test("current scene includes full validated context without provisional 600mm depth", () => {
  assert.deepEqual(validateScenePackage(currentSceneBase), []);
  const moduleIds = currentSceneBase.modules.map(module => module.id);
  assert.deepEqual(moduleIds, [
    "scene/traditional/module/lower-stove",
    "scene/traditional/module/lower-sink",
    "scene/traditional/module/fridge-side",
    "scene/traditional/module/upper-stove",
    "scene/traditional/module/upper-sink-microwave",
    "scene/traditional/module/upper-fridge"
  ]);
  assert.deepEqual(module05.dimensions.geometryMm, { width: 800, height: 700, depth: 400 });
  assert.deepEqual(module07.dimensions.geometryMm, { width: 800, height: 484, depth: 350 });
  assert.equal(currentSceneBase.modules.find(module => module.id.endsWith("upper-sink-microwave"))?.dimensions.geometryMm.depth, 400);
});

test("glass divider is cross-source metric geometry", () => {
  assert.equal(currentSceneBase.environment.includes(glassDivider), true);
  const panel = glassDivider.geometry[0];
  assert.equal(panel?.primitive, "box");
  if (panel?.primitive !== "box") throw new Error("glass panel must be box geometry");
  assert.deepEqual(panel.sizeMm, { width: 8, height: 2601.63, depth: 400 });
  assert.deepEqual(glassDivider.transform.translationMm, { x: 3063.739, y: 8032.528, z: 0 });
});

test("module 04 preserves nominal 600 depth while geometry uses DXF 610", () => {
  assert.equal(module04.dimensions.nominalMm?.depth, 600);
  assert.equal(module04.dimensions.geometryMm.depth, 610);
});

test("sink is promoted from DXF geometry as hosted default fixture", () => {
  const sinkSlot = module03WithSink.applianceSlots.find(slot => slot.role === "kitchen-sink");
  assert.ok(sinkSlot);
  assert.deepEqual(sinkSlot.clearSizeMm, { width: 382.087, height: 178.1241, depth: 382.085 });
  assert.deepEqual(sinkSlot.localTransform.translationMm, { x: 417.295, y: 63.956, z: 580.8759 });
  const sink = currentSceneBase.items.find(item => item.definitionId === "FX-SINK-01");
  assert.equal(sink?.kind, "fixture");
  assert.equal(sink?.hostId, module03WithSink.id);
  assert.equal(sink?.slotId, sinkSlot.id);
});

test("standalone washer and fridge use Promob source placement", () => {
  const washer = currentSceneBase.items.find(item => item.definitionId === "AP-WASHER-01");
  const fridge = currentSceneBase.items.find(item => item.definitionId === "AP-FRIDGE-01");
  assert.deepEqual(washer?.transform.translationMm, { x: 1641.934, y: 7908.81, z: 0 });
  assert.deepEqual(fridge?.transform.translationMm, { x: 5097.427, y: 7900.44, z: 0 });
  assert.equal(washer?.mountPolicy, "standalone");
  assert.equal(fridge?.mountPolicy, "standalone");
});

test("washer fantasy language fits source envelope rather than enforcing reference dimensions", () => {
  const washerDefinition = currentAppearance.applianceDefinitions.find(definition => definition.id === "AP-WASHER-01");
  assert.equal(washerDefinition?.fitPolicy, "fit-to-source-envelope-preserve-front-proportions");
});
