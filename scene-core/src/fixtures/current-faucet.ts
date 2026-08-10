import type { RigidTransform } from "../core/math.js";
import { STONE03_ID, STONE_DESIGN_THICKNESS_MM } from "./current-scene.js";

export const FAUCET_ANCHOR_SCHEMA_VERSION = "FaucetAnchor 1.0" as const;
export const CURRENT_FAUCET_ID = "scene/traditional/fixture-anchor/kitchen-faucet" as const;
export const CURRENT_FAUCET_DEFINITION_ID = "FAUCET-HIGH-ARC-01" as const;

export interface FaucetAnchor {
  readonly schemaVersion: typeof FAUCET_ANCHOR_SCHEMA_VERSION;
  readonly id: string;
  readonly definitionId: string;
  readonly hostEntityId: string;
  readonly localTransform: RigidTransform;
  readonly placementStatus: "confirmed" | "inferred";
  readonly evidenceRefs: readonly string[];
}

export const currentFaucetAnchor: FaucetAnchor = {
  schemaVersion: FAUCET_ANCHOR_SCHEMA_VERSION,
  id: CURRENT_FAUCET_ID,
  definitionId: CURRENT_FAUCET_DEFINITION_ID,
  hostEntityId: STONE03_ID,
  localTransform: {
    translationMm: {
      x: 608.3385,
      y: 482.387475,
      z: STONE_DESIGN_THICKNESS_MM
    },
    rotation: { x: 0, y: 0, z: 0, w: 1 }
  },
  placementStatus: "inferred",
  evidenceRefs: [
    "user-reference:realistic-high-arc-faucet-required",
    "design-default:fh06-1:centered-behind-sink",
    "design-default:fh06-1:45mm-from-sink-rear-edge",
    "host:stone-03:deck-top"
  ]
};
