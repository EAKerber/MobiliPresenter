import {
  ArrowRight,
  Box,
  ChevronLeft,
  ChevronRight,
  CircleDot,
  Cog,
  createIcons,
  Info,
  Layers,
  Link2,
  Paintbrush,
  Plug,
  Ruler,
  SlidersHorizontal,
  TriangleAlert,
  Wrench
} from "lucide";
import type { FrontPresetId, ViewerUiApi } from "../api/ui-contract.js";

export interface ProductPolishV2 {
  dispose(): void;
}

const STYLE_ID = "viewer-product-polish-v2";
const WIDE_DESKTOP_QUERY = "(min-width: 1180px)";

// Temporary UI bridge until the public catalog exposes visual swatch metadata (#215).
const FRONT_SWATCH_COLOR: Readonly<Record<string, string>> = {
  "warm-wood": "#A8744D",
  "neutral-greige": "#B2ADA5"
};

// Values mirror the current authoritative stone presets but remain a removable
// presentation bridge; the public UI contract should eventually publish them.
const STONE_SWATCH_COLOR: Readonly<Record<string, string>> = {
  "light-speckled": "#C9C1B2",
  "warm-beige-speckled": "#B9A58E",
  "graphite-speckled": "#555453"
};

const ICON_NAME_BY_KIND: Readonly<Record<string, string>> = {
  function: "circle-dot",
  construction: "layers",
  installation: "wrench",
  finish: "paintbrush",
  hardware: "cog",
  electrical: "plug",
  interface: "sliders-horizontal",
  component: "box",
  dependency: "link-2",
  notice: "triangle-alert",
  info: "info"
};

