import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const ui = readFileSync(new URL("../src/ui/runtime-controls.ts", import.meta.url), "utf8");
const css = readFileSync(new URL("../src/ui/runtime-controls.css", import.meta.url), "utf8");
const html = readFileSync(new URL("../index.html", import.meta.url), "utf8");

test("guided configurator exposes the approved four-stage architecture", () => {
  for (const label of ["Módulos", "Acabamentos", "Acessórios", "Resumo"]) {
    assert.match(ui, new RegExp(`label: \\"${label}\\"`));
  }
  assert.match(ui, /data\.configuratorStep/);
  assert.match(ui, /aria-current/);
  assert.match(ui, /Continuar para/);
});

test("module visibility stays separate from contextual inspection", () => {
  assert.match(ui, /data\.moduleVisibility/);
  assert.match(ui, /Abrir detalhes do módulo/);
  assert.match(ui, /api\.setModuleVisibility/);
  assert.match(ui, /api\.selectModule/);
});

test("closing product detail preserves selected module", () => {
  const closeHandler = ui.match(/Fechar detalhes do módulo[\s\S]*?close\.addEventListener\("click", \(\) => \{([\s\S]*?)\n    \}\);/);
  assert.ok(closeHandler, "detail close handler must exist");
  assert.match(closeHandler[1], /detailExpanded = false/);
  assert.doesNotMatch(closeHandler[1], /selectModule\(null\)/);
});

test("UI consumes explicit presentation availability and fidelity", () => {
  assert.match(ui, /selectedTechnicalPresentationAvailability/);
  assert.match(ui, /technical-catalog-entry-missing|Detalhes técnicos ainda não publicados/);
  assert.match(ui, /asset\.fidelity === "geometry-derived"/);
  assert.match(ui, /asset\.coverage/);
  assert.match(ui, /asset\.omitted/);
});

test("accessories stage does not reclassify viewer lighting presets as commercial accessories", () => {
  assert.match(ui, /Opções configuráveis ainda não publicadas/);
  assert.doesNotMatch(ui, /catalog\.lightingPresets/);
  assert.doesNotMatch(ui, /setLightingPreset/);
});

test("desktop and mobile compositions preserve a persistent scene region", () => {
  assert.match(css, /body\.viewer-product-ui #app/);
  assert.match(css, /--ui-detail-width/);
  assert.match(css, /--ui-mobile-scene-height/);
  assert.match(css, /viewer-product-detail/);
  assert.match(css, /viewer-module-editor/);
});

test("user-visible shell does not use the internal project codename as product title", () => {
  assert.doesNotMatch(html, /MobiliPresenter/);
  assert.doesNotMatch(ui, /MobiliPresenter/);
  assert.match(html, /Apresentação de Ambiente/);
});
