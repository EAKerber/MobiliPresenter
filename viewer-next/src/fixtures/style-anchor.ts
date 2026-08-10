import {
  currentAppearance,
  module03WithSink,
  setEntityMaterialOverride,
  type AppearancePackage
} from "@mobilipresenter/scene-core";
import { DEFAULT_STONE_PRESET_ID, withStonePreset } from "./stone-presets.js";

const stoneAppearance = withStonePreset(currentAppearance, DEFAULT_STONE_PRESET_ID);

const runtimeAppearance: AppearancePackage = {
  ...stoneAppearance,
  accessoryDefinitions: stoneAppearance.accessoryDefinitions.map(definition =>
    definition.id === "ACC-UNDERCAB-LED-01"
      ? { ...definition, emitters: [] }
      : definition
  )
};

export const styleAnchorAppearance = setEntityMaterialOverride(
  runtimeAppearance,
  module03WithSink.id,
  "front",
  "front-wood"
);