const PRODUCT_POLISH_CSS = `
.viewer-finish-dot {
  width: 12px;
  height: 12px;
  flex: 0 0 12px;
  display: inline-block;
  border: 1px solid color-mix(in srgb, var(--ui-border-strong) 72%, transparent);
  border-radius: 50%;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, .28);
}

.viewer-product-detail__meta .viewer-current-finish-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.viewer-product-card__stack .viewer-finish-value {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
  min-width: 0;
}

.viewer-semantic-icon--library {
  stroke-width: 1.7;
}

@media (min-width: 1180px) {
  html:root {
    --ui-actions-height: 0px;
    --ui-detail-bottom-height: clamp(196px, 24vh, 226px);
  }

  body.viewer-product-ui #app {
    bottom: 0 !important;
  }

  body.viewer-product-ui[data-viewer-detail-open="true"] #app {
    bottom: var(--ui-detail-bottom-height) !important;
  }

  body.viewer-product-ui .viewer-configurator__stage {
    bottom: 0 !important;
  }

  body.viewer-product-ui .viewer-stage--modules {
    padding: 14px 14px 68px;
  }

  body.viewer-product-ui .viewer-stage--modules .viewer-stage-heading {
    gap: 3px;
    margin-bottom: 10px;
  }

  body.viewer-product-ui .viewer-stage--modules .viewer-stage-heading__eyebrow,
  body.viewer-product-ui .viewer-stage--modules .viewer-stage-heading__description {
    display: none;
  }

  body.viewer-product-ui .viewer-stage--modules .viewer-stage-heading h2 {
    margin: 0;
    color: var(--ui-text-secondary);
    font-size: 12px;
    font-weight: 800;
    letter-spacing: .08em;
    text-transform: uppercase;
  }

  body.viewer-product-ui .viewer-stage--modules .viewer-module-list {
    gap: 6px;
  }

  body.viewer-product-ui .viewer-stage--modules .viewer-module-card {
    min-height: 72px;
    grid-template-columns: 28px 56px minmax(0, 1fr) 28px;
    grid-template-areas: "visibility thumbnail copy inspect";
    gap: 6px 8px;
    padding: 7px 8px;
    border-radius: 10px;
  }

  body.viewer-product-ui .viewer-stage--modules .viewer-module-card__visibility {
    width: 28px;
    height: 38px;
  }

  body.viewer-product-ui .viewer-stage--modules .viewer-module-card__thumbnail {
    width: 56px;
    height: 58px;
  }

  body.viewer-product-ui .viewer-stage--modules .viewer-module-card__copy {
    align-self: center;
    gap: 2px;
  }

  body.viewer-product-ui .viewer-stage--modules .viewer-module-card__copy strong {
    font-size: 12px;
    line-height: 1.2;
  }

  body.viewer-product-ui .viewer-stage--modules .viewer-module-card__copy span {
    font-size: 9.5px;
    line-height: 1.25;
  }

  body.viewer-product-ui .viewer-stage--modules .viewer-module-card__inspect {
    width: 28px;
    height: 32px;
    display: grid;
    place-items: center;
    justify-self: end;
    align-self: center;
    padding: 0;
    font-size: 0;
    text-decoration: none;
  }

  body.viewer-product-ui .viewer-stage--modules .viewer-module-card__inspect .viewer-semantic-icon--library {
    width: 18px;
    height: 18px;
  }

  body.viewer-product-ui .viewer-configurator__stage-content {
    scrollbar-gutter: auto;
  }

  body.viewer-product-ui .viewer-configurator__actions {
    left: 14px !important;
    right: auto !important;
    bottom: 10px !important;
    width: calc(var(--ui-stage-width) - 28px) !important;
    height: auto !important;
    min-height: 0 !important;
    padding: 0 !important;
    border: 0 !important;
    background: transparent !important;
    box-shadow: none !important;
    backdrop-filter: none !important;
  }

  body.viewer-product-ui .viewer-configurator__actions::before,
  body.viewer-product-ui .viewer-configurator__actions .viewer-button--secondary {
    display: none !important;
  }

  body.viewer-product-ui .viewer-configurator__actions .viewer-button--primary {
    width: 100% !important;
    min-width: 0 !important;
    min-height: 42px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    border-radius: 8px;
    padding: 9px 14px;
  }

  body.viewer-product-ui[data-viewer-current-step="summary"] .viewer-configurator__actions {
    display: none !important;
  }

  body.viewer-product-ui .viewer-product-detail {
    bottom: 0 !important;
  }

  body.viewer-product-ui .viewer-product-detail__view-selector {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0;
    overflow: hidden;
    padding-bottom: 0;
  }

  body.viewer-product-ui .viewer-product-detail__view-button {
    min-width: 0;
    width: 100%;
    padding-inline: 4px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  body.viewer-product-ui .viewer-product-detail__cards {
    left: var(--ui-stage-width) !important;
    right: var(--ui-detail-width) !important;
    bottom: 0 !important;
    height: var(--ui-detail-bottom-height) !important;
    display: flex !important;
    align-items: stretch !important;
    gap: 12px !important;
    padding: 12px 48px 34px !important;
    overflow-x: auto !important;
    overflow-y: hidden !important;
    scroll-snap-type: x mandatory;
    scroll-padding-inline: 48px;
    scroll-behavior: smooth;
    overscroll-behavior-x: contain;
    touch-action: pan-x pan-y;
    scrollbar-width: none !important;
  }

  body.viewer-product-ui .viewer-product-detail__cards::-webkit-scrollbar {
    display: none !important;
  }

  body.viewer-product-ui .viewer-product-detail__cards .viewer-product-card,
  body.viewer-product-ui .viewer-product-detail__cards .viewer-product-card--wide {
    flex: 0 0 clamp(270px, 32vw, 410px) !important;
    width: auto !important;
    min-width: 0 !important;
    max-width: min(410px, calc(100vw - var(--ui-stage-width) - var(--ui-detail-width) - 96px));
    height: auto !important;
    min-height: 0 !important;
    align-self: stretch;
    scroll-snap-align: start;
    scroll-snap-stop: always;
    overflow-x: hidden !important;
    overflow-y: auto !important;
    scrollbar-width: none !important;
    padding: 12px 14px !important;
    border-radius: 11px;
    overflow-wrap: anywhere;
  }

  body.viewer-product-ui .viewer-product-detail__cards .viewer-product-card::-webkit-scrollbar {
    display: none !important;
  }

  body.viewer-product-ui .viewer-product-detail__cards [data-product-card="specifications"] {
    flex-basis: clamp(330px, 39vw, 470px) !important;
  }

  body.viewer-product-ui .viewer-product-detail__cards [data-product-card="dimensions"] {
    flex-basis: 250px !important;
  }

  body.viewer-product-ui .viewer-product-detail__cards [data-product-card="components"] {
    flex-basis: clamp(290px, 34vw, 390px) !important;
  }

  body.viewer-product-ui .viewer-product-detail__cards [data-product-card="finishes"] {
    flex-basis: 290px !important;
  }

  body.viewer-product-ui .viewer-product-detail__cards [data-product-card="dependencies"],
  body.viewer-product-ui .viewer-product-detail__cards [data-product-card="notices"] {
    flex-basis: clamp(290px, 34vw, 390px) !important;
  }

  body.viewer-product-ui .viewer-product-detail__cards .viewer-product-card > h3 {
    margin-bottom: 9px;
  }

  body.viewer-product-ui .viewer-product-detail__cards .viewer-product-card__list,
  body.viewer-product-ui .viewer-product-detail__cards .viewer-product-card__stack {
    gap: 6px;
    margin-top: 8px;
  }

  body.viewer-product-ui .viewer-product-detail__cards .viewer-product-card__list li,
  body.viewer-product-ui .viewer-product-detail__cards .viewer-product-card__stack li,
  body.viewer-product-ui .viewer-product-detail__cards .viewer-product-notice__text {
    font-size: 10.5px;
    line-height: 1.36;
  }

  body.viewer-product-ui .viewer-product-detail__cards .viewer-product-card__stack li {
    align-items: flex-start;
  }

  body.viewer-product-ui .viewer-product-detail__cards .viewer-product-card__stack strong,
  body.viewer-product-ui .viewer-product-detail__cards .viewer-product-card__stack span {
    min-width: 0;
    white-space: normal;
  }

  .viewer-product-carousel__chrome {
    position: fixed;
    z-index: 30019;
    left: var(--ui-stage-width);
    right: var(--ui-detail-width);
    bottom: 0;
    height: var(--ui-detail-bottom-height);
    pointer-events: none;
  }

  .viewer-product-carousel__arrow {
    position: absolute;
    top: 50%;
    width: 34px;
    height: 34px;
    display: grid;
    place-items: center;
    border: 1px solid var(--ui-border);
    border-radius: 50%;
    background: color-mix(in srgb, var(--ui-surface-strong) 94%, transparent);
    color: var(--ui-text-secondary);
    box-shadow: 0 5px 18px rgba(35, 31, 28, .08);
    transform: translateY(-58%);
    cursor: pointer;
    pointer-events: auto;
    transition: opacity var(--ui-motion), transform var(--ui-motion), background var(--ui-motion);
  }

  .viewer-product-carousel__arrow:hover:not(:disabled) {
    background: var(--ui-surface-strong);
    color: var(--ui-text);
    transform: translateY(-58%) scale(1.04);
  }

  .viewer-product-carousel__arrow:disabled {
    opacity: .28;
    cursor: default;
  }

  .viewer-product-carousel__arrow--previous {
    left: 8px;
  }

  .viewer-product-carousel__arrow--next {
    right: 8px;
  }

  .viewer-product-carousel__arrow .viewer-semantic-icon--library {
    width: 17px;
    height: 17px;
  }

  .viewer-product-carousel__dots {
    position: absolute;
    left: 50%;
    bottom: 8px;
    display: flex;
    align-items: center;
    gap: 7px;
    transform: translateX(-50%);
    pointer-events: auto;
  }

  .viewer-product-carousel__dot {
    width: 7px;
    height: 7px;
    border: 0;
    border-radius: 50%;
    padding: 0;
    background: var(--ui-border-strong);
    opacity: .6;
    cursor: pointer;
    transition: width var(--ui-motion), opacity var(--ui-motion), background var(--ui-motion);
  }

  .viewer-product-carousel__dot[aria-current="true"] {
    width: 18px;
    border-radius: 999px;
    background: var(--ui-accent-strong);
    opacity: 1;
  }
}

@media (prefers-reduced-motion: reduce) {
  body.viewer-product-ui .viewer-product-detail__cards {
    scroll-behavior: auto !important;
  }

  .viewer-product-carousel__arrow,
  .viewer-product-carousel__dot {
    transition: none !important;
  }
}
`;

