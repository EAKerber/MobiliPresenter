import type { DimensionEvidence, DimensionTripleMm } from "@mobilipresenter/scene-core";

export const TECHNICAL_CATALOG_ENTRY_SCHEMA_VERSION = "TechnicalCatalogEntry 0.1.1" as const;
export const TECHNICAL_PRESENTATION_PACKAGE_SCHEMA_VERSION = "TechnicalPresentationPackage 0.1.5" as const;

export type TechnicalTargetKind = "module" | "item";
export type TechnicalAxis = "width" | "height" | "depth";
export type TechnicalViewPlane = "width-height" | "depth-height" | "width-depth";
export type TechnicalViewProjection = TechnicalViewPlane | "isometric";
export type TechnicalViewKind = "orthographic" | "internal" | "isometric" | "detail";
export type TechnicalViewFidelity = "schematic" | "geometry-derived" | "authored";
export type TechnicalViewCoverage =
  | "envelope"
  | "authored-layout"
  | "module-front-primitives"
  | "module-geometry-primitives"
  | "appliance-front-openings";
export type TechnicalViewOmission = "hardware" | "hidden-geometry" | "hidden-line-removal";
export type TechnicalNoticeSeverity = "info" | "important" | "warning";
export type TechnicalDependencyRelation = "requires-present" | "control-point-host" | "technical-support";
export type TechnicalControlKind = "visibility" | "activation";
export type FinishOptionFamily = "front-preset" | "stone-preset";
export type TechnicalComponentKind = "hardware" | "electrical" | "panel" | "interface" | "other";
export type TechnicalFactStatus = "provided" | "confirmed" | "unverified";

/**
 * Camera-relative topology semantics for a physical projected edge.
 *
 * These values say why an edge is or is not a candidate technical line. They
 * intentionally do not encode its world-axis direction and do not claim
 * occlusion. Surface-depth visibility is a later, independent stage.
 */
export type TechnicalProjectedEdgeClass =
  | "silhouette"
  | "crease"
  | "boundary"
  | "shared"
  | "back-facing";

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

export interface TechnicalPresentationSpec {
  readonly primaryEntityId: string;
  readonly companionEntityIds: readonly string[];
}

export interface TechnicalTextFact {
  readonly id: string;
  readonly category: "function" | "construction" | "installation" | "finish" | "hardware" | "electrical";
  readonly text: string;
  readonly semanticKey?: string;
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
  readonly semanticKey?: string;
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

export interface TechnicalPoint2Mm {
  readonly horizontalMm: number;
  readonly verticalMm: number;
}

export interface TechnicalProjectedPrimitive {
  readonly id: string;
  readonly role: string;
  readonly pointsMm: readonly TechnicalPoint2Mm[];
  readonly sourceBindingIds: readonly string[];
}

export interface TechnicalProjectedOpening {
  readonly id: string;
  readonly slotId: string;
  readonly role: string;
  readonly pointsMm: readonly TechnicalPoint2Mm[];
  readonly status: "confirmed" | "inferred";
  readonly evidenceRefs: readonly string[];
}

export interface TechnicalProjectedDimensionGuide {
  readonly axis: TechnicalAxis;
  readonly startMm: TechnicalPoint2Mm;
  readonly endMm: TechnicalPoint2Mm;
}

export interface TechnicalVisibilityInterval {
  readonly startT: number;
  readonly endT: number;
}

export interface TechnicalProjectedEdge {
  readonly id: string;
  readonly classification: TechnicalProjectedEdgeClass;
  readonly startMm: TechnicalPoint2Mm;
  readonly endMm: TechnicalPoint2Mm;
  readonly startViewDepth: number;
  readonly endViewDepth: number;
  /**
   * Present only when this edge was selected as a technical-line candidate and
   * evaluated by the visibility stage. Omitted physical edges remain untouched.
   */
  readonly visibleIntervals?: readonly TechnicalVisibilityInterval[];
  readonly sourcePrimitiveIds: readonly string[];
  readonly sourcePrimitiveRoles: readonly string[];
}

export interface CompiledTechnicalViewGeometry {
  readonly viewId: string;
  readonly projection: TechnicalViewProjection;
  readonly coordinateUnit: "mm";
  readonly boundsMm: {
    readonly horizontal: number;
    readonly vertical: number;
  };
  readonly primitives: readonly TechnicalProjectedPrimitive[];
  readonly openings: readonly TechnicalProjectedOpening[];
  readonly dimensionGuides: readonly TechnicalProjectedDimensionGuide[];
  readonly edges: readonly TechnicalProjectedEdge[];
  readonly coverage: readonly TechnicalViewCoverage[];
  readonly omitted: readonly TechnicalViewOmission[];
}

export interface TechnicalCatalogEntry {
  readonly schemaVersion: typeof TECHNICAL_CATALOG_ENTRY_SCHEMA_VERSION;
  readonly id: string;
  readonly target: { readonly kind: TechnicalTargetKind; readonly entityId: string };
  readonly identity: TechnicalIdentity;
  readonly dimensions?: TechnicalDimensionPresentation;
  readonly presentation?: TechnicalPresentationSpec;
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
  readonly presentation: TechnicalPresentationSpec | null;
  readonly specifications: readonly TechnicalTextFact[];
  readonly components: readonly TechnicalComponentRequirement[];
  readonly notices: readonly TechnicalNotice[];
  readonly dependencies: readonly CompiledTechnicalDependency[];
  readonly availability: { readonly available: boolean; readonly blockingDependencyIds: readonly string[] };
  readonly controls: readonly TechnicalControlCapability[];
  readonly finishes: readonly CompiledFinishPolicy[];
  readonly technicalViews: readonly TechnicalViewRequest[];
  readonly technicalViewGeometry: readonly CompiledTechnicalViewGeometry[];
  readonly sourceRefs: readonly TechnicalSourceRef[];
  readonly provenance: {
    readonly physicalAuthority: "scene-core";
    readonly authoredAuthority: "technical-catalog";
    readonly appearanceAuthority: "appearance-catalog";
    readonly runtimeAuthority: "viewer-runtime";
  };
}
