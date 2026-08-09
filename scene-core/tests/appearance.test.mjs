import assert from "node:assert/strict";
import test from "node:test";
import { validateScenePackage } from "../dist/src/contracts/invariants.js";
import { validateAppearanceForScene } from "../dist/src/appearance/invariants.js";
import { resolveLighting } from "../dist/src/appearance/lighting.js";
import { sceneGeometryDigest } from "../dist/src/core/signature.js";
import { identityTransform } from "../dist/src/contracts/model.js";
import { currentAppearance } from "../dist/src/fixtures/current-appearance.js";
import { currentSceneBase } from "../dist/src/fixtures/current-scene.js";
import { module06 } from "../dist/src/fixtures/current-geometry.js";
import { setVisibilityIntent } from "../dist/src/state/scene-state.js";

test("current scene and appearance packages are internally coherent", () => {
  assert.deepEqual(validateScenePackage(currentSceneBase), []);
  assert.deepEqual(validateAppearanceForScene(currentSceneBase, currentAppearance), []);
});

test("fantasy appliance catalog is stable and includes hood", () => {
  const ids = currentAppearance.applianceDefinitions.map(definition => definition.id).sort();
  assert.deepEqual(ids, [
    "AP-COOKTOP-01", "AP-FRIDGE-01", "AP-HOOD-01", "AP-MICRO-01",
    "AP-OVEN-01", "AP-TANK-01", "AP-WASHER-01", "FX-SINK-01"
  ]);
  const hood = currentAppearance.applianceDefinitions.find(definition => definition.id === "AP-HOOD-01");
  assert.equal(hood?.emitters.length, 1);
});

test("host visibility controls semantic emitters without changing base rig", () => {
  const hoodId = "scene/test/appliance/hood";
  const sceneWithHood = {
    ...currentSceneBase,
    items: [...currentSceneBase.items, {
      id: hoodId,
      kind: "appliance",
      definitionId: "AP-HOOD-01",
      transform: identityTransform(),
      visibilityIntent: "auto",
      defaultVisible: true,
      controllable: true,
      mountPolicy: "hosted",
      hostId: module06.id
    }]
  };
  const visible = resolveLighting(sceneWithHood, currentAppearance);
  assert.equal(visible.semanticEmitters.length, 1);
  const hiddenScene = setVisibilityIntent(sceneWithHood, module06.id, "off");
  const hidden = resolveLighting(hiddenScene, currentAppearance);
  assert.equal(hidden.semanticEmitters.length, 0);
  assert.deepEqual(hidden.baseRig, visible.baseRig);
});

test("visibility and appearance changes do not mutate geometry digest", () => {
  const before = sceneGeometryDigest(currentSceneBase);
  const hidden = setVisibilityIntent(currentSceneBase, module06.id, "off");
  assert.equal(sceneGeometryDigest(hidden), before);
  const changedAppearance = {
    ...currentAppearance,
    materials: currentAppearance.materials.map(material => material.id === "front-primary"
      ? { ...material, baseColorSrgb: "#777777" }
      : material)
  };
  assert.equal(changedAppearance.materials.find(material => material.id === "front-primary")?.baseColorSrgb, "#777777");
  assert.equal(sceneGeometryDigest(currentSceneBase), before);
});
