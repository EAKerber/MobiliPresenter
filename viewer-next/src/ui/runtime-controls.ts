import type {
  FrontPresetId,
  LightingPresetId,
  StonePresetId,
  ViewerUiApi
} from "../api/ui-contract.js";
import "./runtime-controls.css";

export interface RuntimeControlsUi {
  refresh(): void;
  dispose(): void;
}

function button(label: string, className = "viewer-controls__button"): HTMLButtonElement {
  const element = document.createElement("button");
  element.type = "button";
  element.className = className;
  element.textContent = label;
  return element;
}

function section(label: string): { root: HTMLElement; row: HTMLElement } {
  const root = document.createElement("section");
  root.className = "viewer-controls__section";
  const heading = document.createElement("span");
  heading.className = "viewer-controls__label";
  heading.textContent = label;
  const row = document.createElement("div");
  row.className = "viewer-controls__row";
  root.append(heading, row);
  return { root, row };
}

export function mountRuntimeControls(host: HTMLElement, api: ViewerUiApi): RuntimeControlsUi {
  const catalog = api.getCatalog();
  const launcher = button("Controles", "viewer-controls-launcher");
  launcher.setAttribute("aria-expanded", "true");

  const panel = document.createElement("aside");
  panel.className = "viewer-controls";
  panel.setAttribute("aria-label", "Controles técnicos do viewer");
  panel.dataset.viewerRuntimeUi = "mounted";

  const header = document.createElement("div");
  header.className = "viewer-controls__header";
  const titleWrap = document.createElement("div");
  const eyebrow = document.createElement("p");
  eyebrow.className = "viewer-controls__eyebrow";
  eyebrow.textContent = "VRC-02 · interface técnica";
  const title = document.createElement("h1");
  title.className = "viewer-controls__title";
  title.textContent = "MobiliPresenter";
  titleWrap.append(eyebrow, title);
  const close = button("×", "viewer-controls__close");
  close.setAttribute("aria-label", "Recolher controles");
  header.append(titleWrap, close);
  panel.append(header);

  const modules = section("Módulo");
  const moduleButtons = new Map<(typeof catalog.modules)[number], HTMLButtonElement>();
  for (const alias of catalog.modules) {
    const item = button(alias);
    item.dataset.moduleAlias = alias;
    item.addEventListener("click", () => runAction(() => api.selectModule(alias)));
    modules.row.append(item);
    moduleButtons.set(alias, item);
  }
  panel.append(modules.root);

  const selectedSection = document.createElement("section");
  selectedSection.className = "viewer-controls__section";
  const selectedInfo = document.createElement("div");
  selectedInfo.className = "viewer-controls__selected";
  const selectedName = document.createElement("strong");
  const selectedState = document.createElement("span");
  selectedInfo.append(selectedName, selectedState);
  const visibilityButton = button("Ocultar módulo", "viewer-controls__button viewer-controls__button--primary");
  const selectedHint = document.createElement("p");
  selectedHint.className = "viewer-controls__hint";
  selectedHint.textContent = "Clique na cena ou escolha um número acima. Módulos ocultos continuam selecionáveis pelos botões.";
  selectedSection.append(selectedInfo, visibilityButton, selectedHint);
  panel.append(selectedSection);

  const fronts = section("Frente do módulo selecionado");
  const originalFront = button("Original");
  fronts.row.append(originalFront);
  const frontButtons = new Map<FrontPresetId, HTMLButtonElement>();
  for (const preset of catalog.frontPresets) {
    const item = button(preset.label);
    item.dataset.frontPreset = preset.id;
    fronts.row.append(item);
    frontButtons.set(preset.id, item);
  }
  panel.append(fronts.root);

  const stones = section("Pedra");
  const stoneButtons = new Map<StonePresetId, HTMLButtonElement>();
  for (const preset of catalog.stonePresets) {
    const item = button(preset.label);
    item.dataset.stonePreset = preset.id;
    item.addEventListener("click", () => runAction(() => api.setStonePreset(preset.id)));
    stones.row.append(item);
    stoneButtons.set(preset.id, item);
  }
  panel.append(stones.root);

  const lights = section("Iluminação");
  const lightButtons = new Map<LightingPresetId, HTMLButtonElement>();
  for (const preset of catalog.lightingPresets) {
    const item = button(preset.label);
    item.dataset.lightingPreset = preset.id;
    item.addEventListener("click", () => runAction(() => api.setLightingPreset(preset.id)));
    lights.row.append(item);
    lightButtons.set(preset.id, item);
  }
  panel.append(lights.root);

  const resetSection = document.createElement("section");
  resetSection.className = "viewer-controls__section";
  const reset = button("Restaurar configuração", "viewer-controls__button viewer-controls__button--primary viewer-controls__button--danger");
  reset.addEventListener("click", () => runAction(() => api.resetConfiguration()));
  resetSection.append(reset);
  panel.append(resetSection);

  const status = document.createElement("p");
  status.className = "viewer-controls__status";
  status.dataset.error = "false";
  status.textContent = "Estado sincronizado com o renderer.";
  panel.append(status);

  let open = true;

  function setOpen(value: boolean): void {
    open = value;
    panel.hidden = !open;
    launcher.setAttribute("aria-expanded", open ? "true" : "false");
    launcher.textContent = open ? "Controles ativos" : "Controles";
  }

  function report(error: unknown): void {
    status.dataset.error = "true";
    status.textContent = error instanceof Error ? error.message : String(error);
  }

  function runAction(action: () => void): void {
    try {
      action();
      status.dataset.error = "false";
      status.textContent = "Estado sincronizado com o renderer.";
      refresh();
    } catch (error) {
      report(error);
    }
  }

  launcher.addEventListener("click", () => setOpen(!open));
  close.addEventListener("click", () => setOpen(false));

  visibilityButton.addEventListener("click", () => {
    const snapshot = api.getSnapshot();
    const alias = snapshot.selectedModuleAlias;
    if (!alias) return;
    const visible = snapshot.visibilityByModule[alias] !== "off";
    runAction(() => api.setModuleVisibility(alias, visible ? "off" : "inherit"));
  });

  originalFront.addEventListener("click", () => {
    const alias = api.getSnapshot().selectedModuleAlias;
    if (!alias) return;
    runAction(() => api.clearFrontPreset(alias));
  });

  for (const [presetId, item] of frontButtons) {
    item.addEventListener("click", () => {
      const alias = api.getSnapshot().selectedModuleAlias;
      if (!alias) return;
      runAction(() => api.setFrontPreset(alias, presetId));
    });
  }

  function refresh(): void {
    const snapshot = api.getSnapshot();
    const selectedAlias = snapshot.selectedModuleAlias;

    for (const [alias, item] of moduleButtons) {
      const selected = alias === selectedAlias;
      const visible = snapshot.visibilityByModule[alias] !== "off";
      item.setAttribute("aria-pressed", selected ? "true" : "false");
      item.title = visible ? `Módulo ${alias} visível` : `Módulo ${alias} oculto`;
    }

    if (!selectedAlias) {
      selectedName.textContent = "Nenhum módulo";
      selectedState.textContent = "selecione na cena";
      visibilityButton.disabled = true;
      originalFront.disabled = true;
      for (const item of frontButtons.values()) item.disabled = true;
    } else {
      const visible = snapshot.visibilityByModule[selectedAlias] !== "off";
      selectedName.textContent = `Módulo ${selectedAlias}`;
      selectedState.textContent = visible ? "visível" : "oculto";
      visibilityButton.disabled = false;
      visibilityButton.textContent = visible ? "Ocultar módulo" : "Mostrar módulo";
      originalFront.disabled = false;
      for (const item of frontButtons.values()) item.disabled = false;

      const activeFront = snapshot.frontPresetByModule[selectedAlias] ?? null;
      originalFront.setAttribute("aria-pressed", activeFront === null ? "true" : "false");
      for (const [presetId, item] of frontButtons) {
        item.setAttribute("aria-pressed", activeFront === presetId ? "true" : "false");
      }
    }

    for (const [presetId, item] of stoneButtons) {
      item.setAttribute("aria-pressed", snapshot.stonePresetId === presetId ? "true" : "false");
    }
    for (const [presetId, item] of lightButtons) {
      item.setAttribute("aria-pressed", snapshot.lightingPresetId === presetId ? "true" : "false");
    }
  }

  host.append(launcher, panel);
  setOpen(true);
  refresh();

  return {
    refresh,
    dispose(): void {
      launcher.remove();
      panel.remove();
    }
  };
}
