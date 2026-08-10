import {
  currentAppearance,
  module02,
  module03WithSink,
  setEntityMaterialOverride,
  type AppearancePackage,
  type MaterialDefinition
} from "@mobilipresenter/scene-core";
import { DEFAULT_STONE_PRESET_ID, withStonePreset } from "./stone-presets.js";

const stoneAppearance = withStonePreset(currentAppearance, DEFAULT_STONE_PRESET_ID);

function tuneMaterial(definition: MaterialDefinition): MaterialDefinition {
  switch (definition.id) {
    case "front-wood":
      return { ...definition, baseColorSrgb: "#A8744D", roughness: 0.62 };
    case "front-primary":
      return { ...definition, baseColorSrgb: "#B2ADA5", roughness: 0.62 };
    case "wall-white":
      return { ...definition, baseColorSrgb: "#F1EEE8", roughness: 0.9 };
    case "carcass-white":
      return { ...definition, baseColorSrgb: "#F4F1EB", roughness: 0.8 };
    default:
      return definition;
  }
}

const runtimeAppearance: AppearancePackage = {
  ...stoneAppearance,
  materials: stoneAppearance.materials.map(tuneMaterial),
  accessoryDefinitions: stoneAppearance.accessoryDefinitions.map(definition =>
    definition.id === "ACC-UNDERCAB-LED-01"
      ? { ...definition, emitters: [] }
      : definition
  )
};

const module03Wood = setEntityMaterialOverride(
  runtimeAppearance,
  module03WithSink.id,
  "front",
  "front-wood"
);

export const styleAnchorAppearance = setEntityMaterialOverride(
  module03Wood,
  module02.id,
  "front",
  "front-wood"
);
