import type { AppearancePackage } from "@mobilipresenter/scene-core";

export const FRONT_PRESET_IDS = ["warm-wood", "neutral-greige"] as const;
export type FrontPresetId = typeof FRONT_PRESET_IDS[number];

export interface FrontPreset {
  readonly id: FrontPresetId;
  readonly label: string;
  readonly materialId: string;
}

export const FRONT_PRESETS: Readonly<Record<FrontPresetId, FrontPreset>> = {
  "warm-wood": { id: "warm-wood", label: "Amadeirado quente", materialId: "front-wood" },
  "neutral-greige": { id: "neutral-greige", label: "Greige neutro", materialId: "front-primary" }
};

export const DEFAULT_FURNITURE_FINISH_PRESET_ID: FrontPresetId = "neutral-greige";

export const LIGHTING_PRESET_IDS = ["canonical", "soft-neutral", "warm-worktop"] as const;
export type LightingPresetId = typeof LIGHTING_PRESET_IDS[number];

export interface LightingPreset {
  readonly id: LightingPresetId;
  readonly label: string;
}

export const LIGHTING_PRESETS: Readonly<Record<LightingPresetId, LightingPreset>> = {
  canonical: { id: "canonical", label: "Canônico" },
  "soft-neutral": { id: "soft-neutral", label: "Neutro suave" },
  "warm-worktop": { id: "warm-worktop", label: "Bancada quente" }
};

function scaleBaseRig(
  appearance: AppearancePackage,
  intensityScale: number,
  kelvinOffset: number
): AppearancePackage["lighting"]["baseRig"] {
  return appearance.lighting.baseRig.map(light => ({
    ...light,
    relativeIntensity: light.relativeIntensity * intensityScale,
    colorTemperatureK: Math.max(1000, light.colorTemperatureK + kelvinOffset)
  }));
}

export function withLightingPreset(base: AppearancePackage, presetId: LightingPresetId): AppearancePackage {
  switch (presetId) {
    case "canonical":
      return base;
    case "soft-neutral":
      return {
        ...base,
        lighting: {
          ...base.lighting,
          id: `${base.lighting.id}/soft-neutral`,
          environment: {
            ...base.lighting.environment,
            relativeIntensity: base.lighting.environment.relativeIntensity * 0.9
          },
          baseRig: scaleBaseRig(base, 0.88, 150),
          post: {
            ...base.lighting.post,
            bloomStrength: base.lighting.post.bloomStrength * 0.75
          }
        }
      };
    case "warm-worktop":
      return {
        ...base,
        lighting: {
          ...base.lighting,
          id: `${base.lighting.id}/warm-worktop`,
          environment: {
            ...base.lighting.environment,
            relativeIntensity: base.lighting.environment.relativeIntensity * 0.92
          },
          baseRig: scaleBaseRig(base, 0.95, -450),
          post: {
            ...base.lighting.post,
            bloomStrength: base.lighting.post.bloomStrength * 1.1
          }
        }
      };
  }
}
