import {
  currentAppearance,
  module03WithSink,
  setEntityMaterialOverride
} from "@mobilipresenter/scene-core";
import { DEFAULT_STONE_PRESET_ID, withStonePreset } from "./stone-presets.js";

const stoneAppearance = withStonePreset(currentAppearance, DEFAULT_STONE_PRESET_ID);

export const styleAnchorAppearance = setEntityMaterialOverride(
  stoneAppearance,
  module03WithSink.id,
  "front",
  "front-wood"
);
