import { STONE_PRESETS, STONE_PRESET_IDS } from "../fixtures/stone-presets.js";
import { getSelectedTechnicalPresentation } from "../presentation/current-service.js";
import { renderAllTechnicalViews } from "../presentation/technical-diagram.js";
import { FRONT_PRESETS, FRONT_PRESET_IDS, LIGHTING_PRESETS, LIGHTING_PRESET_IDS } from "../runtime/presets.js";
import { moduleIdFromAlias, type ModuleAlias } from "../runtime/query.js";
import type { ViewerConfigurationState, ViewerInteractionState } from "../runtime/viewer-state.js";
import {
  VIEWER_UI_CONTRACT_VERSION,
  type FrontPresetId,
  type LightingPresetId,
  type StonePresetId,
  type ViewerUiApi,
  type ViewerUiCatalog,
  type ViewerUiSnapshot,
  type ViewerVisibilityOverride
} from "./ui-contract.js";

export const VIEWER_UI_MODULE_ALIASES: readonly ModuleAlias[] = ["01", "02", "03", "04", "05", "06", "07"];

export const CURRENT_VIEWER_UI_CATALOG: ViewerUiCatalog = {
  modules: VIEWER_UI_MODULE_ALIASES,
  frontPresets: FRONT_PRESET_IDS.map(id => ({ id, label: FRONT_PRESETS[id].label })),
  stonePresets: STONE_PRESET_IDS.map(id => ({ id, label: STONE_PRESETS[id].label })),
  lightingPresets: LIGHTING_PRESET_IDS.map(id => ({ id, label: LIGHTING_PRESETS[id].label }))
};

export interface ViewerEngineControlPort {
  getConfiguration(): ViewerConfigurationState;
  getInteraction(): ViewerInteractionState;
  setModuleVisibility(alias: string, value: ViewerVisibilityOverride): void;
  setFrontPreset(alias: string, presetId: FrontPresetId): void;
  clearFrontPreset(alias: string): void;
  setStonePreset(presetId: StonePresetId): void;
  setLightingPreset(presetId: LightingPresetId): void;
  resetConfiguration(): void;
  selectModule(alias: string | null): void;
}

export function moduleAliasFromId(moduleId: string | null): ModuleAlias | null {
  if (moduleId === null) return null;
  return VIEWER_UI_MODULE_ALIASES.find(alias => moduleIdFromAlias(alias) === moduleId) ?? null;
}

export function createViewerUiSnapshot(
  configuration: ViewerConfigurationState,
  interaction: ViewerInteractionState
): ViewerUiSnapshot {
  const visibilityByModule = {} as Record<ModuleAlias, ViewerVisibilityOverride>;
  const frontPresetByModule: Partial<Record<ModuleAlias, FrontPresetId>> = {};

  for (const alias of VIEWER_UI_MODULE_ALIASES) {
    const moduleId = moduleIdFromAlias(alias);
    visibilityByModule[alias] = configuration.visibilityByModule[moduleId] ?? "inherit";
    const frontPreset = configuration.frontPresetByModule[moduleId];
    if (frontPreset !== undefined) frontPresetByModule[alias] = frontPreset;
  }

  const selectedModuleAlias = moduleAliasFromId(interaction.selectedModuleId);
  const selectedTechnicalPresentation = getSelectedTechnicalPresentation(
    configuration,
    interaction.selectedModuleId
  );

  return {
    contractVersion: VIEWER_UI_CONTRACT_VERSION,
    selectedModuleAlias,
    visibilityByModule,
    frontPresetByModule,
    stonePresetId: configuration.stonePresetId,
    lightingPresetId: configuration.lightingPresetId,
    selectedTechnicalPresentation,
    selectedTechnicalViewAssets: selectedTechnicalPresentation === null
      ? []
      : renderAllTechnicalViews(selectedTechnicalPresentation)
  };
}

export function createViewerUiApi(runtime: ViewerEngineControlPort): ViewerUiApi {
  return {
    contractVersion: VIEWER_UI_CONTRACT_VERSION,
    getCatalog: () => CURRENT_VIEWER_UI_CATALOG,
    getSnapshot: () => createViewerUiSnapshot(runtime.getConfiguration(), runtime.getInteraction()),
    setModuleVisibility: (alias, value) => runtime.setModuleVisibility(alias, value),
    setFrontPreset: (alias, presetId) => runtime.setFrontPreset(alias, presetId),
    clearFrontPreset: alias => runtime.clearFrontPreset(alias),
    setStonePreset: presetId => runtime.setStonePreset(presetId),
    setLightingPreset: presetId => runtime.setLightingPreset(presetId),
    resetConfiguration: () => runtime.resetConfiguration(),
    selectModule: alias => runtime.selectModule(alias)
  };
}
