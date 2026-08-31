import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const composition = readFileSync(new URL("../src/ui/desktop-composition.ts", import.meta.url), "utf8");
const bootstrap = readFileSync(new URL("../src/bootstrap.ts", import.meta.url), "utf8");

function containsAll(source, values) {
  for (const value of values) assert.ok(source.includes(value), `missing source contract: ${value}`);
}

test("wide desktop keeps module detail distributed between right rail and lower factual strip", () => {
  containsAll(composition, [
    "@media (min-width: 1180px)",
    '--ui-detail-width: clamp(350px, 30vw, 470px)',
    '.viewer-product-detail__cards',
    'position: fixed !important',
    'left: var(--ui-stage-width) !important',
    'right: var(--ui-detail-width) !important',
    'bottom: var(--ui-actions-height) !important',
    'display: flex !important',
    'overflow-x: auto !important',
    'overflow-y: hidden !important',
  ]);
  assert.equal(composition.includes("@media (min-width: 1024px) {"), false);
});

test("desktop footer is compact contextual navigation rather than a large isolated CTA strip", () => {
  containsAll(composition, [
    '.viewer-configurator__actions::before',
    'Etapa 1 de 4 · Módulos',
    'Etapa 2 de 4 · Acabamentos',
    'Etapa 3 de 4 · Acessórios',
    'Etapa 4 de 4 · Resumo',
    '--ui-actions-height: 58px',
    'min-width: 0 !important',
    'width: auto !important',
  ]);
});

test("module card body is a keyboard-accessible primary entry to contextual detail", () => {
  containsAll(composition, [
    '.viewer-stage--modules .viewer-module-card',
    'card.tabIndex = 0',
    'card.setAttribute("role", "button")',
    'isInteractiveTarget(event.target)',
    'openCardDetail(card)',
    'inspect?.click()',
    'event.key !== "Enter" && event.key !== " "',
  ]);
});

test("bootstrap installs and disposes the composition enhancement with product mode", () => {
  containsAll(bootstrap, [
    'installDesktopCompositionEnhancement',
    'desktopComposition = installDesktopCompositionEnhancement()',
    'desktopComposition?.dispose()',
  ]);
});
