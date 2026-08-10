import assert from "node:assert/strict";
import test from "node:test";
import {
  currentSceneBase,
  module02,
  module03WithSink,
  module06
} from "@mobilipresenter/scene-core";
import { Mesh } from "three";
import { styleAnchorAppearance } from "../dist-ts/src/fixtures/style-anchor.js";
import { buildThreeLighting } from "../dist-ts/src/renderer/three/lighting.js";
import { ThreeMaterialRegistry } from "../dist-ts/src/renderer/three/materials.js";
import { createModuleSelectionOverlay } from "../dist-ts/src/renderer/three/selection.js";
import { buildThreeScene } from "../dist-ts/src/renderer/three/scene-adapter.js";
import {
  createDefaultViewerConfiguration,
  deriveViewerAppearance,
  deriveViewerScene,
  reduceViewerConfiguration
} from "../dist-ts/src/runtime/viewer-state.js";

const OVEN_ID = "scene/traditional/appliance/oven";
const COOKTOP_ID = "scene/traditional/appliance/cooktop";
const RANGE_ID = "scene/traditional/appliance/freestanding-range";
const MICRO_ID = "scene/traditional/appliance/microwave";
const LED_ID = "scene/traditional/accessory/under-cab-led-06";
const STONE03_ID = "scene/traditional/accessory/stone-03";

function build(state) {
  const scene = deriveViewerScene(currentSceneBase, state);
  const appearance = deriveViewerAppearance(styleAnchorAppearance, scene, state);
  const registry = new ThreeMaterialRegistry(appearance);
  const adapter = buildThreeScene(scene, (entityId, slot) => registry.resolve(entityId, slot));
  return { scene, appearance, registry, adapter };
}

function firstMaterialIdForSlot(group, slot) {
  let materialId = null;
  group.traverse(object => {
    if (materialId !== null || !(object instanceof Mesh) || object.userData.materialSlot !== slot) return;
    const material = Array.isArray(object.material) ? object.material[0] : object.material;
    materialId = material?.userData.materialDefinitionId ?? null;
  });
  return materialId;
}

test("hide module02 reaches Three groups and activates the replacement stove", () => {
  const state = reduceViewerConfiguration(createDefaultViewerConfiguration(), {
    type: "set-module-visibility",
    moduleId: module02.id,
    value: "off"
  });
  const { registry, adapter } = build(state);
  assert.equal(adapter.entityGroups.get(module02.id)?.visible, false);
  assert.equal(adapter.entityGroups.get(OVEN_ID)?.visible, false);
  assert.equal(adapter.entityGroups.get(COOKTOP_ID)?.visible, false);
  assert.equal(adapter.entityGroups.get(RANGE_ID)?.visible, true);
  registry.dispose();
});

test("hide module06 reaches microwave and hosted LED groups", () => {
  const state = reduceViewerConfiguration(createDefaultViewerConfiguration(), {
    type: "set-module-visibility",
    moduleId: module06.id,
    value: "off"
  });
  const { registry, adapter } = build(state);
  assert.equal(adapter.entityGroups.get(module06.id)?.visible, false);
  assert.equal(adapter.entityGroups.get(MICRO_ID)?.visible, false);
  assert.equal(adapter.entityGroups.get(LED_ID)?.visible, false);
  registry.dispose();
});

test("front and stone presets reach actual Three materials without geometry changes", () => {
  let state = createDefaultViewerConfiguration();
  state = reduceViewerConfiguration(state, {
    type: "set-front-preset",
    moduleId: module03WithSink.id,
    presetId: "neutral-greige"
  });
  state = reduceViewerConfiguration(state, { type: "set-stone-preset", presetId: "graphite-speckled" });
  const { scene, registry, adapter } = build(state);

  assert.equal(firstMaterialIdForSlot(adapter.entityGroups.get(module03WithSink.id), "front"), "front-primary");
  assert.equal(firstMaterialIdForSlot(adapter.entityGroups.get(STONE03_ID), "stone"), "stone-speckled-graphite");
  assert.deepEqual(scene.modules, currentSceneBase.modules);
  assert.deepEqual(scene.camera, currentSceneBase.camera);
  registry.dispose();
});

test("lighting preset reaches the Three base rig while preserving scene geometry", () => {
  const state = reduceViewerConfiguration(createDefaultViewerConfiguration(), {
    type: "set-lighting-preset",
    presetId: "warm-worktop"
  });
  const { scene, appearance, registry } = build(state);
  const lighting = buildThreeLighting(scene, appearance);
  const key = lighting.baseLights.get("key-front-high");
  assert.ok(key);
  assert.match(appearance.lighting.id, /warm-worktop$/);
  assert.ok(key.intensity > 0);
  assert.deepEqual(scene.modules, currentSceneBase.modules);
  registry.dispose();
});

test("selection overlay is interaction-only and does not draw hidden modules", () => {
  const visible = build(createDefaultViewerConfiguration());
  const visibleOverlay = createModuleSelectionOverlay(visible.adapter, visible.scene);
  visibleOverlay.setSelectedModule(module02.id);
  assert.equal(visibleOverlay.getSelectedModuleId(), module02.id);
  assert.equal(visibleOverlay.root.children.length, 1);
  visibleOverlay.dispose();
  visible.registry.dispose();

  const hiddenState = reduceViewerConfiguration(createDefaultViewerConfiguration(), {
    type: "set-module-visibility",
    moduleId: module02.id,
    value: "off"
  });
  const hidden = build(hiddenState);
  const hiddenOverlay = createModuleSelectionOverlay(hidden.adapter, hidden.scene);
  hiddenOverlay.setSelectedModule(module02.id);
  assert.equal(hiddenOverlay.getSelectedModuleId(), module02.id);
  assert.equal(hiddenOverlay.root.children.length, 0);
  hiddenOverlay.dispose();
  hidden.registry.dispose();
});
