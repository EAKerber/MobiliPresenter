import { allSceneEntities, currentSceneBase } from "@mobilipresenter/scene-core";
import { styleAnchorAppearance } from "../fixtures/style-anchor.js";
import { deriveViewerAppearance, deriveViewerScene, type ViewerConfigurationState } from "../runtime/viewer-state.js";
import { CURRENT_TECHNICAL_CATALOG } from "./technical-catalog.js";
import {
  compileTechnicalPresentation,
  compileTechnicalPresentationByAlias,
  type TechnicalPresentationCompilerInput
} from "./compile.js";
import type { TechnicalPresentationPackage } from "./contracts.js";

export type SelectedTechnicalPresentationUnavailableReason = "technical-catalog-entry-missing";

export type SelectedTechnicalPresentationResult =
  | { readonly status: "none"; readonly reason: null; readonly presentation: null }
  | {
      readonly status: "unavailable";
      readonly reason: SelectedTechnicalPresentationUnavailableReason;
      readonly presentation: null;
    }
  | { readonly status: "ready"; readonly reason: null; readonly presentation: TechnicalPresentationPackage };

export function createCurrentTechnicalPresentationInput(
  configuration: ViewerConfigurationState
): TechnicalPresentationCompilerInput {
  const scene = deriveViewerScene(currentSceneBase, configuration);
  const appearance = deriveViewerAppearance(styleAnchorAppearance, scene, configuration);
  return { scene, appearance, configuration, catalog: CURRENT_TECHNICAL_CATALOG };
}

export function getCurrentTechnicalPresentation(
  configuration: ViewerConfigurationState,
  targetEntityId: string
): TechnicalPresentationPackage {
  return compileTechnicalPresentation(createCurrentTechnicalPresentationInput(configuration), targetEntityId);
}

export function getCurrentTechnicalPresentationByAlias(
  configuration: ViewerConfigurationState,
  alias: string
): TechnicalPresentationPackage {
  return compileTechnicalPresentationByAlias(createCurrentTechnicalPresentationInput(configuration), alias);
}

export function getSelectedTechnicalPresentationResult(
  configuration: ViewerConfigurationState,
  selectedEntityId: string | null
): SelectedTechnicalPresentationResult {
  if (selectedEntityId === null) return { status: "none", reason: null, presentation: null };

  const input = createCurrentTechnicalPresentationInput(configuration);
  const targetExists = allSceneEntities(input.scene).some(entity => entity.id === selectedEntityId);
  if (!targetExists) throw new Error(`TECHNICAL_PRESENTATION_TARGET_NOT_FOUND:${selectedEntityId}`);

  const catalogEntry = input.catalog.find(entry => entry.target.entityId === selectedEntityId);
  if (!catalogEntry) {
    return {
      status: "unavailable",
      reason: "technical-catalog-entry-missing",
      presentation: null
    };
  }

  return {
    status: "ready",
    reason: null,
    presentation: compileTechnicalPresentation(input, selectedEntityId)
  };
}

export function getSelectedTechnicalPresentation(
  configuration: ViewerConfigurationState,
  selectedEntityId: string | null
): TechnicalPresentationPackage | null {
  return getSelectedTechnicalPresentationResult(configuration, selectedEntityId).presentation;
}
