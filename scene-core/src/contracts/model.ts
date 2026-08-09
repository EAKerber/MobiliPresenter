import type { Aabb3, RigidTransform, Vec3 } from "../core/math.js";

export const SCENE_PACKAGE_SCHEMA_VERSION = "ScenePackage 0.1.0" as const;
export const MODULE_GEOMETRY_SCHEMA_VERSION = "ModuleGeometry 0.1.0" as const;
export const ENVIRONMENT_GEOMETRY_SCHEMA_VERSION = "EnvironmentGeometry 0.1.0" as const;
export const SOURCE_BINDING_SCHEMA_VERSION = "SourceBinding 0.1.0" as const;

export type MillimeterUnit = "mm";

export interface CoordinateSystem {
  readonly unit: MillimeterUnit;
  readonly xAxis: "right";
  readonly yAxis: "depth";
  readonly zAxis: "up";
  readonly handedness: "right-handed";
}

export const MOBILIPRESENTER_COORDINATE_SYSTEM: CoordinateSystem = {
  unit: "mm",
  xAxis: "right",
  yAxis: "depth",
  zAxis: "up",
  handedness: "right-handed"
};

export type EntityKind = "environment" | "module" | "appliance" | "fixture" | "accessory";
export type VisibilityIntent = "auto" | "on" | "off";
export type MountPolicy = "standalone" | "hosted";

export interface DimensionTripleMm {
  readonly width: number;
  readonly height: number;
  readonly depth: number;
}

export interface DimensionEvidence {
  readonly source: "promob-property" | "promob-dxf" | "technical-sheet" | "calibrated" | "inferred";
  readonly status: "confirmed" | "provided" | "calibrated" | "inferred" | "conflicted";
  readonly reference: string;
}

export interface GeometryDimensions {
  readonly nominalMm?: DimensionTripleMm;
  readonly geometryMm: DimensionTripleMm;
  readonly conflictPolicy: "geometry-wins-for-assembly-preserve-nominal";
  readonly evidence: readonly DimensionEvidence[];
}

export interface SurfaceGeometry {
  readonly id: string;
  readonly role: "panel" | "front" | "shelf" | "back" | "top" | "bottom" | "side" | "divider" | "glass" | "other";
  readonly localTransform: RigidTransform;
  readonly sizeMm: DimensionTripleMm;
  readonly materialSlot?: string;
  readonly sourceBindingIds: readonly string[];
}

export interface ApplianceSlot {
  readonly id: string;
  readonly role: string;
  readonly localTransform: RigidTransform;
  readonly clearSizeMm: DimensionTripleMm;
  readonly defaultApplianceId?: string;
}

export interface SceneEntityBase {
  readonly id: string;
  readonly kind: EntityKind;
  readonly transform: RigidTransform;
  readonly visibilityIntent: VisibilityIntent;
  readonly defaultVisible: boolean;
  readonly mountPolicy: MountPolicy;
  readonly hostId?: string;
}

export interface ModuleGeometry extends SceneEntityBase {
  readonly kind: "module";
  readonly schemaVersion: typeof MODULE_GEOMETRY_SCHEMA_VERSION;
  readonly dimensions: GeometryDimensions;
  readonly structuralEnvelope: Aabb3;
  readonly renderEnvelope: Aabb3;
  readonly surfaces: readonly SurfaceGeometry[];
  readonly applianceSlots: readonly ApplianceSlot[];
}

export interface EnvironmentGeometry extends SceneEntityBase {
  readonly kind: "environment";
  readonly schemaVersion: typeof ENVIRONMENT_GEOMETRY_SCHEMA_VERSION;
  readonly structuralEnvelope: Aabb3;
  readonly surfaces: readonly SurfaceGeometry[];
}

export interface SourceBinding {
  readonly schemaVersion: typeof SOURCE_BINDING_SCHEMA_VERSION;
  readonly id: string;
  readonly sourceFingerprint: string;
  readonly sourceSelector: {
    readonly layer?: string;
    readonly entityType?: "3DFACE" | "LINE";
  };
  readonly targetEntityId: string;
  readonly targetRole: string;
}

export interface FixedPerspectiveCamera {
  readonly id: string;
  readonly mode: "fixed";
  readonly projection: "perspective";
  readonly transform: RigidTransform;
  readonly targetMm: Vec3;
  readonly up: Vec3;
  readonly fovYDeg: number;
  readonly principalPointNormalized: readonly [number, number];
  readonly nearMm: number;
  readonly farMm: number;
  readonly status: "provided" | "calibrated" | "preview";
  readonly evidenceRefs: readonly string[];
}

export interface ScenePackage {
  readonly schemaVersion: typeof SCENE_PACKAGE_SCHEMA_VERSION;
  readonly sceneId: string;
  readonly coordinateSystem: CoordinateSystem;
  readonly camera: FixedPerspectiveCamera;
  readonly environment: readonly EnvironmentGeometry[];
  readonly modules: readonly ModuleGeometry[];
  readonly sourceBindings: readonly SourceBinding[];
}

export function identityTransform(): RigidTransform {
  return {
    translationMm: { x: 0, y: 0, z: 0 },
    rotation: { x: 0, y: 0, z: 0, w: 1 }
  };
}
