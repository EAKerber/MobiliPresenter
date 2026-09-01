import assert from "node:assert/strict";
import test from "node:test";
import { currentSceneBase, resolveMaterialId } from "@mobilipresenter/scene-core";
import { styleAnchorAppearance } from "../dist-ts/src/fixtures/style-anchor.js";
import { parseViewerConfiguration } from "../dist-ts/src/runtime/query.js";
import {
  deriveViewerAppearance,
  deriveViewerScene,
  reduceViewerConfiguration
} from "../dist-ts/src/runtime/viewer-state.js";

const MODULE03_ID = "scene/traditional/module/lower-sink";
const LEGACY_GLOBAL_FRONT_QUERY = "01:neutral-greige,02:neutral-greige,03:neutral-greige,04:neutral-greige,05:neutral-greige,06:neutral-greige,07:neutral-greige";

function module03FrontMaterial(state) {
  const scene = deriveViewerScene(currentSceneBase, state);
  const appearance = deriveViewerAppearance(styleAnchorAppearance, scene, state);
  return resolveMaterialId(appearance, MODULE03_ID, "front");
}

test("historical all-module front query shadows the first-class global finish until reset", () => {
  let state = parseViewerConfiguration(new URLSearchParams({
    front: LEGACY_GLOBAL_FRONT_QUERY
  }));

  assert.equal(state.furnitureFinishPresetId, "neutral-greige");
  assert.equal(Object.keys(state.frontPresetByModule).length, 7);
  assert.equal(state.frontPresetByModule[MODULE03_ID], "neutral-greige");
  assert.equal(module03FrontMaterial(state), "front-primary");

  state = reduceViewerConfiguration(state, {
    type: "set-furniture-finish-preset",
    presetId: "warm-wood"
  });

  assert.equal(state.furnitureFinishPresetId, "warm-wood");
  assert.equal(state.frontPresetByModule[MODULE03_ID], "neutral-greige");
  assert.equal(
    module03FrontMaterial(state),
    "front-primary",
    "legacy per-module override wins over the new global furniture finish"
  );

  state = reduceViewerConfiguration(state, { type: "reset-configuration" });
  assert.deepEqual(state.frontPresetByModule, {});

  state = reduceViewerConfiguration(state, {
    type: "set-furniture-finish-preset",
    presetId: "warm-wood"
  });
  assert.equal(module03FrontMaterial(state), "front-wood");
});
