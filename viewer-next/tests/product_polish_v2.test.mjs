import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const polish = readFileSync(new URL("../src/ui/product-polish-v2.ts", import.meta.url), "utf8");
const contractEnhancements = readFileSync(new URL("../src/ui/product-contract-enhancements.ts", import.meta.url), "utf8");
const finalCss = readFileSync(new URL("../src/ui/product-polish-v2-final.css", import.meta.url), "utf8");
const bootstrap = readFileSync(new URL("../src/bootstrap.ts", import.meta.url), "utf8");
const packageJson = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8"));

function containsAll(source, values) {
  for (const value of values) assert.ok(source.includes(value), `missing source contract: ${value}`);
}

test("product polish uses Lucide instead of introducing another handcrafted semantic icon set", () => {
  assert.equal(packageJson.dependencies.lucide, "1.38.0");
  containsAll(polish, [
    'from "lucide"',
    "createIcons({",
    'electrical: "plug"',
    'hardware: "cog"',
    'construction: "layers"',
    'notice: "triangle-alert"',
    "replaceCustomSemanticIcons()"
  ]);
});

test("wide desktop detail facts are a smooth snap carousel with adjacent-card controls", () => {
  containsAll(polish, [
    'scroll-snap-type: x mandatory',
    'scroll-snap-stop: always',
    'scroll-behavior: smooth',
    'data-product-carousel-direction',
    'data-product-carousel-index',
    'scrollToCard(carouselRoot',
    'viewer-product-carousel__dots'
  ]);
});

test("carousel chevron artwork cannot steal the button hit target", () => {
  containsAll(finalCss, [
    '.viewer-product-carousel__arrow svg',
    '.viewer-product-carousel__arrow svg *',
    'pointer-events: none'
  ]);
});

test("wide desktop reuses the existing next-step action inside the module rail and frees the global footer strip", () => {
  containsAll(polish, [
    '--ui-actions-height: 0px',
    '.viewer-configurator__actions',
    'width: calc(var(--ui-stage-width) - 28px)',
    '.viewer-configurator__actions::before',
    '.viewer-button--secondary',
    'modules: "Acabamentos"',
    'finishes: "Acessórios"',
    'accessories: "Resumo"'
  ]);
});

test("published finish visuals override temporary UI color bridges", () => {
  containsAll(polish, [
    'className = "viewer-finish-dot"',
    'border-radius: 50%',
    'decorateFinishDots(api)'
  ]);
  containsAll(contractEnhancements, [
    'catalog.furnitureFinishPresets',
    'catalog.stonePresets',
    'previewColorSrgb',
    'dataset.materialId',
    'productStoneEnhanced'
  ]);
  assert.equal(/#[0-9A-Fa-f]{6}/.test(contractEnhancements), false);
  containsAll(finalCss, [
    '[data-product-card="finishes"]',
    '.viewer-finish-value',
    'width: 14px',
    'border-radius: 50%',
    '[data-product-stone-enhanced="true"]'
  ]);
});

test("module cards consume authoritative descriptors without requiring module selection", () => {
  containsAll(contractEnhancements, [
    'catalog.moduleDescriptors',
    'descriptor.title',
    'descriptorDimensions(descriptor)',
    'dimensions.display.prefer',
    'dimensions.display.order',
    'productDescriptor'
  ]);
});

test("finishes stage keeps the canonical mobile action reservation and compact stone row", () => {
  containsAll(finalCss, [
    '.viewer-stage--finishes',
    'padding-bottom: 22px !important',
    'grid-template-columns: repeat(3, minmax(0, 1fr))',
    'grid-template-rows: 28px minmax(0, auto)',
    'height: var(--ui-actions-height)',
    'min-height: var(--ui-actions-height)',
    'max-width: min(64vw, 250px)'
  ]);
  assert.equal(finalCss.includes('--ui-actions-height: 58px'), false);
});

test("detail polish reduces avoidable scroll and keeps variable-content cards contained", () => {
  containsAll(polish, [
    '.viewer-product-detail__view-selector',
    'overflow: hidden',
    'overflow-wrap: anywhere',
    'overflow-x: hidden !important',
    'overflow-y: auto !important',
    'scrollbar-width: none !important'
  ]);
});

test("product mode installs and disposes the polish lifecycle", () => {
  containsAll(bootstrap, [
    'installProductPolishV2',
    'productPolishV2 = installProductPolishV2(uiApi)',
    'productPolishV2?.dispose()',
    'installProductContractEnhancements',
    'productContractEnhancements = installProductContractEnhancements(uiApi)',
    'productContractEnhancements?.dispose()'
  ]);
});
