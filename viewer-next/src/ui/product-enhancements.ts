import type { FrontPresetId, ViewerUiApi } from "../api/ui-contract.js";
import type { RuntimeControlsUi } from "./runtime-controls.js";

export interface ProductUiEnhancements {
  dispose(): void;
}

const FRONT_SWATCH_COLOR: Readonly<Record<FrontPresetId, string>> = {
  "warm-wood": "#A8744D",
  "neutral-greige": "#B2ADA5"
};
const PRODUCT_DEFAULT_FRONT_PRESET: FrontPresetId = "neutral-greige";
const SVG_NS = "http://www.w3.org/2000/svg";

type ProductIconKind =
  | "function"
  | "construction"
  | "installation"
  | "finish"
  | "hardware"
  | "electrical"
  | "interface"
  | "component"
  | "dependency"
  | "notice"
  | "info";

const PRODUCT_ICON_PATHS: Readonly<Record<ProductIconKind, readonly string[]>> = {
  function: ["M12 3v3", "M12 18v3", "M3 12h3", "M18 12h3", "M8 8h8v8H8z"],
  construction: ["M4 7l8-4 8 4-8 4-8-4z", "M4 12l8 4 8-4", "M4 17l8 4 8-4"],
  installation: ["M14.5 5.5a4 4 0 0 0-5 5L4 16l4 4 5.5-5.5a4 4 0 0 0 5-5l-3 3-3-3 3-3z"],
  finish: ["M12 3c3 4 6 7.2 6 11a6 6 0 0 1-12 0c0-3.8 3-7 6-11z", "M9 16c.8 1 1.8 1.5 3 1.5"],
  hardware: ["M8 4h8l4 8-4 8H8l-4-8 4-8z", "M9 12h6"],
  electrical: ["M8 4v6", "M16 4v6", "M7 10h10v3a5 5 0 0 1-10 0v-3z", "M12 18v3"],
  interface: ["M5 7h14", "M5 17h14", "M9 4v6", "M15 14v6", "M9 7a2 2 0 1 1 0 .01", "M15 17a2 2 0 1 1 0 .01"],
  component: ["M5 5h14v14H5z", "M5 10h14", "M10 5v14"],
  dependency: ["M9.5 14.5l5-5", "M7 16.5l-1 1a3 3 0 0 1-4-4l4-4a3 3 0 0 1 4 0", "M17 7.5l1-1a3 3 0 0 1 4 4l-4 4a3 3 0 0 1-4 0"],
  notice: ["M12 3l9 17H3L12 3z", "M12 9v5", "M12 17.5v.01"],
  info: ["M12 4a8 8 0 1 0 0 16 8 8 0 0 0 0-16z", "M12 10v6", "M12 7.5v.01"]
};

function reportProductUiError(error: unknown): void {
  const status = document.querySelector<HTMLElement>(".viewer-configurator__status");
  if (!status) return;
  status.dataset.error = "true";
  const message = status.querySelector<HTMLElement>("span");
  if (message) message.textContent = error instanceof Error ? error.message : String(error);
}

function createProductIcon(kind: ProductIconKind): SVGSVGElement {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.classList.add("viewer-semantic-icon");
  svg.dataset.iconKind = kind;
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "1.6");
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("stroke-linejoin", "round");
  for (const d of PRODUCT_ICON_PATHS[kind]) {
    const path = document.createElementNS(SVG_NS, "path");
    path.setAttribute("d", d);
    svg.append(path);
  }
  return svg;
}

function globalFrontPreset(api: ViewerUiApi): FrontPresetId | null {
  const snapshot = api.getSnapshot();
  const ids = api.getCatalog().modules.map(alias => snapshot.frontPresetByModule[alias] ?? null);
  const first = ids[0] ?? null;
  return ids.every(id => id === first) ? first : null;
}

