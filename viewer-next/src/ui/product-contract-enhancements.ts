import type {
  ViewerUiApi,
  ViewerUiModuleDescriptor,
  ViewerUiOption
} from "../api/ui-contract.js";

export interface ProductContractEnhancements {
  dispose(): void;
}

const SVG_NS = "http://www.w3.org/2000/svg";

const SEMANTIC_ICON_PATHS: Readonly<Record<string, readonly string[]>> = {
  "electrical.outlet": [
    "M7 4h10a3 3 0 0 1 3 3v10a3 3 0 0 1-3 3H7a3 3 0 0 1-3-3V7a3 3 0 0 1 3-3z",
    "M9 9v3",
    "M15 9v3",
    "M12 15v.01"
  ],
  "electrical.cable": [
    "M7 4v5a5 5 0 0 0 5 5h1a4 4 0 0 1 4 4v2",
    "M5 4h4",
    "M15 20h4"
  ],
  "electrical.switch": [
    "M5 12h5",
    "M14 8l5 4-5 4",
    "M10 12h9"
  ],
  "hardware.hinge": [
    "M5 5h5v14H5z",
    "M14 5h5v14h-5z",
    "M10 9h4",
    "M10 15h4",
    "M12 12v.01"
  ],
  "hardware.drawer-runner": [
    "M4 8h16",
    "M4 16h16",
    "M7 11h10v2H7z"
  ]
};

function formatMm(value: number): string {
  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 }).format(value);
}

function descriptorDimensions(descriptor: ViewerUiModuleDescriptor): string {
  const { dimensions } = descriptor;
  const values = dimensions.display.prefer === "nominal" && dimensions.nominalMm
    ? dimensions.nominalMm
    : dimensions.geometryMm;
  return `${dimensions.display.order.map(axis => {
    const label = dimensions.display.labels[axis] ?? axis;
    return `${label} ${formatMm(values[axis])}`;
  }).join(" × ")} mm`;
}

function optionVisualByLabel(
  options: readonly ViewerUiOption[],
  label: string
): ViewerUiOption["visual"] | undefined {
  return options.find(option => option.label === label)?.visual;
}

function createPublishedFinishDot(visual: NonNullable<ViewerUiOption["visual"]>): HTMLElement {
  const dot = document.createElement("span");
  dot.className = "viewer-finish-dot";
  dot.style.backgroundColor = visual.previewColorSrgb;
  dot.dataset.materialId = visual.materialId;
  dot.setAttribute("aria-hidden", "true");
  return dot;
}

function createPublishedSemanticIcon(semanticKey: string): SVGSVGElement | null {
  const paths = SEMANTIC_ICON_PATHS[semanticKey];
  if (!paths) return null;

  const svg = document.createElementNS(SVG_NS, "svg");
  svg.classList.add("viewer-semantic-icon", "viewer-semantic-icon--published");
  svg.dataset.semanticIconKey = semanticKey;
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "1.7");
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("stroke-linejoin", "round");

  for (const d of paths) {
    const path = document.createElementNS(SVG_NS, "path");
    path.setAttribute("d", d);
    svg.append(path);
  }
  return svg;
}

function decorateModuleCards(api: ViewerUiApi): void {
  const catalog = api.getCatalog();
  const descriptors = new Map(catalog.moduleDescriptors.map(descriptor => [descriptor.alias, descriptor]));

  for (const card of document.querySelectorAll<HTMLElement>(".viewer-module-card[data-module-alias]")) {
    const alias = card.dataset.moduleAlias;
    if (!alias) continue;
    const descriptor = descriptors.get(alias as ViewerUiModuleDescriptor["alias"]);
    if (!descriptor) continue;

    const title = card.querySelector<HTMLElement>(".viewer-module-card__copy > strong");
    const meta = card.querySelector<HTMLElement>(".viewer-module-card__copy > span");
    if (title && title.textContent !== descriptor.title) title.textContent = descriptor.title;
    if (meta) {
      const dimensions = descriptorDimensions(descriptor);
      if (meta.textContent !== dimensions) meta.textContent = dimensions;
    }

    const inspect = card.querySelector<HTMLButtonElement>(".viewer-module-card__inspect");
    inspect?.setAttribute("aria-label", `Abrir detalhes de ${descriptor.title}`);
    card.dataset.productDescriptor = "true";
  }
}

