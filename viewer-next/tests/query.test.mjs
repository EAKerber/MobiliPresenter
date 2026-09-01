import assert from "node:assert/strict";
import test from "node:test";
import { module02, module03WithSink, module06 } from "@mobilipresenter/scene-core";
import {
  migrateLegacyUniformFrontQuery,
  parseViewerConfiguration,
  parseViewerInteraction
} from "../dist-ts/src/runtime/query.js";

const ALL_NEUTRAL = "01:neutral-greige,02:neutral-greige,03:neutral-greige,04:neutral-greige,05:neutral-greige,06:neutral-greige,07:neutral-greige";
const ALL_WARM = "01:warm-wood,02:warm-wood,03:warm-wood,04:warm-wood,05:warm-wood,06:warm-wood,07:warm-wood";

test("runtime query composes global finish, local front, hide, stone and light state", () => {
  const query = new URLSearchParams(
    "hide=02&finish=warm-wood&front=03:neutral-greige&stone=graphite-speckled&light=warm-worktop"
  );
  const state = parseViewerConfiguration(query);
  assert.equal(state.visibilityByModule[module02.id], "off");
  assert.equal(state.furnitureFinishPresetId, "warm-wood");
  assert.equal(state.frontPresetByModule[module03WithSink.id], "neutral-greige");
  assert.equal(state.stonePresetId, "graphite-speckled");
  assert.equal(state.lightingPresetId, "warm-worktop");
});

test("uniform all-module legacy front state migrates to canonical global finish", () => {
  for (const [legacy, expected] of [[ALL_NEUTRAL, "neutral-greige"], [ALL_WARM, "warm-wood"]]) {
    const migrated = migrateLegacyUniformFrontQuery(new URLSearchParams(`controls=1&front=${legacy}`));
    assert.equal(migrated.migratedLegacyUniformFront, true);
    assert.equal(migrated.migratedFurnitureFinishPresetId, expected);
    assert.equal(migrated.query.has("front"), false);
    assert.equal(migrated.query.get("finish"), expected);
    const state = parseViewerConfiguration(migrated.query);
    assert.equal(state.furnitureFinishPresetId, expected);
    assert.deepEqual(state.frontPresetByModule, {});
  }
});

test("partial and mixed front assignments retain local override semantics", () => {
  const partial = migrateLegacyUniformFrontQuery(new URLSearchParams("front=03:neutral-greige"));
  assert.equal(partial.migratedLegacyUniformFront, false);
  assert.equal(partial.query.get("front"), "03:neutral-greige");
  assert.equal(parseViewerConfiguration(partial.query).frontPresetByModule[module03WithSink.id], "neutral-greige");

  const mixedRaw = "01:warm-wood,02:warm-wood,03:neutral-greige,04:warm-wood,05:warm-wood,06:warm-wood,07:warm-wood";
  const mixed = migrateLegacyUniformFrontQuery(new URLSearchParams(`finish=warm-wood&front=${mixedRaw}`));
  assert.equal(mixed.migratedLegacyUniformFront, false);
  const mixedState = parseViewerConfiguration(mixed.query);
  assert.equal(mixedState.furnitureFinishPresetId, "warm-wood");
  assert.equal(mixedState.frontPresetByModule[module03WithSink.id], "neutral-greige");
});

test("uniform legacy and canonical global finish conflict fails closed", () => {
  assert.throws(
    () => migrateLegacyUniformFrontQuery(new URLSearchParams(`finish=warm-wood&front=${ALL_NEUTRAL}`)),
    /VIEWER_FINISH_QUERY_CONFLICT:warm-wood:neutral-greige/
  );
});

test("duplicate aliases are not collapsed into a global migration", () => {
  const duplicated = "01:neutral-greige,01:neutral-greige,02:neutral-greige,03:neutral-greige,04:neutral-greige,05:neutral-greige,06:neutral-greige";
  const migrated = migrateLegacyUniformFrontQuery(new URLSearchParams(`front=${duplicated}`));
  assert.equal(migrated.migratedLegacyUniformFront, false);
  assert.equal(migrated.query.get("front"), duplicated);
});

test("runtime query selection and hover map stable module aliases independently", () => {
  const interaction = parseViewerInteraction(new URLSearchParams("select=06&hover=03"));
  assert.equal(interaction.selectedModuleId, module06.id);
  assert.equal(interaction.hoveredModuleId, module03WithSink.id);
});

test("runtime query rejects unknown aliases and presets", () => {
  assert.throws(() => parseViewerConfiguration(new URLSearchParams("hide=99")), /VIEWER_MODULE_ALIAS_UNKNOWN/);
  assert.throws(() => parseViewerConfiguration(new URLSearchParams("front=02:magenta")), /VIEWER_FRONT_PRESET_NOT_FOUND/);
  assert.throws(() => parseViewerConfiguration(new URLSearchParams("finish=magenta")), /VIEWER_FRONT_PRESET_NOT_FOUND/);
  assert.throws(() => parseViewerConfiguration(new URLSearchParams("stone=unknown")), /VIEWER_STONE_PRESET_NOT_FOUND/);
  assert.throws(() => parseViewerConfiguration(new URLSearchParams("light=unknown")), /VIEWER_LIGHTING_PRESET_NOT_FOUND/);
  assert.throws(() => parseViewerInteraction(new URLSearchParams("hover=99")), /VIEWER_MODULE_ALIAS_UNKNOWN/);
});