function ensureProductDefaultFrontPreset(api: ViewerUiApi): void {
  const snapshot = api.getSnapshot();
  const aliases = api.getCatalog().modules;
  const hasExplicitFrontPreset = aliases.some(alias => snapshot.frontPresetByModule[alias] !== undefined);
  if (hasExplicitFrontPreset) return;
  for (const alias of aliases) api.setFrontPreset(alias, PRODUCT_DEFAULT_FRONT_PRESET);
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

    const baseGroup = Array.from(svg.children).find(
      child => child instanceof SVGGElement && !child.classList.contains("viewer-product-detail__isometric-dimensions")
    );
    if (baseGroup instanceof SVGGElement) {
      for (const node of baseGroup.querySelectorAll("text")) {
        if (node.textContent?.includes("×") && node.textContent.includes("mm")) node.remove();
      }
    }

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

function factIconKind(category: string): ProductIconKind {
  switch (category) {
    case "function": return "function";
    case "construction": return "construction";
    case "installation": return "installation";
    case "finish": return "finish";
    case "hardware": return "hardware";
    case "electrical": return "electrical";
    default: return "info";
  }
}

function componentIconKind(kind: string): ProductIconKind {
  switch (kind) {
    case "hardware": return "hardware";
    case "electrical": return "electrical";
    case "panel": return "construction";
    case "interface": return "interface";
    default: return "component";
  }
}

function decorateHeading(card: HTMLElement, kind: ProductIconKind, cardKind: string): void {
  card.dataset.productCard = cardKind;
  const heading = card.querySelector<HTMLElement>(":scope > h3");
  if (!heading || heading.dataset.productIcon === "true") return;
  heading.dataset.productIcon = "true";
  const label = document.createElement("span");
  label.textContent = heading.textContent ?? "";
  heading.replaceChildren(createProductIcon(kind), label);
}

function decorateSemanticCards(api: ViewerUiApi): void {
  const pkg = api.getSnapshot().selectedTechnicalPresentation;
  const cardsRoot = document.querySelector<HTMLElement>(".viewer-product-detail__cards");
  if (!pkg || !cardsRoot) return;

  const cards = Array.from(cardsRoot.querySelectorAll<HTMLElement>(":scope > .viewer-product-card"));
  const findCard = (title: string): HTMLElement | undefined => cards.find(card => card.querySelector(":scope > h3")?.textContent === title);

  const specifications = findCard("Especificações");
  if (specifications) {
    decorateHeading(specifications, "info", "specifications");
    const items = Array.from(specifications.querySelectorAll<HTMLLIElement>(".viewer-product-card__list > li"));
    items.forEach((item, index) => {
      const fact = pkg.specifications[index];
      if (!fact || item.dataset.productSemanticDecorated === "true") return;
      item.dataset.productSemanticDecorated = "true";
      item.dataset.semanticKind = fact.category;
      const copy = document.createElement("span");
      copy.className = "viewer-product-card__semantic-copy";
      copy.textContent = item.textContent ?? "";
      item.replaceChildren(createProductIcon(factIconKind(fact.category)), copy);
    });
  }

  const components = findCard("Componentes");
  if (components) {
    decorateHeading(components, "component", "components");
    const items = Array.from(components.querySelectorAll<HTMLLIElement>(".viewer-product-card__stack > li"));
    items.forEach((item, index) => {
      const component = pkg.components[index];
      if (!component || item.dataset.productSemanticDecorated === "true") return;
      item.dataset.productSemanticDecorated = "true";
      item.dataset.semanticKind = component.kind;
      item.prepend(createProductIcon(componentIconKind(component.kind)));
    });
  }

  const finishes = findCard("Acabamento atual");
  if (finishes) {
    decorateHeading(finishes, "finish", "finishes");
    for (const item of finishes.querySelectorAll<HTMLLIElement>(".viewer-product-card__stack > li")) {
      if (item.dataset.productSemanticDecorated === "true") continue;
      item.dataset.productSemanticDecorated = "true";
      item.prepend(createProductIcon("finish"));
    }
  }

  const dependencies = findCard("Dependências");
  if (dependencies) {
    decorateHeading(dependencies, "dependency", "dependencies");
    for (const item of dependencies.querySelectorAll<HTMLLIElement>(".viewer-product-card__stack > li")) {
      if (item.dataset.productSemanticDecorated === "true") continue;
      item.dataset.productSemanticDecorated = "true";
      item.prepend(createProductIcon("dependency"));
    }
  }

  const notices = findCard("Avisos");
  if (notices) {
    decorateHeading(notices, "notice", "notices");
    const items = Array.from(notices.querySelectorAll<HTMLElement>(".viewer-product-notice"));
    items.forEach((item, index) => {
      if (item.dataset.productSemanticDecorated === "true") return;
      item.dataset.productSemanticDecorated = "true";
      item.prepend(createProductIcon(pkg.notices[index]?.severity === "info" ? "info" : "notice"));
    });
  }
}

function decorateTechnicalFigures(api: ViewerUiApi): void {
  const pkg = api.getSnapshot().selectedTechnicalPresentation;
  if (!pkg) return;
  for (const figure of document.querySelectorAll<HTMLElement>(".viewer-product-detail__figure[data-technical-view]")) {
    const request = pkg.technicalViews.find(candidate => candidate.id === figure.dataset.technicalView);
    if (!request) continue;
    figure.dataset.productDrawing = "true";
    figure.dataset.technicalKind = request.kind;
    if (request.plane) figure.dataset.technicalPlane = request.plane;
    const svg = figure.querySelector<SVGSVGElement>("svg");
    if (svg) svg.classList.add("viewer-technical-svg");
  }
}

function decorateUnavailableState(): void {
  const unavailable = document.querySelector<HTMLElement>(".viewer-product-detail__unavailable");
  if (!unavailable || unavailable.dataset.productSemanticDecorated === "true") return;
  unavailable.dataset.productSemanticDecorated = "true";
  const symbol = unavailable.querySelector<HTMLElement>(":scope > span[aria-hidden='true']");
  if (symbol) symbol.replaceWith(createProductIcon("info"));
}

export function installProductUiEnhancements(
  api: ViewerUiApi,
  controls: RuntimeControlsUi
): ProductUiEnhancements {
  let disposed = false;
  let scheduledFrame: number | null = null;

  try {
    ensureProductDefaultFrontPreset(api);
    controls.refresh();
  } catch (error) {
    reportProductUiError(error);
  }

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
    if (heading && heading.textContent !== "Cor dos móveis") heading.textContent = "Cor dos móveis";

    const context = stage.querySelector<HTMLElement>(".viewer-stage-context");
    const contextCopy = "Acabamento global · a escolha é aplicada a todos os módulos do ambiente.";
    if (context && context.textContent !== contextCopy) context.textContent = contextCopy;

    const activePreset = globalFrontPreset(api);
    for (const option of frontGroup.querySelectorAll<HTMLButtonElement>("[data-front-preset]")) {
      const presetId = option.dataset.frontPreset;
      if (!presetId) continue;
      if (presetId === "original") {
        if (!option.hidden) option.hidden = true;
        continue;
      }
      if (option.disabled) option.disabled = false;
      const pressed = activePreset === presetId ? "true" : "false";
      if (option.getAttribute("aria-pressed") !== pressed) option.setAttribute("aria-pressed", pressed);
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
    scheduledFrame = null;
    if (disposed) return;
    decorateModuleThumbnails();
    decorateGlobalFinishes();
    decorateTechnicalFigures(api);
    decorateIsometricDimensions(api);
    decorateSemanticCards(api);
    decorateUnavailableState();
  };

  const scheduleDecorate = (): void => {
    if (scheduledFrame !== null || disposed) return;
    scheduledFrame = requestAnimationFrame(decorate);
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
      if (scheduledFrame !== null) cancelAnimationFrame(scheduledFrame);
      document.removeEventListener("click", handleGlobalFinishClick, true);
    }
  };
}