function iconPlaceholder(name: string): HTMLElement {
  const icon = document.createElement("i");
  icon.dataset.lucide = name;
  icon.setAttribute("aria-hidden", "true");
  return icon;
}

function globalFrontPreset(api: ViewerUiApi): FrontPresetId | null {
  const snapshot = api.getSnapshot();
  const ids = api.getCatalog().modules.map(alias => snapshot.frontPresetByModule[alias] ?? null);
  const first = ids[0] ?? null;
  return ids.every(id => id === first) ? first : null;
}

function swatchCandidates(api: ViewerUiApi): readonly { readonly label: string; readonly color: string }[] {
  const snapshot = api.getSnapshot();
  const catalog = api.getCatalog();
  const candidates: { label: string; color: string }[] = [];

  const frontPreset = globalFrontPreset(api);
  if (frontPreset) {
    const option = catalog.frontPresets.find(candidate => candidate.id === frontPreset);
    const color = FRONT_SWATCH_COLOR[frontPreset];
    if (option && color) candidates.push({ label: option.label, color });
  }

  const stoneOption = catalog.stonePresets.find(candidate => candidate.id === snapshot.stonePresetId);
  const stoneColor = STONE_SWATCH_COLOR[snapshot.stonePresetId];
  if (stoneOption && stoneColor) candidates.push({ label: stoneOption.label, color: stoneColor });

  return candidates;
}

