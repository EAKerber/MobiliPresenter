import assert from "node:assert/strict";
import test from "node:test";
import { module02, module03WithSink, module06 } from "@mobilipresenter/scene-core";
import { parseViewerConfiguration, parseViewerInteraction } from "../dist-ts/src/runtime/query.js";

test("runtime query composes hide, front, stone and light state", () => {
  const query = new URLSearchParams(
    "hide=02&front=03:neutral-greige&stone=graphite-speckled&light=warm-worktop"
  );
  const state = parseViewerConfiguration(query);
  assert.equal(state.visibilityByModule[module02.id], "off");
  assert.equal(state.frontPresetByModule[module03WithSink.id], "neutral-greige");
  assert.equal(state.stonePresetId, "graphite-speckled");
  assert.equal(state.lightingPresetId, "warm-worktop");
});

test("runtime query selection maps stable module aliases", () => {
  const interaction = parseViewerInteraction(new URLSearchParams("select=06"));
  assert.equal(interaction.selectedModuleId, module06.id);
});

test("runtime query rejects unknown aliases and presets", () => {
  assert.throws(() => parseViewerConfiguration(new URLSearchParams("hide=99")), /VIEWER_MODULE_ALIAS_UNKNOWN/);
  assert.throws(() => parseViewerConfiguration(new URLSearchParams("front=02:magenta")), /VIEWER_FRONT_PRESET_NOT_FOUND/);
  assert.throws(() => parseViewerConfiguration(new URLSearchParams("stone=unknown")), /VIEWER_STONE_PRESET_NOT_FOUND/);
  assert.throws(() => parseViewerConfiguration(new URLSearchParams("light=unknown")), /VIEWER_LIGHTING_PRESET_NOT_FOUND/);
});
