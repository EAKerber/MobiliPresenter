import { currentSceneBase } from "@mobilipresenter/scene-core";
import { styleAnchorAppearance } from "../fixtures/style-anchor.js";
import { deriveViewerAppearance, deriveViewerScene, type ViewerConfigurationState } from "../runtime/viewer-state.js";
import { CURRENT_TECHNICAL_CATALOG } from "./technical-catalog.js";
import {
  compileTechnicalPresentation,
  compileTechnicalPresentationByAlias,
  type TechnicalPresentationCompilerInput
} from "./compile.js";
import type { TechnicalPresentationPackage } from "./contracts.js";

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

export function getSelectedTechnicalPresentation(
  configuration: ViewerConfigurationState,
  selectedEntityId: string | null
): TechnicalPresentationPackage | null {
  return selectedEntityId === null ? null : getCurrentTechnicalPresentation(configuration, selectedEntityId);
}
