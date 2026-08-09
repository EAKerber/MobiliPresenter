import {
  currentAppearance,
  module03WithSink,
  setEntityMaterialOverride
} from "@mobilipresenter/scene-core";

export const styleAnchorAppearance = setEntityMaterialOverride(
  currentAppearance,
  module03WithSink.id,
  "front",
  "front-wood"
);
