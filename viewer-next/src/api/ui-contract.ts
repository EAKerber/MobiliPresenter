import type { TechnicalPresentationPackage } from "../presentation/contracts.js";
import type { TechnicalDiagramAsset } from "../presentation/technical-diagram.js";
import type { StonePresetId } from "../fixtures/stone-presets.js";
import type { FrontPresetId, LightingPresetId } from "../runtime/presets.js";
import type { ModuleAlias } from "../runtime/query.js";
import type { ViewerVisibilityOverride } from "../runtime/viewer-state.js";

export const VIEWER_UI_CONTRACT_VERSION = "ViewerUiContract 0.1.0" as const;

export type {
  FrontPresetId,
  LightingPresetId,
  ModuleAlias,
  StonePresetId,
  TechnicalDiagramAsset,
  TechnicalPresentationPackage,
  ViewerVisibilityOverride
};

export interface ViewerUiOption<TId extends string = string> {
  readonly id: TId;
  readonly label: string;
}

export interface ViewerUiCatalog {
  readonly modules: readonly ModuleAlias[];
  readonly frontPresets: readonly ViewerUiOption<FrontPresetId>[];
  readonly stonePresets: readonly ViewerUiOption<StonePresetId>[];
  readonly lightingPresets: readonly ViewerUiOption<LightingPresetId>[];
}

export interface ViewerUiSnapshot {
  readonly contractVersion: typeof VIEWER_UI_CONTRACT_VERSION;
  readonly selectedModuleAlias: ModuleAlias | null;
  readonly hoveredModuleAlias: ModuleAlias | null;
  readonly visibilityByModule: Readonly<Record<ModuleAlias, ViewerVisibilityOverride>>;
  readonly frontPresetByModule: Readonly<Partial<Record<ModuleAlias, FrontPresetId>>>;
  readonly stonePresetId: StonePresetId;
  readonly lightingPresetId: LightingPresetId;
  readonly selectedTechnicalPresentation: TechnicalPresentationPackage | null;
  readonly selectedTechnicalViewAssets: readonly TechnicalDiagramAsset[];
}

export type ViewerUiListener = (snapshot: ViewerUiSnapshot) => void;

export interface ViewerUiApi {
  readonly contractVersion: typeof VIEWER_UI_CONTRACT_VERSION;
  getCatalog(): ViewerUiCatalog;
  getSnapshot(): ViewerUiSnapshot;
  subscribe(listener: ViewerUiListener): () => void;
  setModuleVisibility(alias: ModuleAlias, value: ViewerVisibilityOverride): void;
  setFrontPreset(alias: ModuleAlias, presetId: FrontPresetId): void;
  clearFrontPreset(alias: ModuleAlias): void;
  setStonePreset(presetId: StonePresetId): void;
  setLightingPreset(presetId: LightingPresetId): void;
  resetConfiguration(): void;
  selectModule(alias: ModuleAlias | null): void;
}