function createFinishDot(color: string): HTMLElement {
  const dot = document.createElement("span");
  dot.className = "viewer-finish-dot";
  dot.style.backgroundColor = color;
  dot.setAttribute("aria-hidden", "true");
  return dot;
}

function decorateFinishDots(api: ViewerUiApi): void {
  const candidates = swatchCandidates(api);
  if (candidates.length === 0) return;

  for (const meta of document.querySelectorAll<HTMLElement>(".viewer-product-detail__meta > span")) {
    const text = meta.textContent?.trim() ?? "";
    const candidate = candidates.find(item => item.label === text);
    if (!candidate || meta.dataset.productFinishDot === candidate.color) continue;
    meta.dataset.productFinishDot = candidate.color;
    meta.classList.add("viewer-current-finish-pill");
    meta.prepend(createFinishDot(candidate.color));
  }

  const pkg = api.getSnapshot().selectedTechnicalPresentation;
  const finishesCard = document.querySelector<HTMLElement>('[data-product-card="finishes"]');
  if (!pkg || !finishesCard) return;
  const items = Array.from(finishesCard.querySelectorAll<HTMLLIElement>(".viewer-product-card__stack > li"));
  items.forEach((item, index) => {
    const finish = pkg.finishes[index];
    if (!finish?.currentOptionId) return;
    const current = finish.options.find(option => option.id === finish.currentOptionId);
    if (!current) return;
    const candidate = candidates.find(item => item.label === current.label);
    if (!candidate) return;
    const value = item.querySelector<HTMLElement>(":scope > span:last-child");
    if (!value || value.dataset.productFinishDot === candidate.color) return;
    value.dataset.productFinishDot = candidate.color;
    value.classList.add("viewer-finish-value");
    value.prepend(createFinishDot(candidate.color));
  });
}

function formatDimension(value: number): string {
  return Number.isInteger(value) ? `${value} mm` : `${Number(value.toFixed(1))} mm`;
}

function decorateDimensionsCard(api: ViewerUiApi): void {
  const pkg = api.getSnapshot().selectedTechnicalPresentation;
  const cards = document.querySelector<HTMLElement>(".viewer-product-detail__cards");
  if (!pkg?.dimensions || !cards || cards.querySelector('[data-product-card="dimensions"]')) return;

  const section = document.createElement("section");
  section.className = "viewer-product-card viewer-product-card--dimensions";
  section.dataset.productCard = "dimensions";

  const heading = document.createElement("h3");
  heading.dataset.productIcon = "true";
  const headingLabel = document.createElement("span");
  headingLabel.textContent = "Dimensões";
  heading.append(iconPlaceholder("ruler"), headingLabel);

  const list = document.createElement("ul");
  list.className = "viewer-product-card__stack viewer-product-card__dimensions";
  const labels: Readonly<Record<string, string>> = {
    width: "Largura",
    height: "Altura",
    depth: "Profundidade"
  };
  for (const axis of pkg.dimensions.order) {
    const item = document.createElement("li");
    const label = document.createElement("strong");
    label.textContent = labels[axis] ?? axis;
    const value = document.createElement("span");
    value.textContent = formatDimension(pkg.dimensions.primaryMm[axis]);
    item.append(label, value);
    list.append(item);
  }
  section.append(heading, list);

  const specifications = cards.querySelector<HTMLElement>('[data-product-card="specifications"]');
  if (specifications) specifications.after(section);
  else cards.prepend(section);
}

function replaceCustomSemanticIcons(): void {
  for (const custom of document.querySelectorAll<SVGSVGElement>("svg.viewer-semantic-icon[data-icon-kind]")) {
    const kind = custom.dataset.iconKind ?? "info";
    const name = ICON_NAME_BY_KIND[kind] ?? "info";
    custom.replaceWith(iconPlaceholder(name));
  }
}

