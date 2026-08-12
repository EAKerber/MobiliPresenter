import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const ui = readFileSync(new URL("../src/ui/runtime-controls.ts", import.meta.url), "utf8");
const css = readFileSync(new URL("../src/ui/runtime-controls.css", import.meta.url), "utf8");
const html = readFileSync(new URL("../index.html", import.meta.url), "utf8");

function containsAll(source, values) {
  for (const value of values) assert.ok(source.includes(value), `missing source contract: ${value}`);
}

test("guided configurator keeps the approved four-stage model", () => {
  containsAll(ui, [
    'type ConfiguratorStep = "modules" | "finishes" | "accessories" | "summary";',
    'label: "Módulos"',
    'label: "Acabamentos"',
    'label: "Acessórios"',
    'label: "Resumo"',
    'item.setAttribute("aria-current", active ? "step" : "false")',
  ]);
});

test("module inclusion, inspection and contextual detail remain separate", () => {
  containsAll(ui, [
    "api.setModuleVisibility(alias",
    "api.selectModule(alias)",
    "detailExpanded = false",
    "selectedTechnicalPresentationAvailability",
  ]);
  assert.equal(ui.includes("api.selectModule(null)"), false);
});

test("accessories stage does not reinterpret presentation lighting as a product option", () => {
  containsAll(ui, ["Opções configuráveis ainda não publicadas"]);
  assert.equal(ui.includes("catalog.lightingPresets"), false);
  assert.equal(ui.includes("setLightingPreset"), false);
});

test("technical presentation uses explicit fidelity evidence", () => {
  containsAll(ui, [
    'asset.fidelity === "geometry-derived"',
    "asset.coverage",
    "asset.omitted",
    "Detalhes técnicos ainda não publicados",
  ]);
});

test("responsive shell reserves persistent scene space and avoids the internal codename", () => {
  containsAll(css, [
    "body.viewer-product-ui #app",
    "--ui-detail-width",
    "--ui-mobile-scene-height",
    ".viewer-product-detail",
    ".viewer-module-editor",
  ]);
  assert.equal(ui.includes("MobiliPresenter"), false);
  assert.equal(html.includes("MobiliPresenter"), false);
  assert.ok(html.includes("Apresentação de Ambiente — Vista Fixa"));
});
