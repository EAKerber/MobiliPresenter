import type { FrontPresetId, ViewerUiApi } from "../api/ui-contract.js";
import type { RuntimeControlsUi } from "./runtime-controls.js";

const FINISH_STAGE_SELECTOR = '[data-stage-panel="finishes"]';
const FINISH_OPTION_SELECTOR = '[data-front-preset]';
const GLOBAL_CONTEXT_COPY = "Acabamento global · a escolha é aplicada a todos os módulos do ambiente.";

function normalizeFinishStage(stage: Element, activePresetId: FrontPresetId): void {
  const heading = stage.querySelector<HTMLElement>(".viewer-option-group h3");
  if (heading) heading.textContent = "Cor dos móveis";

  const context = stage.querySelector<HTMLElement>(".viewer-stage-context");
  if (context) context.textContent = GLOBAL_CONTEXT_COPY;

  for (const option of stage.querySelectorAll<HTMLButtonElement>(FINISH_OPTION_SELECTOR)) {
    const presetId = option.dataset.frontPreset;
    if (!presetId) continue;
    if (presetId === "original") {
      option.hidden = true;
      continue;
    }

    option.disabled = false;
    option.setAttribute("aria-pressed", activePresetId === presetId ? "true" : "false");
  }
}

function normalizeGlobalFinishControls(api: ViewerUiApi, root: ParentNode = document): void {
  const activePresetId = api.getSnapshot().furnitureFinishPresetId;
  if (root instanceof Element && root.matches(FINISH_STAGE_SELECTOR)) {
    normalizeFinishStage(root, activePresetId);
  }
  for (const stage of root.querySelectorAll<Element>(FINISH_STAGE_SELECTOR)) {
    normalizeFinishStage(stage, activePresetId);
  }
}

export function installGlobalFinishControl(
  api: ViewerUiApi,
  controls: RuntimeControlsUi
): () => void {
  let disposed = false;

  const handleClick = (event: Event): void => {
    const target = event.target instanceof Element
      ? event.target.closest<HTMLButtonElement>(`${FINISH_STAGE_SELECTOR} ${FINISH_OPTION_SELECTOR}`)
      : null;
    if (!target || target.hidden) return;

    const presetId = target.dataset.frontPreset;
    if (!presetId || presetId === "original") return;

    event.preventDefault();
    event.stopPropagation();
    if (event instanceof MouseEvent) event.stopImmediatePropagation();

    api.setFurnitureFinishPreset(presetId as FrontPresetId);
    controls.refresh();
    normalizeGlobalFinishControls(api);
  };

  const observer = new MutationObserver(records => {
    if (disposed) return;
    for (const record of records) {
      for (const node of record.addedNodes) {
        if (!(node instanceof Element)) continue;
        normalizeGlobalFinishControls(api, node);
      }
    }
  });

  document.addEventListener("click", handleClick, true);
  observer.observe(document.documentElement, { childList: true, subtree: true });
  normalizeGlobalFinishControls(api);

  return () => {
    disposed = true;
    observer.disconnect();
    document.removeEventListener("click", handleClick, true);
  };
}