function decorateStoneChoices(api: ViewerUiApi): void {
  const catalog = api.getCatalog();
  const stage = document.querySelector<HTMLElement>('[data-stage-panel="finishes"]');
  if (!stage) return;

  for (const choice of stage.querySelectorAll<HTMLButtonElement>("[data-stone-preset]")) {
    const presetId = choice.dataset.stonePreset;
    if (!presetId) continue;
    const option = catalog.stonePresets.find(candidate => candidate.id === presetId);
    if (!option?.visual) continue;

    let swatch = choice.querySelector<HTMLElement>(".viewer-choice-card__swatch");
    let label = choice.querySelector<HTMLElement>(".viewer-choice-card__label");
    if (!swatch || !label) {
      const copy = choice.textContent?.trim() || option.label;
      choice.replaceChildren();
      swatch = document.createElement("span");
      swatch.className = "viewer-choice-card__swatch";
      swatch.setAttribute("aria-hidden", "true");
      label = document.createElement("span");
      label.className = "viewer-choice-card__label";
      label.textContent = copy;
      choice.append(swatch, label);
    }
    swatch.style.backgroundColor = option.visual.previewColorSrgb;
    swatch.dataset.materialId = option.visual.materialId;
    choice.dataset.productStoneEnhanced = "true";
  }
}

function decoratePublishedFinishDots(api: ViewerUiApi): void {
  const catalog = api.getCatalog();
  const snapshot = api.getSnapshot();
  const selectedFurniture = catalog.furnitureFinishPresets.find(option => option.id === snapshot.furnitureFinishPresetId);
  const selectedStone = catalog.stonePresets.find(option => option.id === snapshot.stonePresetId);
  const selected: ViewerUiOption[] = [];
  if (selectedFurniture) selected.push(selectedFurniture);
  if (selectedStone) selected.push(selectedStone);

  for (const meta of document.querySelectorAll<HTMLElement>(".viewer-product-detail__meta > span")) {
    const visual = optionVisualByLabel(selected, meta.textContent?.trim() ?? "");
    if (!visual) continue;

    meta.classList.add("viewer-current-finish-pill");
    let dot = meta.querySelector<HTMLElement>(".viewer-finish-dot");
    if (!dot) {
      dot = createPublishedFinishDot(visual);
      meta.prepend(dot);
    } else {
      dot.style.backgroundColor = visual.previewColorSrgb;
      dot.dataset.materialId = visual.materialId;
    }
    meta.dataset.productFinishSource = "published-visual";
  }

  const allFinishOptions: ViewerUiOption[] = [
    ...catalog.furnitureFinishPresets,
    ...catalog.stonePresets
  ];
  for (const value of document.querySelectorAll<HTMLElement>(".viewer-product-card .viewer-finish-value")) {
    const visual = optionVisualByLabel(allFinishOptions, value.textContent?.trim() ?? "");
    if (!visual) continue;

    let dot = value.querySelector<HTMLElement>(".viewer-finish-dot");
    if (!dot) {
      dot = createPublishedFinishDot(visual);
      value.prepend(dot);
    } else {
      dot.style.backgroundColor = visual.previewColorSrgb;
      dot.dataset.materialId = visual.materialId;
    }
    value.dataset.productFinishSource = "published-visual";
  }
}

function decoratePublishedSemanticIcons(): void {
  for (const item of document.querySelectorAll<HTMLElement>("[data-semantic-kind]")) {
    const semanticKey = item.dataset.semanticKind;
    if (!semanticKey || !SEMANTIC_ICON_PATHS[semanticKey]) continue;

    const current = item.querySelector<HTMLElement>(":scope > .viewer-semantic-icon, :scope > i[data-lucide]");
    if (current?.dataset.semanticIconKey === semanticKey) continue;

    const icon = createPublishedSemanticIcon(semanticKey);
    if (!icon) continue;
    if (current) current.replaceWith(icon);
    else item.prepend(icon);
    item.dataset.productSemanticIconSource = "published-key";
  }
}

export function installProductContractEnhancements(api: ViewerUiApi): ProductContractEnhancements {
  let disposed = false;
  let scheduledFrame: number | null = null;

  const decorate = (): void => {
    scheduledFrame = null;
    if (disposed) return;
    decorateModuleCards(api);
    decorateStoneChoices(api);
    decoratePublishedFinishDots(api);
    decoratePublishedSemanticIcons();
  };

  const scheduleDecorate = (): void => {
    if (disposed || scheduledFrame !== null) return;
    scheduledFrame = requestAnimationFrame(decorate);
  };

  const observer = new MutationObserver(scheduleDecorate);
  observer.observe(document.body, { childList: true, subtree: true });
  decorate();

  return {
    dispose(): void {
      disposed = true;
      observer.disconnect();
      if (scheduledFrame !== null) cancelAnimationFrame(scheduledFrame);
    }
  };
}
