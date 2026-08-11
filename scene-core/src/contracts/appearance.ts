import type { Vec3 } from "../core/math.js";
import type { DimensionTripleMm } from "./model.js";

export const APPEARANCE_PACKAGE_SCHEMA_VERSION = "AppearancePackage 0.1.0" as const;
export const APPLIANCE_DEFINITION_SCHEMA_VERSION = "ApplianceDefinition 0.1.0" as const;
export const ACCESSORY_DEFINITION_SCHEMA_VERSION = "AccessoryDefinition 0.1.0" as const;
export const MATERIAL_DEFINITION_SCHEMA_VERSION = "MaterialDefinition 0.1.0" as const;
export const LIGHTING_POLICY_SCHEMA_VERSION = "LightingPolicy 0.1.0" as const;

export type ApplianceRole =
  | "laundry-washer"
  | "laundry-tank"
  | "freestanding-range"
  | "built-in-oven"
  | "cooktop"
  | "hood"
  | "built-in-microwave"
  | "refrigerator"
  | "kitchen-sink";

export type AccessoryRole = "countertop" | "plinth" | "under-cab-light" | "trim";

export type FitPolicy =
  | "fit-to-slot-front-authoritative"
  | "top-surface-fit"
  | "under-cab-fit"
  | "letterbox-allowed-within-slot"
  | "fit-to-environment-envelope"
  | "fit-to-source-envelope-preserve-front-proportions"
  | "fixture-adjustable-preserve-basin-language"
  | "stone-cutout-dependent"
  | "allow-small-nonuniform-scale-depth<=3%";

export interface SemanticEmitterDefinition {
  readonly id: string;
  readonly type: "point" | "line" | "rect";
  readonly colorTemperatureK: number;
  readonly relativeIntensity: number;
  readonly localPositionNormalized: readonly [number, number, number];
  readonly localDirection?: Vec3;
}

export interface ApplianceDefinition {
  readonly schemaVersion: typeof APPLIANCE_DEFINITION_SCHEMA_VERSION;
  readonly id: string;
  readonly role: ApplianceRole;
  readonly appearanceFamily: string;
  readonly nominalAppearanceMm: DimensionTripleMm;
  readonly fitPolicy: FitPolicy;
  readonly assetPolicy: "parametric-preferred" | "normalized-external-allowed";
  readonly requiredVisualFeatures: readonly string[];
  readonly materialSlots: readonly string[];
  readonly emitters: readonly SemanticEmitterDefinition[];
  readonly sourceHints: readonly string[];
}

export interface AccessoryDefinition {
  readonly schemaVersion: typeof ACCESSORY_DEFINITION_SCHEMA_VERSION;
  readonly id: string;
  readonly role: AccessoryRole;
  readonly materialSlots: readonly string[];
  readonly emitters: readonly SemanticEmitterDefinition[];
  readonly sourceHints: readonly string[];
}

export type MaterialMappingPolicy = "panel-local" | "module-continuous" | "world-continuous";

export interface MaterialDefinition {
  readonly schemaVersion: typeof MATERIAL_DEFINITION_SCHEMA_VERSION;
  readonly id: string;
  readonly mappingPolicy: MaterialMappingPolicy;
  readonly baseColorSrgb: string;
  readonly roughness: number;
  readonly metallic: number;
  readonly opacity: number;
  readonly transmission: number;
  readonly emissiveSrgb?: string;
  readonly emissiveIntensity?: number;
  readonly physicalTextureScaleMm?: readonly [number, number];
  readonly grainDirection?: "u" | "v" | "world-x" | "world-y" | "world-z";
  readonly textureUri?: string;
  readonly normalUri?: string;
}

export interface MaterialAssignments {
  readonly defaultsBySlot: Readonly<Record<string, string>>;
  readonly entityOverrides: Readonly<Record<string, Readonly<Record<string, string>>>>;
}

export interface RelativeLight {
  readonly id: string;
  readonly type: "ambient" | "directional" | "rect";
  readonly relativeIntensity: number;
  readonly colorTemperatureK: number;
  readonly direction?: Vec3;
  readonly softness: number;
}

export interface LightingPolicy {
  readonly schemaVersion: typeof LIGHTING_POLICY_SCHEMA_VERSION;
  readonly id: string;
  readonly units: "relative-renderer-neutral";
  readonly environment: {
    readonly type: "neutral-room-pmrem";
    readonly relativeIntensity: number;
  };
  readonly baseRig: readonly RelativeLight[];
  readonly semanticEmitters: "from-effective-visible-entities";
  readonly post: {
    readonly bloomEnabled: boolean;
    readonly bloomStrength: number;
    readonly bloomRadius: number;
    readonly emitterMaskOnly: true;
    readonly vignetteStrength: number;
  };
}

export interface AppearancePackage {
  readonly schemaVersion: typeof APPEARANCE_PACKAGE_SCHEMA_VERSION;
  readonly applianceDefinitions: readonly ApplianceDefinition[];
  readonly accessoryDefinitions: readonly AccessoryDefinition[];
  readonly materials: readonly MaterialDefinition[];
  readonly assignments: MaterialAssignments;
  readonly lighting: LightingPolicy;
}
