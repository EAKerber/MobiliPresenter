import type {
  TechnicalPoint2Mm,
  TechnicalProjectedEdge,
  TechnicalProjectedEdgeClass,
  TechnicalVisibilityInterval
} from "./contracts.js";
import { TECHNICAL_VISIBILITY_VERSION } from "./technical-visibility.js";

export const TECHNICAL_LINE_MODEL_VERSION = "technical-line-model/v0.6" as const;

export type TechnicalRenderableEdgeClass = Exclude<
  TechnicalProjectedEdgeClass,
  "back" | "depth"
>;

export type TechnicalRenderableEdge =
  Omit<TechnicalProjectedEdge, "classification"> & {
    readonly classification: TechnicalRenderableEdgeClass;
  };

export type TechnicalLineDrawReason =
  | "silhouette"
  | "front-datum"
  | "shared-boundary"
  | "planar-detail";

export type TechnicalLineOmitReason =
  | "front-thickness-rear"
  | "rear-plane"
  | "non-silhouette-depth";

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

export interface TechnicalLineModel {
  readonly contractVersion: typeof TECHNICAL_LINE_MODEL_VERSION;
  readonly visibilityContractVersion: typeof TECHNICAL_VISIBILITY_VERSION;
  readonly physicalEdgeCount: number;
  readonly renderedEdgeCount: number;
  readonly renderedEdges: readonly TechnicalRenderableEdge[];
  readonly candidates: readonly TechnicalLineCandidate[];
  readonly omittedEdgeIds: readonly string[];
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
    case "front":
      return rendered(edge, "front", "front-datum");
    case "shared":
      return rendered(edge, "shared", "shared-boundary");
    case "internal":
      return edge.sourcePrimitiveRoles.includes("front")
        ? {
            edge,
            disposition: "omit",
            reason: "front-thickness-rear"
          }
        : rendered(edge, "internal", "planar-detail");
    case "back":
      return {
        edge,
        disposition: "omit",
        reason: "rear-plane"
      };
    case "depth":
      return {
        edge,
        disposition: "omit",
        reason: "non-silhouette-depth"
      };
  }
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
  const candidates = physicalEdges.map(classifyCandidate);
  const drawnCandidates = candidates.filter(
    (candidate): candidate is Extract<TechnicalLineCandidate, { disposition: "draw" }> =>
      candidate.disposition === "draw"
  );
  const renderedEdges = drawnCandidates.flatMap(candidate => visibleSegments(candidate.edge));
  const omittedEdgeIds = candidates
    .filter(candidate => candidate.disposition === "omit")
    .map(candidate => candidate.edge.id);
  const occludedEdgeIds = drawnCandidates
    .filter(candidate => normalizedIntervals(candidate.edge).length === 0)
    .map(candidate => candidate.edge.id);
  const clippedEdgeIds = drawnCandidates
    .filter(candidate => {
      const intervals = normalizedIntervals(candidate.edge);
      return intervals.length > 0 && !(intervals.length === 1 && isFullInterval(intervals[0]!));
    })
    .map(candidate => candidate.edge.id);

  return {
    contractVersion: TECHNICAL_LINE_MODEL_VERSION,
    visibilityContractVersion: TECHNICAL_VISIBILITY_VERSION,
    physicalEdgeCount: physicalEdges.length,
    renderedEdgeCount: renderedEdges.length,
    renderedEdges,
    candidates,
    omittedEdgeIds,
    occludedEdgeIds,
    clippedEdgeIds
  };
}
