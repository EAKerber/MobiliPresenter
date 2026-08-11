export const HARDWARE_DEFINITION_SCHEMA_VERSION = "HardwareDefinition 0.1.0" as const;
export const HARDWARE_ANCHOR_SCHEMA_VERSION = "HardwareAnchor 0.1.0" as const;

export type HardwareOrientation = "horizontal" | "vertical";

export type HardwarePlacementPolicy =
  | { readonly type: "absolute-uv-mm"; readonly uMm: number; readonly vMm: number }
  | {
      readonly type: "edge-offset-mm";
      readonly horizontal: { readonly from: "left" | "right"; readonly mm: number };
      readonly vertical: { readonly from: "bottom" | "top"; readonly mm: number };
    }
  | { readonly type: "centered" };

export interface HardwareAnchor {
  readonly schemaVersion: typeof HARDWARE_ANCHOR_SCHEMA_VERSION;
  readonly id: string;
  readonly hostEntityId: string;
  readonly hostGeometryId: string;
  readonly surface: "front";
  readonly placement: HardwarePlacementPolicy;
  readonly normalOffsetMm: number;
  readonly orientation: HardwareOrientation;
  readonly hardwareDefinitionId: string;
  readonly status: "confirmed" | "inferred";
  readonly evidenceRefs: readonly string[];
}

export interface BarHandleDefinition {
  readonly schemaVersion: typeof HARDWARE_DEFINITION_SCHEMA_VERSION;
  readonly id: string;
  readonly family: "bar-handle";
  readonly mountSpacingMm: number;
  readonly barLengthMm: number;
  readonly barWidthMm: number;
  readonly barDepthMm: number;
  readonly standoffDepthMm: number;
  readonly supportWidthMm: number;
}

export interface PointHandleDefinition {
  readonly schemaVersion: typeof HARDWARE_DEFINITION_SCHEMA_VERSION;
  readonly id: string;
  readonly family: "point-handle";
  readonly radiusMm: number;
  readonly depthMm: number;
  readonly frontCap: "flat";
}

export type HardwareDefinition = BarHandleDefinition | PointHandleDefinition;
