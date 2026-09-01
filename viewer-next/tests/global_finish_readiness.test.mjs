import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const control = readFileSync(new URL("../src/ui/global-finish-readiness.ts", import.meta.url), "utf8");
const bootstrap = readFileSync(new URL("../src/bootstrap.ts", import.meta.url), "utf8");
const productEnhancements = readFileSync(new URL("../src/ui/product-enhancements.ts", import.meta.url), "utf8");
const html = readFileSync(new URL("../index.html", import.meta.url), "utf8");

function containsAll(source, values) {
  for (const value of values) assert.ok(source.includes(value), `missing source contract: ${value}`);
}

test("global MDF finish is a first-interaction control backed by the canonical API", () => {
  containsAll(control, [
    "installGlobalFinishControl",
    "api.getSnapshot().furnitureFinishPresetId",
    "api.setFurnitureFinishPreset",
    "controls.refresh()",
    'presetId === "original"',
    "option.hidden = true",
    "option.disabled = false",
    'document.addEventListener("click", handleClick, true)',
    "event.stopImmediatePropagation()",
  ]);
  assert.equal(control.includes("resetConfiguration"), false);
  assert.equal(control.includes("setFrontPreset"), false);
});

test("bootstrap installs global finish authority before product enhancement compatibility", () => {
  const controlIndex = bootstrap.indexOf("installGlobalFinishControl(uiApi, controls)");
  const enhancementIndex = bootstrap.indexOf("installProductUiEnhancements(uiApi, controls)");
  assert.ok(controlIndex >= 0, "global finish control missing from bootstrap");
  assert.ok(enhancementIndex > controlIndex, "global finish control must own the click before product enhancements");

  assert.equal(html.includes("/src/ui/global-finish-readiness.ts"), false);
  assert.ok(html.includes("/src/bootstrap.ts"), "bootstrap entrypoint missing");

  // Product enhancements may continue styling the same cards during the migration,
  // but the earlier capture handler stops its legacy writer from receiving the click.
  containsAll(productEnhancements, ["api.setFurnitureFinishPreset", "handleGlobalFinishClick"]);
});
