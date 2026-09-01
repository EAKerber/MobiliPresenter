import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const readiness = readFileSync(new URL("../src/ui/global-finish-readiness.ts", import.meta.url), "utf8");
const productEnhancements = readFileSync(new URL("../src/ui/product-enhancements.ts", import.meta.url), "utf8");
const html = readFileSync(new URL("../index.html", import.meta.url), "utf8");

function containsAll(source, values) {
  for (const value of values) assert.ok(source.includes(value), `missing source contract: ${value}`);
}

test("global MDF finish options are interactive before any reset or module selection", () => {
  containsAll(readiness, [
    'const FINISH_STAGE_SELECTOR = \'[data-stage-panel="finishes"]\';',
    'const FINISH_OPTION_SELECTOR = \'[data-front-preset]\';',
    'presetId === "original"',
    "option.hidden = true",
    "if (option.disabled) option.disabled = false",
    "new MutationObserver",
    "observer.observe(document.documentElement, { childList: true, subtree: true })",
    "installGlobalFinishReadiness();",
  ]);

  assert.equal(readiness.includes("resetConfiguration"), false);
  assert.equal(readiness.includes("setFurnitureFinishPreset"), false);
});

test("finish readiness loads before viewer bootstrap while product mode retains finish authority", () => {
  const readinessIndex = html.indexOf('/src/ui/global-finish-readiness.ts');
  const bootstrapIndex = html.indexOf('/src/bootstrap.ts');
  assert.ok(readinessIndex >= 0, "global finish readiness module missing from index");
  assert.ok(bootstrapIndex > readinessIndex, "global finish readiness must load before bootstrap");

  containsAll(productEnhancements, [
    "api.setFurnitureFinishPreset",
    "snapshot.furnitureFinishPresetId",
    "catalog.furnitureFinishPresets",
  ]);
});
