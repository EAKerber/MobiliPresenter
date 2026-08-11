import assert from "node:assert/strict";
import test from "node:test";
import {
  STONE02_ID,
  STONE03_ID,
  currentSceneBase,
  module02,
  resolveEffectiveVisibility,
  resolveMaterialId
} from "@mobilipresenter/scene-core";
import { styleAnchorAppearance } from "../dist-ts/src/fixtures/style-anchor.js";
import {
  configurationFingerprint,
  createDefaultViewerConfiguration,
  createDefaultViewerInteraction,
  deriveViewerAppearance,
  deriveViewerScene,
  reduceViewerConfiguration,
  reduceViewerInteraction
} from "../dist-ts/src/runtime/viewer-state.js";

const OVEN_ID = "scene/traditional/appliance/oven";
const COOKTOP_ID = "scene/traditional/appliance/cooktop";
const RANGE_ID = "scene/traditional/appliance/freestanding-range";

test("module02 hide derives hosted visibility and replacement stove deterministically", () => {
  const initial = createDefaultViewerConfiguration();
  const hidden = reduceViewerConfiguration(initial, {
    type: "set-module-visibility",
    moduleId: module02.id,
    value: "off"
  });
  const scene = deriveViewerScene(currentSceneBase, hidden);
  const visibility = resolveEffectiveVisibility(scene);
  assert.equal(visibility.get(module02.id)?.effectiveVisible, false);
  assert.equal(visibility.get(OVEN_ID)?.effectiveVisible, false);
  assert.equal(visibility.get(COOKTOP_ID)?.effectiveVisible, false);
  assert.equal(visibility.get(RANGE_ID)?.effectiveVisible, true);

  const restored = reduceViewerConfiguration(hidden, {
    type: "set-module-visibility",
    moduleId: module02.id,
    value: "inherit"
  });
  assert.equal(configurationFingerprint(restored), configurationFingerprint(initial));
});

test("controlled appearance presets alter only derived appearance contracts", () => {
  let state = createDefaultViewerConfiguration();
  state = reduceViewerConfiguration(state, {
    type: "set-front-preset",
    moduleId: module02.id,
    presetId: "neutral-greige"
  });
  state = reduceViewerConfiguration(state, { type: "set-stone-preset", presetId: "graphite-speckled" });
  state = reduceViewerConfiguration(state, { type: "set-lighting-preset", presetId: "warm-worktop" });

  const scene = deriveViewerScene(currentSceneBase, state);
  const appearance = deriveViewerAppearance(styleAnchorAppearance, scene, state);
  assert.equal(resolveMaterialId(appearance, module02.id, "front"), "front-primary");
  assert.equal(resolveMaterialId(appearance, STONE02_ID, "stone"), "stone-speckled-graphite");
  assert.equal(resolveMaterialId(appearance, STONE03_ID, "stone"), "stone-speckled-graphite");
  assert.match(appearance.lighting.id, /warm-worktop$/);
  assert.deepEqual(scene.camera, currentSceneBase.camera);
  assert.deepEqual(scene.modules, currentSceneBase.modules);
});

test("configuration action order converges to the same fingerprint", () => {
  const initial = createDefaultViewerConfiguration();
  const a = reduceViewerConfiguration(
    reduceViewerConfiguration(initial, {
      type: "set-module-visibility",
      moduleId: module02.id,
      value: "off"
    }),
    { type: "set-front-preset", moduleId: module02.id, presetId: "neutral-greige" }
  );
  const b = reduceViewerConfiguration(
    reduceViewerConfiguration(initial, {
      type: "set-front-preset",
      moduleId: module02.id,
      presetId: "neutral-greige"
    }),
    { type: "set-module-visibility", moduleId: module02.id, value: "off" }
  );
  assert.equal(configurationFingerprint(a), configurationFingerprint(b));
});

test("invalid module ids are rejected during derivation", () => {
  const state = reduceViewerConfiguration(createDefaultViewerConfiguration(), {
    type: "set-module-visibility",
    moduleId: "scene/traditional/module/does-not-exist",
    value: "off"
  });
  assert.throws(() => deriveViewerScene(currentSceneBase, state), /VIEWER_MODULE_NOT_FOUND/);
});

test("interaction state stays independent and resettable", () => {
  const initial = createDefaultViewerInteraction();
  const selected = reduceViewerInteraction(initial, { type: "select-module", moduleId: module02.id });
  const hovered = reduceViewerInteraction(selected, { type: "hover-module", moduleId: module02.id });
  assert.equal(hovered.selectedModuleId, module02.id);
  assert.equal(hovered.hoveredModuleId, module02.id);
  assert.deepEqual(reduceViewerInteraction(hovered, { type: "reset-interaction" }), initial);
});
