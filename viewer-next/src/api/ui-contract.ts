import type { DimensionTripleMm } from "@mobilipresenter/scene-core";
import type {
  TechnicalAxis,
  TechnicalPresentationPackage,
  TechnicalPresentationSpec
} from "../presentation/contracts.js";
import type { TechnicalDiagramAsset } from "../presentation/technical-diagram.js";
import type { StonePresetId } from "../fixtures/stone-presets.js";
import type { FrontPresetId, LightingPresetId } from "../runtime/presets.js";
import type { ModuleAlias } from "../runtime/query.js";
import type { ViewerVisibilityOverride } from "../runtime/viewer-state.js";

export const VIEWER_UI_CONTRACT_VERSION = "ViewerUiContract 0.2.0" as const;

export type {
  FrontPresetId,
  LightingPresetId,
  ModuleAlias,
  StonePresetId,
  TechnicalDiagramAsset,
  TechnicalPresentationPackage,
  ViewerVisibilityOverride
};

export interface ViewerUiOptionVisual {
  readonly kind: "material";
  readonly materialId: string;
  readonly previewColorSrgb: string;
}

export interface ViewerUiOption<TId extends string = string> {
  readonly id: TId;
  readonly label: string;
  readonly visual?: ViewerUiOptionVisual;
}

export interface ViewerUiModuleDimensions {
  readonly nominalMm?: DimensionTripleMm;
  readonly geometryMm: DimensionTripleMm;
  readonly display: {
    readonly order: readonly TechnicalAxis[];
    readonly labels: Readonly<Partial<Record<TechnicalAxis, string>>>;
    readonly prefer: "nominal" | "geometry";
  };
}

export interface ViewerUiModuleDescriptor {
  readonly alias: ModuleAlias;
  readonly entityId: string;
  readonly title: string;
  readonly shortLabel?: string;
  readonly category: string;
  readonly dimensions: ViewerUiModuleDimensions;
  readonly technicalPresentationStatus: "ready" | "unavailable";
  readonly presentation: TechnicalPresentationSpec;
}

export interface ViewerUiCatalog {
  readonly modules: readonly ModuleAlias[];
  readonly moduleDescriptors: readonly ViewerUiModuleDescriptor[];
  readonly furnitureFinishPresets: readonly ViewerUiOption<FrontPresetId>[];
  readonly frontPresets: readonly ViewerUiOption<FrontPresetId>[];
  readonly stonePresets: readonly ViewerUiOption<StonePresetId>[];
  readonly lightingPresets: readonly ViewerUiOption<LightingPresetId>[];
}

export type ViewerUiTechnicalPresentationAvailability =
  | { readonly status: "none"; readonly reason: null }
  | { readonly status: "ready"; readonly reason: null }
  | { readonly status: "unavailable"; readonly reason: "technical-catalog-entry-missing" };

export interface ViewerUiSnapshot {
  readonly contractVersion: typeof VIEWER_UI_CONTRACT_VERSION;
  readonly selectedModuleAlias: ModuleAlias | null;
  readonly visibilityByModule: Readonly<Record<ModuleAlias, ViewerVisibilityOverride>>;
  readonly furnitureFinishPresetId: FrontPresetId;
  readonly frontPresetByModule: Readonly<Partial<Record<ModuleAlias, FrontPresetId>>>;
  readonly stonePresetId: StonePresetId;
  readonly lightingPresetId: LightingPresetId;
  readonly selectedTechnicalPresentationAvailability: ViewerUiTechnicalPresentationAvailability;
  readonly selectedTechnicalPresentation: TechnicalPresentationPackage | null;
  readonly selectedTechnicalViewAssets: readonly TechnicalDiagramAsset[];
}

export interface ViewerUiApi {
  readonly contractVersion: typeof VIEWER_UI_CONTRACT_VERSION;
  getCatalog(): ViewerUiCatalog;
  getSnapshot(): ViewerUiSnapshot;
  setModuleVisibility(alias: ModuleAlias, value: ViewerVisibilityOverride): void;
  setFurnitureFinishPreset(presetId: FrontPresetId): void;
  setFrontPreset(alias: ModuleAlias, presetId: FrontPresetId): void;
  clearFrontPreset(alias: ModuleAlias): void;
  setStonePreset(presetId: StonePresetId): void;
  setLightingPreset(presetId: LightingPresetId): void;
  resetConfiguration(): void;
  selectModule(alias: ModuleAlias | null): void;
}
