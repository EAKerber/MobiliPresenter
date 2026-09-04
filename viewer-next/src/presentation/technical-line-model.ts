import type {
  TechnicalPoint2Mm,
  TechnicalProjectedEdge,
  TechnicalVisibilityInterval
} from "./contracts.js";
import { TECHNICAL_VISIBILITY_VERSION } from "./technical-visibility.js";

export const TECHNICAL_LINE_MODEL_VERSION = "technical-line-model/v0.6" as const;

/**
 * Render classes are deliberately separate from physical edge semantics.
 * The SVG styling contract can remain stable while topology classification
 * evolves independently.
 */
export type TechnicalRenderableEdgeClass =
  | "shared"
  | "internal"
  | "front"
  | "silhouette";

export type TechnicalRenderableEdge =
  Omit<TechnicalProjectedEdge, "classification"> & {
    readonly classification: TechnicalRenderableEdgeClass;
  };

export type TechnicalLineDrawReason =
  | "silhouette"
  | "visible-crease"
  | "visible-boundary"
  | "shared-boundary";

export type TechnicalLineOmitReason = "back-facing";

export type TechnicalLineCandidate =
  | {
      readonly edge: TechnicalRenderableEdge;
      readonly disposition: "draw";
      readonly reason: TechnicalLineDrawReason;
    }
  | {
      readonly edge: TechnicalProjectedEdge;
      readonly disposition: "omit";
      readonly reason: TechnicalLineOmitReason;
    };

export interface TechnicalLineSelection {
  readonly physicalEdgeCount: number;
  readonly selectedEdgeCount: number;
  readonly selectedEdges: readonly TechnicalRenderableEdge[];
  readonly candidates: readonly TechnicalLineCandidate[];
  readonly omittedEdgeIds: readonly string[];
}

export interface TechnicalLineModel extends TechnicalLineSelection {
  readonly contractVersion: typeof TECHNICAL_LINE_MODEL_VERSION;
  readonly visibilityContractVersion: typeof TECHNICAL_VISIBILITY_VERSION;
  readonly renderedEdgeCount: number;
  readonly renderedEdges: readonly TechnicalRenderableEdge[];
  readonly occludedEdgeIds: readonly string[];
  readonly clippedEdgeIds: readonly string[];
}

function rendered(
  edge: TechnicalProjectedEdge,
  classification: TechnicalRenderableEdgeClass,
  reason: TechnicalLineDrawReason
): TechnicalLineCandidate {
  return {
    edge: { ...edge, classification },
    disposition: "draw",
    reason
  };
}

function classifyCandidate(edge: TechnicalProjectedEdge): TechnicalLineCandidate {
  switch (edge.classification) {
    case "silhouette":
      return rendered(edge, "silhouette", "silhouette");
    case "crease":
      return rendered(edge, "internal", "visible-crease");
    case "boundary":
      return rendered(edge, "front", "visible-boundary");
    case "shared":
      return rendered(edge, "shared", "shared-boundary");
    case "back-facing":
      return {
        edge,
        disposition: "omit",
        reason: "back-facing"
      };
  }
}

export function selectTechnicalLineEdges(
  physicalEdges: readonly TechnicalProjectedEdge[]
): TechnicalLineSelection {
  const candidates = physicalEdges.map(classifyCandidate);
  const selectedEdges = candidates
    .filter(
      (candidate): candidate is Extract<TechnicalLineCandidate, { disposition: "draw" }> =>
        candidate.disposition === "draw"
    )
    .map(candidate => candidate.edge);
  const omittedEdgeIds = candidates
    .filter(candidate => candidate.disposition === "omit")
    .map(candidate => candidate.edge.id);

  return {
    physicalEdgeCount: physicalEdges.length,
    selectedEdgeCount: selectedEdges.length,
    selectedEdges,
    candidates,
    omittedEdgeIds
  };
}

function lerpPoint(
  start: TechnicalPoint2Mm,
  end: TechnicalPoint2Mm,
  t: number
): TechnicalPoint2Mm {
  return {
    horizontalMm: start.horizontalMm + (end.horizontalMm - start.horizontalMm) * t,
    verticalMm: start.verticalMm + (end.verticalMm - start.verticalMm) * t
  };
}

function normalizedIntervals(edge: TechnicalRenderableEdge): readonly TechnicalVisibilityInterval[] {
  const intervals = edge.visibleIntervals ?? [{ startT: 0, endT: 1 }];
  return intervals
    .map(interval => ({
      startT: Math.max(0, Math.min(1, interval.startT)),
      endT: Math.max(0, Math.min(1, interval.endT))
    }))
    .filter(interval => interval.endT - interval.startT > 1e-9);
}

function isFullInterval(interval: TechnicalVisibilityInterval): boolean {
  return Math.abs(interval.startT) <= 1e-9 && Math.abs(interval.endT - 1) <= 1e-9;
}

function visibleSegments(edge: TechnicalRenderableEdge): readonly TechnicalRenderableEdge[] {
  const intervals = normalizedIntervals(edge);
  if (intervals.length === 1 && isFullInterval(intervals[0]!)) return [edge];

  return intervals.map((interval, index) => ({
    ...edge,
    id: `${edge.id}:visible-${index + 1}`,
    startMm: lerpPoint(edge.startMm, edge.endMm, interval.startT),
    endMm: lerpPoint(edge.startMm, edge.endMm, interval.endT),
    startViewDepth: edge.startViewDepth + (edge.endViewDepth - edge.startViewDepth) * interval.startT,
    endViewDepth: edge.startViewDepth + (edge.endViewDepth - edge.startViewDepth) * interval.endT,
    visibleIntervals: [{ startT: 0, endT: 1 }]
  }));
}

export function buildTechnicalLineModel(
  physicalEdges: readonly TechnicalProjectedEdge[]
): TechnicalLineModel {
  const selection = selectTechnicalLineEdges(physicalEdges);
  const renderedEdges = selection.selectedEdges.flatMap(visibleSegments);
  const occludedEdgeIds = selection.selectedEdges
    .filter(edge => normalizedIntervals(edge).length === 0)
    .map(edge => edge.id);
  const clippedEdgeIds = selection.selectedEdges
    .filter(edge => {
      const intervals = normalizedIntervals(edge);
      return intervals.length > 0 && !(intervals.length === 1 && isFullInterval(intervals[0]!));
    })
    .map(edge => edge.id);

  return {
    contractVersion: TECHNICAL_LINE_MODEL_VERSION,
    visibilityContractVersion: TECHNICAL_VISIBILITY_VERSION,
    ...selection,
    renderedEdgeCount: renderedEdges.length,
    renderedEdges,
    occludedEdgeIds,
    clippedEdgeIds
  };
}
