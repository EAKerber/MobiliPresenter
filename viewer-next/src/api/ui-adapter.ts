import { currentSceneBase } from "@mobilipresenter/scene-core";
import { STONE_PRESETS, STONE_PRESET_IDS } from "../fixtures/stone-presets.js";
import { styleAnchorAppearance } from "../fixtures/style-anchor.js";
import { getSelectedTechnicalPresentationResult } from "../presentation/current-service.js";
import { CURRENT_TECHNICAL_CATALOG } from "../presentation/technical-catalog.js";
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
  type ViewerUiModuleDescriptor,
  type ViewerUiOption,
  type ViewerUiSnapshot,
  type ViewerVisibilityOverride
} from "./ui-contract.js";

export const VIEWER_UI_MODULE_ALIASES: readonly ModuleAlias[] = ["01", "02", "03", "04", "05", "06", "07"];

function frontPresetOptions(): readonly ViewerUiOption<FrontPresetId>[] {
  return FRONT_PRESET_IDS.map(id => {
    const preset = FRONT_PRESETS[id];
    const material = styleAnchorAppearance.materials.find(candidate => candidate.id === preset.materialId);
    if (!material) throw new Error(`VIEWER_UI_FINISH_MATERIAL_NOT_FOUND:${preset.materialId}`);
    return {
      id,
      label: preset.label,
      visual: {
        kind: "material" as const,
        materialId: preset.materialId,
        previewColorSrgb: material.baseColorSrgb
      }
    };
  });
}

function stonePresetOptions(): readonly ViewerUiOption<StonePresetId>[] {
  return STONE_PRESET_IDS.map(id => {
    const preset = STONE_PRESETS[id];
    return {
      id,
      label: preset.label,
      visual: {
        kind: "material" as const,
        materialId: preset.materialId,
        previewColorSrgb: preset.baseColorSrgb
      }
    };
  });
}

function moduleDescriptor(alias: ModuleAlias): ViewerUiModuleDescriptor {
  const entityId = moduleIdFromAlias(alias);
  const module = currentSceneBase.modules.find(candidate => candidate.id === entityId);
  if (!module) throw new Error(`VIEWER_UI_MODULE_NOT_FOUND:${alias}:${entityId}`);
  const entry = CURRENT_TECHNICAL_CATALOG.find(candidate => candidate.target.kind === "module" && candidate.target.entityId === entityId);
  const display = entry?.dimensions ?? {
    order: ["width", "height", "depth"] as const,
    labels: { width: "L", height: "A", depth: "P" },
    prefer: "nominal" as const
  };
  return {
    alias,
    entityId,
    title: entry?.identity.title ?? `Módulo ${alias}`,
    ...(entry?.identity.shortLabel ? { shortLabel: entry.identity.shortLabel } : {}),
    category: entry?.identity.category ?? "módulo",
    dimensions: {
      ...(module.dimensions.nominalMm ? { nominalMm: module.dimensions.nominalMm } : {}),
      geometryMm: module.dimensions.geometryMm,
      display
    },
    technicalPresentationStatus: entry ? "ready" : "unavailable",
    presentation: entry?.presentation ?? { primaryEntityId: entityId, companionEntityIds: [] }
  };
}

const frontOptions = frontPresetOptions();

export const CURRENT_VIEWER_UI_CATALOG: ViewerUiCatalog = {
  modules: VIEWER_UI_MODULE_ALIASES,
  moduleDescriptors: VIEWER_UI_MODULE_ALIASES.map(moduleDescriptor),
  furnitureFinishPresets: frontOptions,
  frontPresets: frontOptions,
  stonePresets: stonePresetOptions(),
  lightingPresets: LIGHTING_PRESET_IDS.map(id => ({ id, label: LIGHTING_PRESETS[id].label }))
};

export interface ViewerEngineControlPort {
  getConfiguration(): ViewerConfigurationState;
  getInteraction(): ViewerInteractionState;
  setModuleVisibility(alias: string, value: ViewerVisibilityOverride): void;
  setFurnitureFinishPreset(presetId: FrontPresetId): void;
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
  const presentationResult = getSelectedTechnicalPresentationResult(
    configuration,
    interaction.selectedModuleId
  );
  const selectedTechnicalPresentation = presentationResult.presentation;
  const selectedTechnicalPresentationAvailability = presentationResult.status === "unavailable"
    ? { status: "unavailable" as const, reason: presentationResult.reason }
    : presentationResult.status === "ready"
      ? { status: "ready" as const, reason: null }
      : { status: "none" as const, reason: null };

  return {
    contractVersion: VIEWER_UI_CONTRACT_VERSION,
    selectedModuleAlias,
    visibilityByModule,
    furnitureFinishPresetId: configuration.furnitureFinishPresetId,
    frontPresetByModule,
    stonePresetId: configuration.stonePresetId,
    lightingPresetId: configuration.lightingPresetId,
    selectedTechnicalPresentationAvailability,
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
    setFurnitureFinishPreset: presetId => runtime.setFurnitureFinishPreset(presetId),
    setFrontPreset: (alias, presetId) => runtime.setFrontPreset(alias, presetId),
    clearFrontPreset: alias => runtime.clearFrontPreset(alias),
    setStonePreset: presetId => runtime.setStonePreset(presetId),
    setLightingPreset: presetId => runtime.setLightingPreset(presetId),
    resetConfiguration: () => runtime.resetConfiguration(),
    selectModule: alias => runtime.selectModule(alias)
  };
}
