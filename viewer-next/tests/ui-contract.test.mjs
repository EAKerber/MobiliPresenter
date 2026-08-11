import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import test from "node:test";
import { module03WithSink } from "@mobilipresenter/scene-core";
import {
  CURRENT_VIEWER_UI_CATALOG,
  createViewerUiApi,
  createViewerUiSnapshot
} from "../dist-ts/src/api/ui-adapter.js";
import { VIEWER_UI_CONTRACT_VERSION } from "../dist-ts/src/api/ui-contract.js";
import {
  createDefaultViewerConfiguration,
  createDefaultViewerInteraction,
  reduceViewerInteraction
} from "../dist-ts/src/runtime/viewer-state.js";

test("UI adapter exposes one stable snapshot with technical presentation and derived SVG assets", () => {
  const configuration = createDefaultViewerConfiguration();
  const interaction = reduceViewerInteraction(createDefaultViewerInteraction(), {
    type: "select-module",
    moduleId: module03WithSink.id
  });
  const snapshot = createViewerUiSnapshot(configuration, interaction);

  assert.equal(snapshot.contractVersion, VIEWER_UI_CONTRACT_VERSION);
  assert.equal(snapshot.selectedModuleAlias, "03");
  assert.equal(snapshot.selectedTechnicalPresentation?.identity.alias, "03");
  assert.ok(snapshot.selectedTechnicalViewAssets.length > 0);
  assert.ok(snapshot.selectedTechnicalViewAssets.some(asset => asset.status === "ready" && asset.svg?.includes("<svg")));
  assert.equal(snapshot.visibilityByModule["03"], "inherit");
});

test("UI API delegates actions while keeping catalogs and engine state behind the adapter", () => {
  let selected = null;
  const configuration = createDefaultViewerConfiguration();
  const interaction = createDefaultViewerInteraction();
  const calls = [];
  const api = createViewerUiApi({
    getConfiguration: () => configuration,
    getInteraction: () => interaction,
    setModuleVisibility: (alias, value) => calls.push(["visibility", alias, value]),
    setFrontPreset: (alias, presetId) => calls.push(["front", alias, presetId]),
    clearFrontPreset: alias => calls.push(["front-clear", alias]),
    setStonePreset: presetId => calls.push(["stone", presetId]),
    setLightingPreset: presetId => calls.push(["lighting", presetId]),
    resetConfiguration: () => calls.push(["reset"]),
    selectModule: alias => { selected = alias; calls.push(["select", alias]); }
  });

  assert.equal(api.contractVersion, VIEWER_UI_CONTRACT_VERSION);
  assert.deepEqual(api.getCatalog(), CURRENT_VIEWER_UI_CATALOG);
  api.selectModule("04");
  api.setModuleVisibility("04", "off");
  api.setStonePreset("graphite-speckled");
  assert.equal(selected, "04");
  assert.deepEqual(calls, [
    ["select", "04"],
    ["visibility", "04", "off"],
    ["stone", "graphite-speckled"]
  ]);
});

test("UI implementation cannot import engine internals outside src/api", () => {
  const uiDir = new URL("../src/ui/", import.meta.url);
  const forbiddenImport = /from\s+["']\.\.\/(runtime|renderer|presentation|fixtures|main)(?:\/|["'])/;

  for (const name of readdirSync(uiDir).filter(name => name.endsWith(".ts"))) {
    const source = readFileSync(new URL(name, uiDir), "utf8");
    assert.equal(
      forbiddenImport.test(source),
      false,
      `${name} crosses UI-engine boundary; import through src/api instead`
    );
  }
});
