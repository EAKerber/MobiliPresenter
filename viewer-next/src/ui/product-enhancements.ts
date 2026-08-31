import type { FrontPresetId, ViewerUiApi } from "../api/ui-contract.js";
import type { RuntimeControlsUi } from "./runtime-controls.js";

export interface ProductUiEnhancements {
  dispose(): void;
}

const FRONT_SWATCH_COLOR: Readonly<Record<FrontPresetId, string>> = {
  "warm-wood": "#A8744D",
  "neutral-greige": "#B2ADA5"
};
const SVG_NS = "http://www.w3.org/2000/svg";

function reportProductUiError(error: unknown): void {
  const status = document.querySelector<HTMLElement>(".viewer-configurator__status");
  if (!status) return;
  status.dataset.error = "true";
  const message = status.querySelector<HTMLElement>("span");
  if (message) message.textContent = error instanceof Error ? error.message : String(error);
}

function globalFrontPreset(api: ViewerUiApi): FrontPresetId | null {
  const snapshot = api.getSnapshot();
  const ids = api.getCatalog().modules.map(alias => snapshot.frontPresetByModule[alias] ?? null);
  const first = ids[0] ?? null;
  return ids.every(id => id === first) ? first : null;
}

function fmt(value: number): string {
  return Number.isInteger(value) ? String(value) : String(Number(value.toFixed(1)));
}

function svgLine(group: SVGGElement, x1: number, y1: number, x2: number, y2: number): void {
  const line = document.createElementNS(SVG_NS, "line");
  line.setAttribute("x1", x1.toFixed(2));
  line.setAttribute("y1", y1.toFixed(2));
  line.setAttribute("x2", x2.toFixed(2));
  line.setAttribute("y2", y2.toFixed(2));
  group.append(line);
}

function svgText(group: SVGGElement, x: number, y: number, value: string): void {
  const label = document.createElementNS(SVG_NS, "text");
  label.setAttribute("x", x.toFixed(2));
  label.setAttribute("y", y.toFixed(2));
  label.setAttribute("text-anchor", "middle");
  label.textContent = value;
  group.append(label);
}

function addDimension(
  group: SVGGElement,
  a: readonly [number, number],
  b: readonly [number, number],
  label: string,
  offset: readonly [number, number]
): void {
  const ax = a[0] + offset[0];
  const ay = a[1] + offset[1];
  const bx = b[0] + offset[0];
  const by = b[1] + offset[1];
  svgLine(group, a[0], a[1], ax, ay);
  svgLine(group, b[0], b[1], bx, by);
  svgLine(group, ax, ay, bx, by);

  const dx = bx - ax;
  const dy = by - ay;
  const length = Math.max(1, Math.hypot(dx, dy));
  const nx = (-dy / length) * 4;
  const ny = (dx / length) * 4;
  svgLine(group, ax - nx, ay - ny, ax + nx, ay + ny);
  svgLine(group, bx - nx, by - ny, bx + nx, by + ny);
  svgText(group, (ax + bx) / 2, (ay + by) / 2 - 7, label);
}

function decorateIsometricDimensions(api: ViewerUiApi): void {
  const pkg = api.getSnapshot().selectedTechnicalPresentation;
  if (!pkg?.dimensions) return;
  const { width, height, depth } = pkg.dimensions.primaryMm;

  for (const figure of document.querySelectorAll<HTMLElement>(".viewer-product-detail__figure[data-technical-view]")) {
    const viewId = figure.dataset.technicalView;
    const request = pkg.technicalViews.find(candidate => candidate.id === viewId);
    if (request?.kind !== "isometric") continue;
    const svg = figure.querySelector<SVGSVGElement>("svg");
    if (!svg || svg.dataset.productDimensions === "true") continue;
    svg.dataset.productDimensions = "true";

    const points3d: readonly [number, number, number][] = [
      [0, 0, 0], [width, 0, 0], [width, depth, 0], [0, depth, 0],
      [0, 0, height], [width, 0, height], [width, depth, height], [0, depth, height]
    ];
    const raw = points3d.map(([px, py, pz]) => [px - py * 0.62, -pz + (px + py) * 0.28] as const);
    const xs = raw.map(point => point[0]);
    const ys = raw.map(point => point[1]);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    const scale = Math.min(324 / Math.max(1, maxX - minX), 204 / Math.max(1, maxY - minY));
    const project = (index: number): readonly [number, number] => {
      const point = raw[index]!;
      return [48 + (point[0] - minX) * scale, 48 + (point[1] - minY) * scale];
    };

    const group = document.createElementNS(SVG_NS, "g");
    group.classList.add("viewer-product-detail__isometric-dimensions");
    group.setAttribute("fill", "none");
    group.setAttribute("stroke", "currentColor");
    group.setAttribute("stroke-width", "1.2");
    group.setAttribute("vector-effect", "non-scaling-stroke");
    addDimension(group, project(0), project(1), `${fmt(width)} mm`, [0, 27]);
    addDimension(group, project(1), project(2), `${fmt(depth)} mm`, [22, 17]);
    addDimension(group, project(0), project(4), `${fmt(height)} mm`, [-25, 0]);
    svg.append(group);
  }
}

