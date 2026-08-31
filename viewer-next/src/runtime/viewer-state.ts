import {
  setEntityMaterialOverride,
  setVisibilityIntent,
  type AppearancePackage,
  type ScenePackage
} from "@mobilipresenter/scene-core";
import {
  DEFAULT_STONE_PRESET_ID,
  STONE_PRESET_IDS,
  withStonePreset,
  type StonePresetId
} from "../fixtures/stone-presets.js";
import {
  DEFAULT_FURNITURE_FINISH_PRESET_ID,
  FRONT_PRESET_IDS,
  FRONT_PRESETS,
  LIGHTING_PRESET_IDS,
  withLightingPreset,
  type FrontPresetId,
  type LightingPresetId
} from "./presets.js";

export const VIEWER_CONFIGURATION_SCHEMA_VERSION = "ViewerConfigurationState 0.1.1" as const;
export const VIEWER_INTERACTION_SCHEMA_VERSION = "ViewerInteractionState 0.1.0" as const;

export type ViewerVisibilityOverride = "inherit" | "on" | "off";

export interface ViewerConfigurationState {
  readonly schemaVersion: typeof VIEWER_CONFIGURATION_SCHEMA_VERSION;
  readonly visibilityByModule: Readonly<Record<string, ViewerVisibilityOverride>>;
  readonly furnitureFinishPresetId: FrontPresetId;
  readonly frontPresetByModule: Readonly<Record<string, FrontPresetId>>;
  readonly stonePresetId: StonePresetId;
  readonly lightingPresetId: LightingPresetId;
}

export interface ViewerInteractionState {
  readonly schemaVersion: typeof VIEWER_INTERACTION_SCHEMA_VERSION;
  readonly hoveredModuleId: string | null;
  readonly selectedModuleId: string | null;
}

export type ViewerConfigurationAction =
  | { readonly type: "set-module-visibility"; readonly moduleId: string; readonly value: ViewerVisibilityOverride }
  | { readonly type: "set-furniture-finish-preset"; readonly presetId: FrontPresetId }
  | { readonly type: "set-front-preset"; readonly moduleId: string; readonly presetId: FrontPresetId }
  | { readonly type: "clear-front-preset"; readonly moduleId: string }
  | { readonly type: "set-stone-preset"; readonly presetId: StonePresetId }
  | { readonly type: "set-lighting-preset"; readonly presetId: LightingPresetId }
  | { readonly type: "reset-configuration" };

export type ViewerInteractionAction =
  | { readonly type: "hover-module"; readonly moduleId: string | null }
  | { readonly type: "select-module"; readonly moduleId: string | null }
  | { readonly type: "reset-interaction" };

export function createDefaultViewerConfiguration(): ViewerConfigurationState {
  return {
    schemaVersion: VIEWER_CONFIGURATION_SCHEMA_VERSION,
    visibilityByModule: {},
    furnitureFinishPresetId: DEFAULT_FURNITURE_FINISH_PRESET_ID,
    frontPresetByModule: {},
    stonePresetId: DEFAULT_STONE_PRESET_ID,
    lightingPresetId: "canonical"
  };
}

export function createDefaultViewerInteraction(): ViewerInteractionState {
  return {
    schemaVersion: VIEWER_INTERACTION_SCHEMA_VERSION,
    hoveredModuleId: null,
    selectedModuleId: null
  };
}

function withoutKey<T>(source: Readonly<Record<string, T>>, key: string): Readonly<Record<string, T>> {
  if (!(key in source)) return source;
  const next = { ...source };
  delete next[key];
  return next;
}

export function reduceViewerConfiguration(
  state: ViewerConfigurationState,
  action: ViewerConfigurationAction
): ViewerConfigurationState {
  switch (action.type) {
    case "set-module-visibility":
      return {
        ...state,
        visibilityByModule: action.value === "inherit"
          ? withoutKey(state.visibilityByModule, action.moduleId)
          : { ...state.visibilityByModule, [action.moduleId]: action.value }
      };
    case "set-furniture-finish-preset":
      return { ...state, furnitureFinishPresetId: action.presetId };
    case "set-front-preset":
      return {
        ...state,
        frontPresetByModule: { ...state.frontPresetByModule, [action.moduleId]: action.presetId }
      };
    case "clear-front-preset":
      return { ...state, frontPresetByModule: withoutKey(state.frontPresetByModule, action.moduleId) };
    case "set-stone-preset":
      return { ...state, stonePresetId: action.presetId };
    case "set-lighting-preset":
      return { ...state, lightingPresetId: action.presetId };
    case "reset-configuration":
      return createDefaultViewerConfiguration();
  }
}

