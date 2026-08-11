import type { TechnicalPresentationPackage } from "../presentation/contracts.js";

export const VIEWER_UI_CONTRACT_VERSION = "ViewerUiContract 0.1.0" as const;

export type ModuleAlias = "01" | "02" | "03" | "04" | "05" | "06" | "07";
export type ViewerVisibilityOverride = "inherit" | "on" | "off";
export type FrontPresetId = "warm-wood" | "neutral-greige";
export type StonePresetId = "light-speckled" | "warm-beige-speckled" | "graphite-speckled";
export type LightingPresetId = "canonical" | "soft-neutral" | "warm-worktop";

export interface ViewerUiOption {
  readonly id: string;
  readonly label: string;
}

export interface ViewerUiCatalog {
  readonly modules: readonly ModuleAlias[];
  readonly frontPresets: readonly ViewerUiOption[];
  readonly stonePresets: readonly ViewerUiOption[];
  readonly lightingPresets: readonly ViewerUiOption[];
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
