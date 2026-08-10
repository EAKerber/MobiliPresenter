import { STONE_PRESETS, STONE_PRESET_IDS, type StonePresetId } from "../fixtures/stone-presets.js";
import { FRONT_PRESETS, FRONT_PRESET_IDS, LIGHTING_PRESETS, LIGHTING_PRESET_IDS, type FrontPresetId, type LightingPresetId } from "../runtime/presets.js";
import { moduleIdFromAlias, type ModuleAlias } from "../runtime/query.js";
import type { ViewerConfigurationState, ViewerInteractionState, ViewerVisibilityOverride } from "../runtime/viewer-state.js";
import "./runtime-controls.css";

const MODULE_ALIASES: readonly ModuleAlias[] = ["01", "02", "03", "04", "05", "06", "07"];

export interface RuntimeControlsApi {
  getConfiguration(): ViewerConfigurationState;
  getInteraction(): ViewerInteractionState;
  isModuleVisible(alias: string): boolean;
  setModuleVisibility(alias: string, value: ViewerVisibilityOverride): void;
  setFrontPreset(alias: string, presetId: FrontPresetId): void;
  clearFrontPreset(alias: string): void;
  setStonePreset(presetId: StonePresetId): void;
  setLightingPreset(presetId: LightingPresetId): void;
  resetConfiguration(): void;
  selectModule(alias: string | null): void;
}

export interface RuntimeControlsUi {
  refresh(): void;
  dispose(): void;
}

function aliasForModuleId(moduleId: string | null): ModuleAlias | null {
  if (!moduleId) return null;
  return MODULE_ALIASES.find(alias => moduleIdFromAlias(alias) === moduleId) ?? null;
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

export function mountRuntimeControls(host: HTMLElement, api: RuntimeControlsApi): RuntimeControlsUi {
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
  const moduleButtons = new Map<ModuleAlias, HTMLButtonElement>();
  for (const alias of MODULE_ALIASES) {
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
  for (const presetId of FRONT_PRESET_IDS) {
    const item = button(FRONT_PRESETS[presetId].label);
    item.dataset.frontPreset = presetId;
    fronts.row.append(item);
    frontButtons.set(presetId, item);
  }
  panel.append(fronts.root);

  const stones = section("Pedra");
  const stoneButtons = new Map<StonePresetId, HTMLButtonElement>();
  for (const presetId of STONE_PRESET_IDS) {
    const item = button(STONE_PRESETS[presetId].label);
    item.dataset.stonePreset = presetId;
    item.addEventListener("click", () => runAction(() => api.setStonePreset(presetId)));
    stones.row.append(item);
    stoneButtons.set(presetId, item);
  }
  panel.append(stones.root);

  const lights = section("Iluminação");
  const lightButtons = new Map<LightingPresetId, HTMLButtonElement>();
  for (const presetId of LIGHTING_PRESET_IDS) {
    const item = button(LIGHTING_PRESETS[presetId].label);
    item.dataset.lightingPreset = presetId;
    item.addEventListener("click", () => runAction(() => api.setLightingPreset(presetId)));
    lights.row.append(item);
    lightButtons.set(presetId, item);
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
    const alias = aliasForModuleId(api.getInteraction().selectedModuleId);
    if (!alias) return;
    const visible = api.isModuleVisible(alias);
    runAction(() => api.setModuleVisibility(alias, visible ? "off" : "inherit"));
  });

  originalFront.addEventListener("click", () => {
    const alias = aliasForModuleId(api.getInteraction().selectedModuleId);
    if (!alias) return;
    runAction(() => api.clearFrontPreset(alias));
  });

  for (const [presetId, item] of frontButtons) {
    item.addEventListener("click", () => {
      const alias = aliasForModuleId(api.getInteraction().selectedModuleId);
      if (!alias) return;
      runAction(() => api.setFrontPreset(alias, presetId));
    });
  }

  function refresh(): void {
    const configuration = api.getConfiguration();
    const interaction = api.getInteraction();
    const selectedAlias = aliasForModuleId(interaction.selectedModuleId);

    for (const [alias, item] of moduleButtons) {
      const selected = alias === selectedAlias;
      item.setAttribute("aria-pressed", selected ? "true" : "false");
      item.title = api.isModuleVisible(alias) ? `Módulo ${alias} visível` : `Módulo ${alias} oculto`;
    }

    if (!selectedAlias) {
      selectedName.textContent = "Nenhum módulo";
      selectedState.textContent = "selecione na cena";
      visibilityButton.disabled = true;
      originalFront.disabled = true;
      for (const item of frontButtons.values()) item.disabled = true;
    } else {
      const visible = api.isModuleVisible(selectedAlias);
      selectedName.textContent = `Módulo ${selectedAlias}`;
      selectedState.textContent = visible ? "visível" : "oculto";
      visibilityButton.disabled = false;
      visibilityButton.textContent = visible ? "Ocultar módulo" : "Mostrar módulo";
      originalFront.disabled = false;
      for (const item of frontButtons.values()) item.disabled = false;

      const selectedId = moduleIdFromAlias(selectedAlias);
      const activeFront = configuration.frontPresetByModule[selectedId] ?? null;
      originalFront.setAttribute("aria-pressed", activeFront === null ? "true" : "false");
      for (const [presetId, item] of frontButtons) {
        item.setAttribute("aria-pressed", activeFront === presetId ? "true" : "false");
      }
    }

    for (const [presetId, item] of stoneButtons) {
      item.setAttribute("aria-pressed", configuration.stonePresetId === presetId ? "true" : "false");
    }
    for (const [presetId, item] of lightButtons) {
      item.setAttribute("aria-pressed", configuration.lightingPresetId === presetId ? "true" : "false");
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