function decorateModuleInspectButtons(wideDesktop: boolean): void {
  for (const button of document.querySelectorAll<HTMLButtonElement>(".viewer-module-card__inspect")) {
    if (!wideDesktop) continue;
    if (button.dataset.productChevron === "true" && button.querySelector("svg.lucide")) continue;
    button.dataset.productChevron = "true";
    button.replaceChildren(iconPlaceholder("chevron-right"));
  }
}

function decorateStageCta(wideDesktop: boolean): void {
  if (!wideDesktop) return;
  const step = document.body.dataset.viewerCurrentStep;
  const labels: Readonly<Record<string, string>> = {
    modules: "Acabamentos",
    finishes: "Acessórios",
    accessories: "Resumo"
  };
  const label = step ? labels[step] : undefined;
  const next = document.querySelector<HTMLButtonElement>(".viewer-configurator__actions .viewer-button--primary");
  if (!next || next.hidden || !label) return;
  if (next.dataset.productCtaStep === step && next.querySelector("svg.lucide")) return;
  next.dataset.productCtaStep = step ?? "";
  const copy = document.createElement("span");
  copy.textContent = label;
  next.replaceChildren(copy, iconPlaceholder("arrow-right"));
}

function cardsFor(root: HTMLElement): HTMLElement[] {
  return Array.from(root.querySelectorAll<HTMLElement>(":scope > .viewer-product-card"));
}

function activeCardIndex(root: HTMLElement): number {
  const cards = cardsFor(root);
  if (cards.length === 0) return 0;
  const center = root.scrollLeft + root.clientWidth / 2;
  let bestIndex = 0;
  let bestDistance = Number.POSITIVE_INFINITY;
  cards.forEach((card, index) => {
    const cardCenter = card.offsetLeft + card.offsetWidth / 2;
    const distance = Math.abs(cardCenter - center);
    if (distance < bestDistance) {
      bestDistance = distance;
      bestIndex = index;
    }
  });
  return bestIndex;
}

function scrollToCard(root: HTMLElement, index: number): void {
  const cards = cardsFor(root);
  const target = cards[Math.max(0, Math.min(index, cards.length - 1))];
  if (!target) return;
  const left = Math.max(0, target.offsetLeft - Math.max(0, (root.clientWidth - target.offsetWidth) / 2));
  root.scrollTo({
    left,
    behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth"
  });
}

function ensureCarouselChrome(root: HTMLElement, wideDesktop: boolean): HTMLElement | null {
  let chrome = document.querySelector<HTMLElement>(".viewer-product-carousel__chrome");
  if (!wideDesktop || cardsFor(root).length < 2) {
    chrome?.remove();
    return null;
  }

  if (!chrome) {
    chrome = document.createElement("div");
    chrome.className = "viewer-product-carousel__chrome";

    const previous = document.createElement("button");
    previous.type = "button";
    previous.className = "viewer-product-carousel__arrow viewer-product-carousel__arrow--previous";
    previous.dataset.productCarouselDirection = "previous";
    previous.setAttribute("aria-label", "Card anterior");
    previous.append(iconPlaceholder("chevron-left"));

    const next = document.createElement("button");
    next.type = "button";
    next.className = "viewer-product-carousel__arrow viewer-product-carousel__arrow--next";
    next.dataset.productCarouselDirection = "next";
    next.setAttribute("aria-label", "Próximo card");
    next.append(iconPlaceholder("chevron-right"));

    const dots = document.createElement("div");
    dots.className = "viewer-product-carousel__dots";
    dots.setAttribute("aria-label", "Paginação das informações do módulo");

    chrome.append(previous, dots, next);
    document.body.append(chrome);
  }

  const cards = cardsFor(root);
  const dots = chrome.querySelector<HTMLElement>(".viewer-product-carousel__dots")!;
  if (dots.children.length !== cards.length) {
    dots.replaceChildren();
    cards.forEach((_, index) => {
      const dot = document.createElement("button");
      dot.type = "button";
      dot.className = "viewer-product-carousel__dot";
      dot.dataset.productCarouselIndex = String(index);
      dot.setAttribute("aria-label", `Ir para card ${index + 1} de ${cards.length}`);
      dots.append(dot);
    });
  }
  return chrome;
}

