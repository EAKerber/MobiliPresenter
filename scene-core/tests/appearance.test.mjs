import assert from "node:assert/strict";
import test from "node:test";
import { validateScenePackage } from "../dist/src/contracts/invariants.js";
import { validateAppearanceForScene } from "../dist/src/appearance/invariants.js";
import { resolveLighting } from "../dist/src/appearance/lighting.js";
import { resolveMaterialId, setEntityMaterialOverride } from "../dist/src/appearance/materials.js";
import { sceneGeometryDigest } from "../dist/src/core/signature.js";
import { currentAppearance } from "../dist/src/fixtures/current-appearance.js";
import { currentSceneBase } from "../dist/src/fixtures/current-scene.js";
import { module03WithSink, module05 } from "../dist/src/fixtures/current-context.js";
import { module06 } from "../dist/src/fixtures/current-geometry.js";
import { setVisibilityIntent } from "../dist/src/state/scene-state.js";

test("current scene and appearance packages are internally coherent", () => {
  assert.deepEqual(validateScenePackage(currentSceneBase), []);
  assert.deepEqual(validateAppearanceForScene(currentSceneBase, currentAppearance), []);
});

test("fantasy appliance and accessory catalogs are stable", () => {
  const applianceIds = currentAppearance.applianceDefinitions.map(definition => definition.id).sort();
  assert.deepEqual(applianceIds, [
    "AP-COOKTOP-01", "AP-FRIDGE-01", "AP-HOOD-01", "AP-MICRO-01",
    "AP-OVEN-01", "AP-RANGE-01", "AP-TANK-01", "AP-WASHER-01", "FX-SINK-01"
  ]);
  const accessoryIds = currentAppearance.accessoryDefinitions.map(definition => definition.id).sort();
  assert.deepEqual(accessoryIds, ["ACC-PLINTH-LOWER", "ACC-STONE-COUNTERTOP", "ACC-UNDERCAB-LED-01"]);
});

test("canonical lighting resolves hood and under-cab emitters independently", () => {
  const baseline = resolveLighting(currentSceneBase, currentAppearance);
  assert.equal(baseline.environment.type, "neutral-room-pmrem");
  assert.deepEqual(baseline.semanticEmitters.map(emitter => emitter.definitionId).sort(), ["ACC-UNDERCAB-LED-01", "AP-HOOD-01"]);

  const hoodHiddenScene = setVisibilityIntent(currentSceneBase, module05.id, "off");
  const hoodHidden = resolveLighting(hoodHiddenScene, currentAppearance);
  assert.deepEqual(hoodHidden.semanticEmitters.map(emitter => emitter.definitionId), ["ACC-UNDERCAB-LED-01"]);

  const ledHiddenScene = setVisibilityIntent(currentSceneBase, module06.id, "off");
  const ledHidden = resolveLighting(ledHiddenScene, currentAppearance);
  assert.deepEqual(ledHidden.semanticEmitters.map(emitter => emitter.definitionId), ["AP-HOOD-01"]);

  const bothHidden = resolveLighting(setVisibilityIntent(hoodHiddenScene, module06.id, "off"), currentAppearance);
  assert.equal(bothHidden.semanticEmitters.length, 0);
  assert.deepEqual(bothHidden.baseRig, baseline.baseRig);
  assert.deepEqual(bothHidden.environment, baseline.environment);
});

test("entity material override is isolated and geometry-neutral", () => {
  const before = sceneGeometryDigest(currentSceneBase);
  assert.equal(resolveMaterialId(currentAppearance, module03WithSink.id, "front"), "front-primary");
  assert.equal(resolveMaterialId(currentAppearance, module06.id, "front"), "front-primary");

  const overridden = setEntityMaterialOverride(currentAppearance, module03WithSink.id, "front", "front-wood");
  assert.equal(resolveMaterialId(overridden, module03WithSink.id, "front"), "front-wood");
  assert.equal(resolveMaterialId(overridden, module06.id, "front"), "front-primary");
  assert.equal(sceneGeometryDigest(currentSceneBase), before);
});

test("visibility changes do not mutate geometry digest", () => {
  const before = sceneGeometryDigest(currentSceneBase);
  const hidden = setVisibilityIntent(currentSceneBase, module06.id, "off");
  assert.equal(sceneGeometryDigest(hidden), before);
});

test("standalone appliances carry target envelopes required by their fit policies", () => {
  const washer = currentSceneBase.items.find(item => item.definitionId === "AP-WASHER-01");
  const fridge = currentSceneBase.items.find(item => item.definitionId === "AP-FRIDGE-01");
  const range = currentSceneBase.items.find(item => item.definitionId === "AP-RANGE-01");
  const tank = currentSceneBase.items.find(item => item.definitionId === "AP-TANK-01");
  assert.deepEqual(washer?.targetEnvelopeMm, { width: 690, height: 990, depth: 730 });
  assert.deepEqual(fridge?.targetEnvelopeMm, { width: 809, height: 1900, depth: 750 });
  assert.deepEqual(range?.targetEnvelopeMm, { width: 760, height: 970, depth: 650 });
  assert.deepEqual(tank?.targetEnvelopeMm, { width: 500, height: 820, depth: 500 });
});
