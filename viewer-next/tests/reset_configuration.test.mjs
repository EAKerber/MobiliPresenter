import assert from "node:assert/strict";
import test from "node:test";
import { currentSceneBase, resolveMaterialId } from "@mobilipresenter/scene-core";
import { styleAnchorAppearance } from "../dist-ts/src/fixtures/style-anchor.js";
import { moduleIdFromAlias } from "../dist-ts/src/runtime/query.js";
import {
  createDefaultViewerConfiguration,
  deriveViewerAppearance,
  deriveViewerScene,
  reduceViewerConfiguration
} from "../dist-ts/src/runtime/viewer-state.js";

test("reset restores the canonical neutral furniture finish for module 03 and every front-capable module", () => {
  const module03 = moduleIdFromAlias("03");
  const baseline = createDefaultViewerConfiguration();
  const customized = reduceViewerConfiguration(
    reduceViewerConfiguration(baseline, {
      type: "set-furniture-finish-preset",
      presetId: "warm-wood"
    }),
    {
      type: "set-front-preset",
      moduleId: module03,
      presetId: "warm-wood"
    }
  );

  const restored = reduceViewerConfiguration(customized, { type: "reset-configuration" });
  assert.deepEqual(restored, baseline);
  assert.equal(restored.furnitureFinishPresetId, "neutral-greige");
  assert.equal(restored.frontPresetByModule[module03], undefined);

  const scene = deriveViewerScene(currentSceneBase, restored);
  const appearance = deriveViewerAppearance(styleAnchorAppearance, scene, restored);
  const frontCapableModules = scene.modules.filter(module =>
    module.geometry.some(primitive => primitive.materialSlot === "front")
  );

  assert.ok(frontCapableModules.some(module => module.id === module03));
  for (const module of frontCapableModules) {
    assert.equal(
      resolveMaterialId(appearance, module.id, "front"),
      "front-primary",
      `reset left ${module.id} outside the canonical neutral finish`
    );
  }
});
