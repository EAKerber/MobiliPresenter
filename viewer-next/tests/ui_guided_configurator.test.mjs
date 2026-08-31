import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const ui = readFileSync(new URL("../src/ui/runtime-controls.ts", import.meta.url), "utf8");
const css = readFileSync(new URL("../src/ui/runtime-controls.css", import.meta.url), "utf8");
const productCss = readFileSync(new URL("../src/ui/product-presentation.css", import.meta.url), "utf8");
const productEnhancements = readFileSync(new URL("../src/ui/product-enhancements.ts", import.meta.url), "utf8");
const selection = readFileSync(new URL("../src/renderer/three/selection.ts", import.meta.url), "utf8");
const bootstrap = readFileSync(new URL("../src/bootstrap.ts", import.meta.url), "utf8");
const thumbnail = readFileSync(new URL("../src/thumbnail.ts", import.meta.url), "utf8");
const html = readFileSync(new URL("../index.html", import.meta.url), "utf8");
const netlify = readFileSync(new URL("../../netlify.toml", import.meta.url), "utf8");

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

test("product mode widens the desktop rail and distributes detail to right and bottom surfaces", () => {
  containsAll(productCss, [
    "--ui-stage-width: clamp(360px, 28vw, 420px)",
    "--ui-detail-bottom-height",
    'body.viewer-product-ui[data-viewer-detail-open="true"] #app',
    ".viewer-product-detail__cards",
    "bottom: var(--ui-actions-height)",
  ]);
});

test("product mode publishes global furniture finishes with authoritative visual swatches", () => {
  containsAll(productEnhancements, [
    '"warm-wood": "#A8744D"',
    '"neutral-greige": "#B2ADA5"',
    "Cor dos móveis",
    "Acabamento global",
    "for (const alias of api.getCatalog().modules)",
    "api.setFrontPreset(alias",
  ]);
  containsAll(productCss, [".viewer-choice-card__swatch", "border-radius: 10px"]);
});

test("module thumbnails are isolated renderer assets and selection contour is intentionally stronger", () => {
  containsAll(productEnhancements, ["/module-thumbnails/module-${alias}.png"]);
  containsAll(thumbnail, [
    "environment: []",
    "items: []",
    "modules: [moduleDefinition]",
    'const THUMBNAIL_WOOD = "#A8744D"',
    "new PerspectiveCamera",
    "assertRenderedPixels",
    "adapter.scene.background = null",
  ]);
  containsAll(selection, ["material.opacity = 0.62"]);
});

test("isometric product views receive explicit width height and depth dimension lines", () => {
  containsAll(productEnhancements, [
    'request?.kind !== "isometric"',
    "addDimension(group, project(0), project(1)",
    "addDimension(group, project(1), project(2)",
    "addDimension(group, project(0), project(4)",
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
  containsAll(productCss, [
    '.viewer-configurator__status[data-error="false"]',
    "--ui-mobile-scene-height: min(43vh, 360px)",
    ".viewer-product-detail",
  ]);
  assert.equal(ui.includes("MobiliPresenter"), false);
  assert.equal(productEnhancements.includes("MobiliPresenter"), false);
  assert.equal(html.includes("MobiliPresenter"), false);
  assert.ok(html.includes("Configure seu ambiente — Vista fixa"));
  assert.ok(html.includes("/src/ui/product-presentation.css"));
});

test("Netlify product builds open the current UI by default without weakening diagnostic overrides", () => {
  containsAll(netlify, ['VITE_DEFAULT_UI_MODE = "product"']);
  containsAll(bootstrap, [
    "VITE_DEFAULT_UI_MODE",
    '=== "product"',
    'query.get("fidelity") !== "1"',
    'controlsPreference === "1"',
    'controlsPreference !== "0" && defaultUiMode',
    'app.dataset.viewerUiMode = controlsEnabled ? "product" : "renderer-only"',
    "installProductUiEnhancements",
  ]);
});
