import type { FrontPresetId, ViewerUiApi } from "../api/ui-contract.js";
import type { RuntimeControlsUi } from "./runtime-controls.js";

export interface ProductUiEnhancements {
  dispose(): void;
}

const FRONT_SWATCH_COLOR: Readonly<Record<FrontPresetId, string>> = {
  "warm-wood": "#A8744D",
  "neutral-greige": "#B2ADA5"
};

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
