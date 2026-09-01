const FINISH_STAGE_SELECTOR = '[data-stage-panel="finishes"]';
const FINISH_OPTION_SELECTOR = '[data-front-preset]';

function normalizeFinishStage(stage: Element): void {
  for (const option of stage.querySelectorAll<HTMLButtonElement>(FINISH_OPTION_SELECTOR)) {
    const presetId = option.dataset.frontPreset;
    if (!presetId) continue;

    if (presetId === "original") {
      option.hidden = true;
      continue;
    }

    // Runtime controls still originate these buttons from the legacy
    // per-module front model. Product mode owns them as global furniture
    // finishes, so they must be interactive from the first rendered frame.
    if (option.disabled) option.disabled = false;
  }
}

function normalizeGlobalFinishControls(root: ParentNode = document): void {
  if (root instanceof Element && root.matches(FINISH_STAGE_SELECTOR)) {
    normalizeFinishStage(root);
  }
  for (const stage of root.querySelectorAll<Element>(FINISH_STAGE_SELECTOR)) {
    normalizeFinishStage(stage);
  }
}

export function installGlobalFinishReadiness(): () => void {
  normalizeGlobalFinishControls();

  const observer = new MutationObserver(records => {
    for (const record of records) {
      for (const node of record.addedNodes) {
        if (!(node instanceof Element)) continue;
        normalizeGlobalFinishControls(node);
      }
    }
  });

  observer.observe(document.documentElement, { childList: true, subtree: true });
  return () => observer.disconnect();
}

installGlobalFinishReadiness();
