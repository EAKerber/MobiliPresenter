import type {
  TechnicalProjectedEdge,
  TechnicalProjectedEdgeClass
} from "./contracts.js";

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
  readonly physicalEdgeCount: number;
  readonly renderedEdgeCount: number;
  readonly renderedEdges: readonly TechnicalRenderableEdge[];
  readonly candidates: readonly TechnicalLineCandidate[];
  readonly omittedEdgeIds: readonly string[];
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

export function buildTechnicalLineModel(
  physicalEdges: readonly TechnicalProjectedEdge[]
): TechnicalLineModel {
  const candidates = physicalEdges.map(classifyCandidate);
  const renderedEdges = candidates
    .filter((candidate): candidate is Extract<TechnicalLineCandidate, { disposition: "draw" }> =>
      candidate.disposition === "draw"
    )
    .map(candidate => candidate.edge);
  const omittedEdgeIds = candidates
    .filter(candidate => candidate.disposition === "omit")
    .map(candidate => candidate.edge.id);

  return {
    contractVersion: TECHNICAL_LINE_MODEL_VERSION,
    physicalEdgeCount: physicalEdges.length,
    renderedEdgeCount: renderedEdges.length,
    renderedEdges,
    candidates,
    omittedEdgeIds
  };
}
