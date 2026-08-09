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
  unit: "mm", xAxis: "right", yAxis: "depth", zAxis: "up", handedness: "right-handed"
};

export type EntityKind = "environment" | "module" | "appliance" | "fixture" | "accessory";
export type VisibilityIntent = "auto" | "on" | "off";
export type MountPolicy = "standalone" | "hosted";
export type SemanticLayer = 0 | 1 | 2;
export type GeometryRole = "panel" | "front" | "shelf" | "back" | "top" | "bottom" | "side" | "divider" | "glass" | "wall" | "column" | "stone" | "plinth" | "light-profile" | "other";

export interface DimensionTripleMm { readonly width: number; readonly height: number; readonly depth: number; }
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

export interface GeometryPrimitiveBase {
  readonly id: string;
  readonly role: GeometryRole;
  readonly localTransform: RigidTransform;
  readonly materialSlot?: string;
  readonly sourceBindingIds: readonly string[];
}
export interface BoxGeometry extends GeometryPrimitiveBase { readonly primitive: "box"; readonly sizeMm: DimensionTripleMm; }
export interface FaceGeometry extends GeometryPrimitiveBase {
  readonly primitive: "face";
  readonly uAxis: Vec3;
  readonly vAxis: Vec3;
  readonly normal: Vec3;
  readonly sizeMm: readonly [number, number];
}
export type GeometryPrimitive = BoxGeometry | FaceGeometry;

export interface ApplianceSlot {
  readonly id: string;
  readonly role: string;
  readonly localTransform: RigidTransform;
  readonly clearSizeMm: DimensionTripleMm;
  readonly defaultApplianceId?: string;
  readonly status?: "confirmed" | "inferred";
  readonly evidenceRefs?: readonly string[];
}

export interface SceneEntityBase {
  readonly id: string;
  readonly kind: EntityKind;
  readonly transform: RigidTransform;
  readonly visibilityIntent: VisibilityIntent;
  readonly defaultVisible: boolean;
  readonly controllable?: boolean;
  readonly mountPolicy: MountPolicy;
  readonly hostId?: string;
}

export interface SceneItem extends SceneEntityBase {
  readonly kind: "appliance" | "fixture" | "accessory";
  readonly definitionId: string;
  readonly slotId?: string;
  readonly targetEnvelopeMm?: DimensionTripleMm;
  readonly geometry?: readonly GeometryPrimitive[];
}

export interface ModuleGeometry extends SceneEntityBase {
  readonly kind: "module";
  readonly schemaVersion: typeof MODULE_GEOMETRY_SCHEMA_VERSION;
  readonly dimensions: GeometryDimensions;
  readonly structuralEnvelope: Aabb3;
  readonly renderEnvelope: Aabb3;
  readonly geometry: readonly GeometryPrimitive[];
  readonly applianceSlots: readonly ApplianceSlot[];
}

export interface EnvironmentGeometry extends SceneEntityBase {
  readonly kind: "environment";
  readonly schemaVersion: typeof ENVIRONMENT_GEOMETRY_SCHEMA_VERSION;
  readonly structuralEnvelope: Aabb3;
  readonly geometry: readonly GeometryPrimitive[];
}

export interface SourceBinding {
  readonly schemaVersion: typeof SOURCE_BINDING_SCHEMA_VERSION;
  readonly id: string;
  readonly sourceFingerprint: string;
  readonly sourceSelector: { readonly layer?: string; readonly entityType?: "3DFACE" | "LINE"; };
  readonly targetEntityId: string;
  readonly targetRole: string;
}

export interface FixedPerspectiveCamera {
  readonly id: string;
  readonly mode: "fixed";
  readonly projection: "perspective";
  readonly positionMm: Vec3;
  readonly targetMm: Vec3;
  readonly up: Vec3;
  readonly fovYDeg: number;
  readonly principalPointNormalized: readonly [number, number];
  readonly nearMm: number;
  readonly farMm: number;
  readonly status: "provided" | "calibrated" | "preview";
  readonly evidenceRefs: readonly string[];
}

export interface PresentationFrame {
  readonly preferredAspectRatio: number;
  readonly fit: "contain" | "cover";
  readonly cropAllowed: boolean;
  readonly safeAreaNormalized: readonly [number, number, number, number];
}

export interface ScenePackage {
  readonly schemaVersion: typeof SCENE_PACKAGE_SCHEMA_VERSION;
  readonly sceneId: string;
  readonly coordinateSystem: CoordinateSystem;
  readonly camera: FixedPerspectiveCamera;
  readonly presentationFrame?: PresentationFrame;
  readonly environment: readonly EnvironmentGeometry[];
  readonly items: readonly SceneItem[];
  readonly modules: readonly ModuleGeometry[];
  readonly sourceBindings: readonly SourceBinding[];
}

export function identityTransform(): RigidTransform {
  return { translationMm: { x: 0, y: 0, z: 0 }, rotation: { x: 0, y: 0, z: 0, w: 1 } };
}
