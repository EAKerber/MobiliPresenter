import type { RigidTransform, Vec3 } from "../core/math.js";

export const UNDER_CAB_LIGHT_SCHEMA_VERSION = "UnderCabLightContract 1.0" as const;
export const UNDER_CAB_LIGHT_ITEM_ID = "scene/traditional/accessory/under-cab-led-06" as const;
export const UNDER_CAB_LIGHT_HOST_ID = "scene/traditional/module/upper-sink-microwave" as const;
export const UNDER_CAB_LIGHT_PROFILE_ID = "UNDER-CAB-CORNER-18-45-01" as const;

const SQRT_HALF = Math.SQRT1_2;

export interface UnderCabLightContract {
  readonly schemaVersion: typeof UNDER_CAB_LIGHT_SCHEMA_VERSION;
  readonly id: string;
  readonly itemId: string;
  readonly hostModuleId: string;
  readonly profileDefinitionId: string;
  readonly localTransform: RigidTransform;
  readonly visualSizeMm: { readonly width: number; readonly height: number; readonly depth: number };
  readonly mount: "rear-corner-surface-45deg";
  readonly profileAngleDeg: 45;
  readonly diffuser: "opal";
  readonly emitter: {
    readonly colorTemperatureK: 3000;
    readonly relativeIntensity: number;
    readonly localPositionNormalized: readonly [number, number, number];
    readonly localDirection: Vec3;
    readonly emittingWidthMm: number;
    readonly emittingHeightMm: number;
  };
  readonly provenance: {
    readonly source: "placement:LAYER115";
    readonly legacyEnvelopeMm: { readonly width: number; readonly height: number; readonly depth: number };
    readonly legacyLocalTransform: RigidTransform;
  };
  readonly evidenceRefs: readonly string[];
}

export const currentUnderCabLightContract: UnderCabLightContract = {
  schemaVersion: UNDER_CAB_LIGHT_SCHEMA_VERSION,
  id: "scene/traditional/lighting-contract/under-cab-06",
  itemId: UNDER_CAB_LIGHT_ITEM_ID,
  hostModuleId: UNDER_CAB_LIGHT_HOST_ID,
  profileDefinitionId: UNDER_CAB_LIGHT_PROFILE_ID,
  localTransform: {
    translationMm: { x: 0, y: 382, z: -18 },
    rotation: { x: 0, y: 0, z: 0, w: 1 }
  },
  visualSizeMm: { width: 1200, height: 18, depth: 18 },
  mount: "rear-corner-surface-45deg",
  profileAngleDeg: 45,
  diffuser: "opal",
  emitter: {
    colorTemperatureK: 3000,
    relativeIntensity: 0.65,
    localPositionNormalized: [0.5, 0.5, 0.5],
    localDirection: { x: 0, y: -SQRT_HALF, z: -SQRT_HALF },
    emittingWidthMm: 1180,
    emittingHeightMm: 16
  },
  provenance: {
    source: "placement:LAYER115",
    legacyEnvelopeMm: { width: 1200, height: 40.91, depth: 32.02 },
    legacyLocalTransform: {
      translationMm: { x: 0, y: 0, z: -40.91 },
      rotation: { x: 0, y: 0, z: 0, w: 1 }
    }
  },
  evidenceRefs: [
    "user-reference:rear-corner-profile-as-visual-base",
    "design-default:fh06-2:surface-mounted-corner-profile",
    "design-default:fh06-2:opal-diffuser-3000k-cri90",
    "promob-dxf:LAYER115:legacy-envelope-and-run-length"
  ]
};
