import type {
  ViewerUiApi,
  ViewerUiModuleDescriptor,
  ViewerUiOption
} from "../api/ui-contract.js";

export interface ProductContractEnhancements {
  dispose(): void;
}

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

    const checkbox = card.querySelector<HTMLInputElement>("[data-module-visibility]");
    if (checkbox) {
      const verb = card.dataset.visible === "false" ? "Mostrar" : "Ocultar";
      checkbox.setAttribute("aria-label", `${verb} ${descriptor.title}`);
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
    const dot = meta.querySelector<HTMLElement>(".viewer-finish-dot");
    if (visual && dot) {
      dot.style.backgroundColor = visual.previewColorSrgb;
      dot.dataset.materialId = visual.materialId;
    }
  }

  const allFinishOptions: ViewerUiOption[] = [
    ...catalog.furnitureFinishPresets,
    ...catalog.stonePresets
  ];
  for (const value of document.querySelectorAll<HTMLElement>(".viewer-product-card .viewer-finish-value")) {
    const visual = optionVisualByLabel(allFinishOptions, value.textContent?.trim() ?? "");
    const dot = value.querySelector<HTMLElement>(".viewer-finish-dot");
    if (visual && dot) {
      dot.style.backgroundColor = visual.previewColorSrgb;
      dot.dataset.materialId = visual.materialId;
    }
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