function updateCarouselState(root: HTMLElement): void {
  const chrome = document.querySelector<HTMLElement>(".viewer-product-carousel__chrome");
  if (!chrome) return;
  const cards = cardsFor(root);
  const active = activeCardIndex(root);
  const previous = chrome.querySelector<HTMLButtonElement>('[data-product-carousel-direction="previous"]');
  const next = chrome.querySelector<HTMLButtonElement>('[data-product-carousel-direction="next"]');
  if (previous) previous.disabled = active <= 0;
  if (next) next.disabled = active >= cards.length - 1;
  for (const [index, dot] of Array.from(chrome.querySelectorAll<HTMLButtonElement>(".viewer-product-carousel__dot")).entries()) {
    dot.setAttribute("aria-current", index === active ? "true" : "false");
  }
}

function applyLucideIcons(): void {
  createIcons({
    icons: {
      ArrowRight,
      Box,
      ChevronLeft,
      ChevronRight,
      CircleDot,
      Cog,
      Info,
      Layers,
      Link2,
      Paintbrush,
      Plug,
      Ruler,
      SlidersHorizontal,
      TriangleAlert,
      Wrench
    },
    attrs: {
      class: ["viewer-semantic-icon", "viewer-semantic-icon--library"],
      "stroke-width": 1.7,
      "aria-hidden": "true"
    },
    root: document.body
  });
}

export function installProductPolishV2(api: ViewerUiApi): ProductPolishV2 {
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = PRODUCT_POLISH_CSS;
  document.head.append(style);

  const wideDesktop = matchMedia(WIDE_DESKTOP_QUERY);
  let disposed = false;
  let scheduledFrame: number | null = null;
  let carouselRoot: HTMLElement | null = null;

  const decorate = (): void => {
    scheduledFrame = null;
    if (disposed) return;

    const wide = wideDesktop.matches;
    decorateDimensionsCard(api);
    replaceCustomSemanticIcons();
    decorateModuleInspectButtons(wide);
    decorateStageCta(wide);
    decorateFinishDots(api);

    const nextCarouselRoot = document.querySelector<HTMLElement>(".viewer-product-detail__cards");
    if (!wide || !nextCarouselRoot) {
      document.querySelector(".viewer-product-carousel__chrome")?.remove();
      carouselRoot = null;
    } else {
      carouselRoot = nextCarouselRoot;
      carouselRoot.dataset.productCarousel = "true";
      ensureCarouselChrome(carouselRoot, wide);
      updateCarouselState(carouselRoot);
    }

    applyLucideIcons();
  };

  const scheduleDecorate = (): void => {
    if (disposed || scheduledFrame !== null) return;
    scheduledFrame = requestAnimationFrame(decorate);
  };

  const observer = new MutationObserver(scheduleDecorate);
  observer.observe(document.body, { childList: true, subtree: true });

  const onClick = (event: MouseEvent): void => {
    const target = event.target instanceof Element ? event.target : null;
    if (!target || !carouselRoot) return;
    const arrow = target.closest<HTMLButtonElement>("[data-product-carousel-direction]");
    if (arrow) {
      const current = activeCardIndex(carouselRoot);
      scrollToCard(carouselRoot, current + (arrow.dataset.productCarouselDirection === "next" ? 1 : -1));
      return;
    }
    const dot = target.closest<HTMLButtonElement>("[data-product-carousel-index]");
    if (dot) {
      const index = Number.parseInt(dot.dataset.productCarouselIndex ?? "0", 10);
      if (Number.isInteger(index)) scrollToCard(carouselRoot, index);
    }
  };

  const onScroll = (event: Event): void => {
    if (event.target !== carouselRoot) return;
    scheduleDecorate();
  };

  const onViewportChange = (): void => scheduleDecorate();
  document.addEventListener("click", onClick);
  document.addEventListener("scroll", onScroll, true);
  window.addEventListener("resize", onViewportChange);
  wideDesktop.addEventListener("change", onViewportChange);
  decorate();

  return {
    dispose(): void {
      disposed = true;
      observer.disconnect();
      if (scheduledFrame !== null) cancelAnimationFrame(scheduledFrame);
      document.removeEventListener("click", onClick);
      document.removeEventListener("scroll", onScroll, true);
      window.removeEventListener("resize", onViewportChange);
      wideDesktop.removeEventListener("change", onViewportChange);
      document.querySelector(".viewer-product-carousel__chrome")?.remove();
      style.remove();
    }
  };
}
