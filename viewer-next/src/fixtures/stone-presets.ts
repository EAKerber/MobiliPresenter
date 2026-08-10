import {
  MATERIAL_DEFINITION_SCHEMA_VERSION,
  STONE02_ID,
  STONE03_ID,
  setEntityMaterialOverride,
  type AppearancePackage,
  type MaterialDefinition
} from "@mobilipresenter/scene-core";

export const STONE_PRESET_IDS = [
  "light-speckled",
  "warm-beige-speckled",
  "graphite-speckled"
] as const;

export type StonePresetId = typeof STONE_PRESET_IDS[number];

export interface StonePreset {
  readonly id: StonePresetId;
  readonly materialId: string;
  readonly label: string;
  readonly baseColorSrgb: string;
  readonly roughness: number;
  readonly physicalPatternScaleMm: readonly [number, number];
}

export const STONE_PRESETS: Readonly<Record<StonePresetId, StonePreset>> = {
  "light-speckled": {
    id: "light-speckled",
    materialId: "stone-speckled-light",
    label: "Claro salpicado",
    baseColorSrgb: "#C9C1B2",
    roughness: 0.46,
    physicalPatternScaleMm: [600, 600]
  },
  "warm-beige-speckled": {
    id: "warm-beige-speckled",
    materialId: "stone-speckled-warm-beige",
    label: "Bege quente salpicado",
    baseColorSrgb: "#B9A58E",
    roughness: 0.48,
    physicalPatternScaleMm: [600, 600]
  },
  "graphite-speckled": {
    id: "graphite-speckled",
    materialId: "stone-speckled-graphite",
    label: "Grafite salpicado",
    baseColorSrgb: "#555453",
    roughness: 0.43,
    physicalPatternScaleMm: [600, 600]
  }
};

export const DEFAULT_STONE_PRESET_ID: StonePresetId = "light-speckled";

function presetMaterial(preset: StonePreset): MaterialDefinition {
  return {
    schemaVersion: MATERIAL_DEFINITION_SCHEMA_VERSION,
    id: preset.materialId,
    mappingPolicy: "world-continuous",
    baseColorSrgb: preset.baseColorSrgb,
    roughness: preset.roughness,
    metallic: 0,
    opacity: 1,
    transmission: 0,
    physicalTextureScaleMm: preset.physicalPatternScaleMm
  };
}

export function withStonePreset(
  base: AppearancePackage,
  presetId: StonePresetId = DEFAULT_STONE_PRESET_ID
): AppearancePackage {
  const preset = STONE_PRESETS[presetId];
  const presetMaterialIds = new Set(STONE_PRESET_IDS.map(id => STONE_PRESETS[id].materialId));
  const materials = [
    ...base.materials.filter(material => !presetMaterialIds.has(material.id)),
    ...STONE_PRESET_IDS.map(id => presetMaterial(STONE_PRESETS[id]))
  ];
  const augmented: AppearancePackage = { ...base, materials };
  const stone02 = setEntityMaterialOverride(augmented, STONE02_ID, "stone", preset.materialId);
  return setEntityMaterialOverride(stone02, STONE03_ID, "stone", preset.materialId);
}
