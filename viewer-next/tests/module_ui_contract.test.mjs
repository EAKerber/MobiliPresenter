import assert from "node:assert/strict";
import test from "node:test";
import {
  currentSceneBase,
  module03WithSink,
  resolveMaterialId
} from "@mobilipresenter/scene-core";
import { CURRENT_VIEWER_UI_CATALOG } from "../dist-ts/src/api/ui-adapter.js";
import { styleAnchorAppearance } from "../dist-ts/src/fixtures/style-anchor.js";
import { CURRENT_TECHNICAL_CATALOG } from "../dist-ts/src/presentation/technical-catalog.js";
import {
  createDefaultViewerConfiguration,
  deriveViewerAppearance,
  reduceViewerConfiguration
} from "../dist-ts/src/runtime/viewer-state.js";

test("module UI catalog publishes all seven modules without requiring selection", () => {
  assert.deepEqual(CURRENT_VIEWER_UI_CATALOG.modules, ["01", "02", "03", "04", "05", "06", "07"]);
  assert.equal(CURRENT_VIEWER_UI_CATALOG.moduleDescriptors.length, 7);
  assert.ok(CURRENT_VIEWER_UI_CATALOG.moduleDescriptors.every(descriptor => descriptor.technicalPresentationStatus === "ready"));

  const module01 = CURRENT_VIEWER_UI_CATALOG.moduleDescriptors.find(descriptor => descriptor.alias === "01");
  assert.equal(module01?.title, "Aéreo da lavanderia");
  assert.equal(module01?.dimensions.nominalMm?.width, 763.3, "Scene Core physical authority must win over rounded sheet display");

  const module04 = CURRENT_VIEWER_UI_CATALOG.moduleDescriptors.find(descriptor => descriptor.alias === "04");
  assert.deepEqual(module04?.dimensions.display.order, ["height", "depth", "width"]);
  assert.deepEqual(module04?.dimensions.display.labels, { height: "A", depth: "P", width: "E" });
});

test("technical catalog covers modules 01 through 07 and declares presentation companions", () => {
  const moduleEntries = CURRENT_TECHNICAL_CATALOG.filter(entry => entry.target.kind === "module");
  assert.deepEqual(moduleEntries.map(entry => entry.identity.alias), ["01", "02", "03", "04", "05", "06", "07"]);

  const module02 = moduleEntries.find(entry => entry.identity.alias === "02");
  assert.ok(module02?.presentation?.companionEntityIds.includes("scene/traditional/appliance/oven"));
  assert.ok(module02?.presentation?.companionEntityIds.includes("scene/traditional/appliance/cooktop"));

  const module06 = moduleEntries.find(entry => entry.identity.alias === "06");
  assert.ok(module06?.presentation?.companionEntityIds.includes("scene/traditional/appliance/microwave"));
  assert.ok(module06?.presentation?.companionEntityIds.includes("scene/traditional/accessory/under-cab-led-06"));

  const module07 = moduleEntries.find(entry => entry.identity.alias === "07");
  assert.deepEqual(module07?.presentation?.companionEntityIds, ["scene/traditional/appliance/fridge"]);
});

test("neutral furniture finish is canonical default and applies to module 03", () => {
  const configuration = createDefaultViewerConfiguration();
  assert.equal(configuration.furnitureFinishPresetId, "neutral-greige");
  assert.deepEqual(configuration.frontPresetByModule, {});

  const appearance = deriveViewerAppearance(styleAnchorAppearance, currentSceneBase, configuration);
  assert.equal(resolveMaterialId(appearance, module03WithSink.id, "front"), "front-primary");
});

test("global furniture finish changes all front-capable modules with one configuration action", () => {
  const initial = createDefaultViewerConfiguration();
  const warm = reduceViewerConfiguration(initial, {
    type: "set-furniture-finish-preset",
    presetId: "warm-wood"
  });
  const appearance = deriveViewerAppearance(styleAnchorAppearance, currentSceneBase, warm);

  for (const module of currentSceneBase.modules) {
    if (!module.geometry.some(primitive => primitive.materialSlot === "front")) continue;
    assert.equal(resolveMaterialId(appearance, module.id, "front"), "front-wood", module.id);
  }
});

test("finish options publish visual metadata from material authority", () => {
  const warm = CURRENT_VIEWER_UI_CATALOG.furnitureFinishPresets.find(option => option.id === "warm-wood");
  const neutral = CURRENT_VIEWER_UI_CATALOG.furnitureFinishPresets.find(option => option.id === "neutral-greige");
  assert.equal(warm?.visual?.materialId, "front-wood");
  assert.equal(warm?.visual?.previewColorSrgb, "#A8744D");
  assert.equal(neutral?.visual?.materialId, "front-primary");
  assert.equal(neutral?.visual?.previewColorSrgb, "#B2ADA5");
});