export function installProductUiEnhancements(
  api: ViewerUiApi,
  controls: RuntimeControlsUi
): ProductUiEnhancements {
  let disposed = false;
  let scheduled = false;

  const decorateModuleThumbnails = (): void => {
    for (const card of document.querySelectorAll<HTMLElement>(".viewer-module-card[data-module-alias]")) {
      const alias = card.dataset.moduleAlias;
      if (!alias) continue;
      const thumbnail = card.querySelector<HTMLElement>(".viewer-module-card__thumbnail");
      if (!thumbnail || thumbnail.dataset.productThumbnail === "true") continue;
      thumbnail.dataset.productThumbnail = "true";
      const image = document.createElement("img");
      image.className = "viewer-module-card__thumbnail-image";
      image.src = `/module-thumbnails/module-${alias}.png`;
      image.alt = "";
      image.decoding = "async";
      image.loading = "eager";
      image.addEventListener("error", () => {
        thumbnail.dataset.thumbnailUnavailable = "true";
        image.remove();
      }, { once: true });
      thumbnail.replaceChildren(image);
    }
  };

  const decorateGlobalFinishes = (): void => {
    const stage = document.querySelector<HTMLElement>('[data-stage-panel="finishes"]');
    if (!stage) return;

    const frontGroup = stage.querySelector<HTMLElement>(".viewer-option-group");
    if (!frontGroup) return;
    const heading = frontGroup.querySelector<HTMLElement>("h3");
    if (heading) heading.textContent = "Cor dos móveis";

    const context = stage.querySelector<HTMLElement>(".viewer-stage-context");
    if (context) context.textContent = "Acabamento global · a escolha é aplicada a todos os módulos do ambiente.";

    const activePreset = globalFrontPreset(api);
    for (const option of frontGroup.querySelectorAll<HTMLButtonElement>("[data-front-preset]")) {
      const presetId = option.dataset.frontPreset;
      if (!presetId) continue;
      if (presetId === "original") {
        option.hidden = true;
        continue;
      }
      option.disabled = false;
      option.setAttribute("aria-pressed", activePreset === presetId ? "true" : "false");
      if (option.dataset.productFinishEnhanced === "true") continue;
      option.dataset.productFinishEnhanced = "true";
      const label = option.textContent ?? presetId;
      option.replaceChildren();
      const swatch = document.createElement("span");
      swatch.className = "viewer-choice-card__swatch";
      swatch.setAttribute("aria-hidden", "true");
      swatch.style.backgroundColor = FRONT_SWATCH_COLOR[presetId as FrontPresetId] ?? "#d8d0c7";
      const copy = document.createElement("span");
      copy.className = "viewer-choice-card__label";
      copy.textContent = label;
      option.append(swatch, copy);
    }
  };

  const decorate = (): void => {
    scheduled = false;
    if (disposed) return;
    decorateModuleThumbnails();
    decorateGlobalFinishes();
    decorateIsometricDimensions(api);
  };

  const scheduleDecorate = (): void => {
    if (scheduled || disposed) return;
    scheduled = true;
    queueMicrotask(decorate);
  };

  const handleGlobalFinishClick = (event: Event): void => {
    const target = event.target instanceof Element
      ? event.target.closest<HTMLButtonElement>('[data-stage-panel="finishes"] [data-front-preset]')
      : null;
    if (!target || target.hidden) return;
    const presetId = target.dataset.frontPreset;
    if (!presetId || presetId === "original") return;

    event.preventDefault();
    event.stopPropagation();
    if (event instanceof MouseEvent) event.stopImmediatePropagation();

    try {
      for (const alias of api.getCatalog().modules) {
        api.setFrontPreset(alias, presetId as FrontPresetId);
      }
      controls.refresh();
      scheduleDecorate();
    } catch (error) {
      reportProductUiError(error);
    }
  };

  document.addEventListener("click", handleGlobalFinishClick, true);
  const observer = new MutationObserver(scheduleDecorate);
  observer.observe(document.body, { childList: true, subtree: true });
  decorate();

  return {
    dispose(): void {
      disposed = true;
      observer.disconnect();
      document.removeEventListener("click", handleGlobalFinishClick, true);
    }
  };
}