export function reduceViewerInteraction(
  state: ViewerInteractionState,
  action: ViewerInteractionAction
): ViewerInteractionState {
  switch (action.type) {
    case "hover-module":
      return { ...state, hoveredModuleId: action.moduleId };
    case "select-module":
      return { ...state, selectedModuleId: action.moduleId };
    case "reset-interaction":
      return createDefaultViewerInteraction();
  }
}

function moduleById(scene: ScenePackage, moduleId: string) {
  const module = scene.modules.find(candidate => candidate.id === moduleId);
  if (!module) throw new Error(`VIEWER_MODULE_NOT_FOUND:${moduleId}`);
  return module;
}

function assertFrontPreset(presetId: FrontPresetId): void {
  if (!FRONT_PRESET_IDS.includes(presetId)) throw new Error(`VIEWER_FRONT_PRESET_NOT_FOUND:${presetId}`);
}

function assertFrontPresetTarget(scene: ScenePackage, moduleId: string, presetId: FrontPresetId): void {
  const module = moduleById(scene, moduleId);
  assertFrontPreset(presetId);
  if (!module.geometry.some(primitive => primitive.materialSlot === "front")) {
    throw new Error(`VIEWER_MODULE_FRONT_SLOT_MISSING:${moduleId}`);
  }
}

export function deriveViewerScene(
  base: ScenePackage,
  state: ViewerConfigurationState
): ScenePackage {
  let scene = base;
  for (const [moduleId, override] of Object.entries(state.visibilityByModule).sort(([a], [b]) => a.localeCompare(b))) {
    moduleById(base, moduleId);
    if (override === "inherit") continue;
    scene = setVisibilityIntent(scene, moduleId, override);
  }
  return scene;
}

function applyGlobalFurnitureFinish(
  appearance: AppearancePackage,
  scene: ScenePackage,
  presetId: FrontPresetId
): AppearancePackage {
  assertFrontPreset(presetId);
  const materialId = FRONT_PRESETS[presetId].materialId;
  let next = appearance;
  for (const module of [...scene.modules].sort((a, b) => a.id.localeCompare(b.id))) {
    if (!module.geometry.some(primitive => primitive.materialSlot === "front")) continue;
    next = setEntityMaterialOverride(next, module.id, "front", materialId);
  }
  return next;
}

export function deriveViewerAppearance(
  base: AppearancePackage,
  scene: ScenePackage,
  state: ViewerConfigurationState
): AppearancePackage {
  if (!STONE_PRESET_IDS.includes(state.stonePresetId)) {
    throw new Error(`VIEWER_STONE_PRESET_NOT_FOUND:${state.stonePresetId}`);
  }
  if (!LIGHTING_PRESET_IDS.includes(state.lightingPresetId)) {
    throw new Error(`VIEWER_LIGHTING_PRESET_NOT_FOUND:${state.lightingPresetId}`);
  }

  let appearance = withStonePreset(base, state.stonePresetId);
  appearance = applyGlobalFurnitureFinish(appearance, scene, state.furnitureFinishPresetId);
  for (const [moduleId, presetId] of Object.entries(state.frontPresetByModule).sort(([a], [b]) => a.localeCompare(b))) {
    assertFrontPresetTarget(scene, moduleId, presetId);
    appearance = setEntityMaterialOverride(appearance, moduleId, "front", FRONT_PRESETS[presetId].materialId);
  }
  return withLightingPreset(appearance, state.lightingPresetId);
}

export function configurationFingerprint(state: ViewerConfigurationState): string {
  const visibility = Object.entries(state.visibilityByModule).sort(([a], [b]) => a.localeCompare(b));
  const fronts = Object.entries(state.frontPresetByModule).sort(([a], [b]) => a.localeCompare(b));
  return JSON.stringify({
    schemaVersion: state.schemaVersion,
    visibility,
    furnitureFinishPresetId: state.furnitureFinishPresetId,
    fronts,
    stonePresetId: state.stonePresetId,
    lightingPresetId: state.lightingPresetId
  });
}
