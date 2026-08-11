import type { DimensionEvidence, DimensionTripleMm } from "@mobilipresenter/scene-core";

export const TECHNICAL_CATALOG_ENTRY_SCHEMA_VERSION = "TechnicalCatalogEntry 0.1.0" as const;
export const TECHNICAL_PRESENTATION_PACKAGE_SCHEMA_VERSION = "TechnicalPresentationPackage 0.1.0" as const;

export type TechnicalTargetKind = "module" | "item";
export type TechnicalAxis = "width" | "height" | "depth";
export type TechnicalViewPlane = "width-height" | "depth-height" | "width-depth";
export type TechnicalViewKind = "orthographic" | "internal" | "isometric" | "detail";
export type TechnicalNoticeSeverity = "info" | "important" | "warning";
export type TechnicalDependencyRelation = "requires-present" | "control-point-host" | "technical-support";
export type TechnicalControlKind = "visibility" | "activation";
export type FinishOptionFamily = "front-preset" | "stone-preset";
export type TechnicalComponentKind = "hardware" | "electrical" | "panel" | "interface" | "other";
export type TechnicalFactStatus = "provided" | "confirmed" | "unverified";

export interface TechnicalSourceRef {
  readonly authority: "scene-core" | "technical-catalog" | "appearance-catalog" | "viewer-runtime" | "derived";
  readonly reference: string;
  readonly status: TechnicalFactStatus;
}

export interface TechnicalIdentity {
  readonly alias: string;
  readonly title: string;
  readonly category: string;
  readonly shortLabel?: string;
}

export interface TechnicalDimensionPresentation {
  readonly order: readonly TechnicalAxis[];
  readonly labels: Readonly<Partial<Record<TechnicalAxis, string>>>;
  readonly prefer: "nominal" | "geometry";
}

export interface TechnicalTextFact {
  readonly id: string;
  readonly category: "function" | "construction" | "installation" | "finish" | "hardware" | "electrical";
  readonly text: string;
  readonly source: TechnicalSourceRef;
}

export interface TechnicalComponentRequirement {
  readonly id: string;
  readonly kind: TechnicalComponentKind;
  readonly label: string;
  readonly specification?: string;
  readonly quantity?: number;
  readonly unit?: string;
  readonly linkedEntityId?: string;
  readonly source: TechnicalSourceRef;
}

export interface TechnicalNotice {
  readonly id: string;
  readonly severity: TechnicalNoticeSeverity;
  readonly title?: string;
  readonly text: string;
  readonly source: TechnicalSourceRef;
}

export interface TechnicalDependencySpec {
  readonly relation: TechnicalDependencyRelation;
  readonly targetEntityId: string;
  readonly label: string;
  readonly source: TechnicalSourceRef;
}

export interface TechnicalControlCapability {
  readonly kind: TechnicalControlKind;
  readonly label: string;
  readonly binding: "viewer-visibility" | "feature-enabled";
  readonly implementationStatus: "bound" | "declared-not-bound";
  readonly defaultEnabled?: boolean;
}

export interface FinishPolicy {
  readonly id: string;
  readonly label: string;
  readonly targetEntityId: string;
  readonly materialSlot: string;
  readonly optionFamily: FinishOptionFamily;
  readonly allowedOptionIds: readonly string[];
}

export interface InternalLayoutSegment {
  readonly label: string;
  readonly spanMm: number;
}

export interface InternalLayoutSpec {
  readonly axis: "width" | "height";
  readonly segments: readonly InternalLayoutSegment[];
  readonly subdivisions?: readonly {
    readonly segmentIndex: number;
    readonly count: number;
    readonly label?: string;
  }[];
  readonly source: TechnicalSourceRef;
}

export interface TechnicalViewRequest {
  readonly id: string;
  readonly label: string;
  readonly kind: TechnicalViewKind;
  readonly plane?: TechnicalViewPlane;
  readonly dimensionAxes?: readonly TechnicalAxis[];
  readonly internalLayout?: InternalLayoutSpec;
  readonly source: "scene-envelope" | "scene-geometry" | "authored-internal-layout" | "external-contract";
}

export interface TechnicalCatalogEntry {
  readonly schemaVersion: typeof TECHNICAL_CATALOG_ENTRY_SCHEMA_VERSION;
  readonly id: string;
  readonly target: { readonly kind: TechnicalTargetKind; readonly entityId: string };
  readonly identity: TechnicalIdentity;
  readonly dimensions?: TechnicalDimensionPresentation;
  readonly specifications: readonly TechnicalTextFact[];
  readonly components: readonly TechnicalComponentRequirement[];
  readonly notices: readonly TechnicalNotice[];
  readonly dependencies: readonly TechnicalDependencySpec[];
  readonly controls: readonly TechnicalControlCapability[];
  readonly finishes: readonly FinishPolicy[];
  readonly technicalViews: readonly TechnicalViewRequest[];
  readonly sourceRefs: readonly TechnicalSourceRef[];
}

export interface CompiledTechnicalDimensions {
  readonly primaryKind: "nominal" | "geometry";
  readonly primaryMm: DimensionTripleMm;
  readonly nominalMm?: DimensionTripleMm;
  readonly geometryMm: DimensionTripleMm;
  readonly order: readonly TechnicalAxis[];
  readonly labels: Readonly<Partial<Record<TechnicalAxis, string>>>;
  readonly evidence: readonly DimensionEvidence[];
}

export interface CompiledFinishOption {
  readonly id: string;
  readonly label: string;
  readonly materialId: string;
}

export interface CompiledFinishPolicy extends FinishPolicy {
  readonly options: readonly CompiledFinishOption[];
  readonly currentOptionId: string | null;
  readonly resolvedMaterialId: string;
}

export interface CompiledTechnicalDependency extends TechnicalDependencySpec {
  readonly targetKind: "environment" | "module" | "appliance" | "fixture" | "accessory";
  readonly effectiveVisible: boolean;
}

export interface TechnicalPresentationPackage {
  readonly schemaVersion: typeof TECHNICAL_PRESENTATION_PACKAGE_SCHEMA_VERSION;
  readonly target: TechnicalCatalogEntry["target"];
  readonly identity: TechnicalIdentity;
  readonly dimensions: CompiledTechnicalDimensions | null;
  readonly specifications: readonly TechnicalTextFact[];
  readonly components: readonly TechnicalComponentRequirement[];
  readonly notices: readonly TechnicalNotice[];
  readonly dependencies: readonly CompiledTechnicalDependency[];
  readonly availability: { readonly available: boolean; readonly blockingDependencyIds: readonly string[] };
  readonly controls: readonly TechnicalControlCapability[];
  readonly finishes: readonly CompiledFinishPolicy[];
  readonly technicalViews: readonly TechnicalViewRequest[];
  readonly sourceRefs: readonly TechnicalSourceRef[];
  readonly provenance: {
    readonly physicalAuthority: "scene-core";
    readonly authoredAuthority: "technical-catalog";
    readonly appearanceAuthority: "appearance-catalog";
    readonly runtimeAuthority: "viewer-runtime";
  };
}
