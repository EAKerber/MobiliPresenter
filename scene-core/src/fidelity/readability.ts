import type { Vec3 } from "../core/math.js";
import { currentFixedCamera } from "../fixtures/current-camera.js";
import { CURRENT_FIDELITY_SUPERSAMPLE, CURRENT_FIDELITY_VIEWPORT } from "../fixtures/current-fidelity.js";
import { createScreenMetricProfile, projectMetricSegment } from "./projection.js";

export interface ReadabilityProbe {
  readonly id: string;
  readonly role: "front-seam" | "oven-surround" | "module-boundary" | "sink-opening";
  readonly aMm: Vec3;
  readonly bMm: Vec3;
  readonly searchBandCanonicalPx: number;
  readonly contrastThreshold: number;
  readonly evidenceRefs: readonly string[];
}

export interface ProjectedReadabilityProbe extends ReadabilityProbe {
  readonly aPx4x: readonly [number, number];
  readonly bPx4x: readonly [number, number];
  readonly aCanonicalPx: readonly [number, number];
  readonly bCanonicalPx: readonly [number, number];
  readonly searchBandPx4x: number;
}

const OVEN_OPENING_LEFT_X = 3167.244;
const OVEN_OPENING_RIGHT_X = 3767.244;
const OVEN_OPENING_FRONT_Y = 8102.44;
const OVEN_OPENING_BOTTOM_Z = 179;
const OVEN_OPENING_TOP_Z = 779;
const OVEN_OPENING_EVIDENCE = [
  "scene-core:module02-front-opening",
  "design-default:fh06-1:600x600-opening"
] as const;

const SINK_OPENING_X0 = 4294.3722625;
const SINK_OPENING_X1 = 4647.8027375;
const SINK_OPENING_Y0 = 8227.3797875;
const SINK_OPENING_Y1 = 8523.4972125;
const SINK_OPENING_Z = 889;
const SINK_OPENING_EVIDENCE = [
  "scene-core:module03-confirmed-sink-slot",
  "viewer-contract:SINK-UNDERMOUNT-40X34-01",
  "fh06-1-s4:true-rounded-stone-hole"
] as const;

export const currentReadabilityProbes: readonly ReadabilityProbe[] = [
  {
    id: "module03/drawer-seam/1-2", role: "front-seam",
    aMm: { x: 3864.749, y: 8102.44, z: 669 }, bMm: { x: 4260.749, y: 8102.44, z: 669 },
    searchBandCanonicalPx: 3, contrastThreshold: 0.02,
    evidenceRefs: ["scene-core:module03-fronts"]
  },
  {
    id: "module03/drawer-seam/2-3", role: "front-seam",
    aMm: { x: 3864.749, y: 8102.44, z: 480 }, bMm: { x: 4260.749, y: 8102.44, z: 480 },
    searchBandCanonicalPx: 3, contrastThreshold: 0.02,
    evidenceRefs: ["scene-core:module03-fronts"]
  },
  {
    id: "module03/drawer-seam/3-4", role: "front-seam",
    aMm: { x: 3864.749, y: 8102.44, z: 291 }, bMm: { x: 4260.749, y: 8102.44, z: 291 },
    searchBandCanonicalPx: 3, contrastThreshold: 0.02,
    evidenceRefs: ["scene-core:module03-fronts"]
  },
  {
    id: "module03/door-seam", role: "front-seam",
    aMm: { x: 4671.088, y: 8102.44, z: 203 }, bMm: { x: 4671.088, y: 8102.44, z: 757 },
    searchBandCanonicalPx: 3, contrastThreshold: 0.02,
    evidenceRefs: ["scene-core:module03-fronts"]
  },
  {
    id: "module01/door-seam", role: "front-seam",
    aMm: { x: 1950.309, y: 8270.827, z: 1750 }, bMm: { x: 1950.309, y: 8270.827, z: 2350 },
    searchBandCanonicalPx: 3, contrastThreshold: 0.02,
    evidenceRefs: ["promob-dxf:LAYER48,LAYER53"]
  },
  {
    id: "module06/door-left-center-seam", role: "front-seam",
    aMm: { x: 4191.427, y: 8232.44, z: 1650 }, bMm: { x: 4191.427, y: 8232.44, z: 2350 },
    searchBandCanonicalPx: 3, contrastThreshold: 0.02,
    evidenceRefs: ["scene-core:module06-fronts"]
  },
  {
    id: "module02/oven-opening-left", role: "oven-surround",
    aMm: { x: OVEN_OPENING_LEFT_X, y: OVEN_OPENING_FRONT_Y, z: OVEN_OPENING_BOTTOM_Z },
    bMm: { x: OVEN_OPENING_LEFT_X, y: OVEN_OPENING_FRONT_Y, z: OVEN_OPENING_TOP_Z },
    searchBandCanonicalPx: 4, contrastThreshold: 0.02,
    evidenceRefs: OVEN_OPENING_EVIDENCE
  },
  {
    id: "module02/oven-opening-right", role: "oven-surround",
    aMm: { x: OVEN_OPENING_RIGHT_X, y: OVEN_OPENING_FRONT_Y, z: OVEN_OPENING_BOTTOM_Z },
    bMm: { x: OVEN_OPENING_RIGHT_X, y: OVEN_OPENING_FRONT_Y, z: OVEN_OPENING_TOP_Z },
    searchBandCanonicalPx: 4, contrastThreshold: 0.02,
    evidenceRefs: OVEN_OPENING_EVIDENCE
  },
  {
    id: "module02/oven-opening-bottom", role: "oven-surround",
    aMm: { x: OVEN_OPENING_LEFT_X, y: OVEN_OPENING_FRONT_Y, z: OVEN_OPENING_BOTTOM_Z },
    bMm: { x: OVEN_OPENING_RIGHT_X, y: OVEN_OPENING_FRONT_Y, z: OVEN_OPENING_BOTTOM_Z },
    searchBandCanonicalPx: 4, contrastThreshold: 0.02,
    evidenceRefs: OVEN_OPENING_EVIDENCE
  },
  {
    id: "module02/oven-opening-top", role: "oven-surround",
    aMm: { x: OVEN_OPENING_LEFT_X, y: OVEN_OPENING_FRONT_Y, z: OVEN_OPENING_TOP_Z },
    bMm: { x: OVEN_OPENING_RIGHT_X, y: OVEN_OPENING_FRONT_Y, z: OVEN_OPENING_TOP_Z },
    searchBandCanonicalPx: 4, contrastThreshold: 0.02,
    evidenceRefs: OVEN_OPENING_EVIDENCE
  },
  {
    id: "sink/opening/front", role: "sink-opening",
    aMm: { x: SINK_OPENING_X0, y: SINK_OPENING_Y0, z: SINK_OPENING_Z },
    bMm: { x: SINK_OPENING_X1, y: SINK_OPENING_Y0, z: SINK_OPENING_Z },
    searchBandCanonicalPx: 4, contrastThreshold: 0.02,
    evidenceRefs: SINK_OPENING_EVIDENCE
  },
  {
    id: "sink/opening/back", role: "sink-opening",
    aMm: { x: SINK_OPENING_X0, y: SINK_OPENING_Y1, z: SINK_OPENING_Z },
    bMm: { x: SINK_OPENING_X1, y: SINK_OPENING_Y1, z: SINK_OPENING_Z },
    searchBandCanonicalPx: 4, contrastThreshold: 0.02,
    evidenceRefs: SINK_OPENING_EVIDENCE
  },
  {
    id: "sink/opening/left", role: "sink-opening",
    aMm: { x: SINK_OPENING_X0, y: SINK_OPENING_Y0, z: SINK_OPENING_Z },
    bMm: { x: SINK_OPENING_X0, y: SINK_OPENING_Y1, z: SINK_OPENING_Z },
    searchBandCanonicalPx: 4, contrastThreshold: 0.02,
    evidenceRefs: SINK_OPENING_EVIDENCE
  },
  {
    id: "sink/opening/right", role: "sink-opening",
    aMm: { x: SINK_OPENING_X1, y: SINK_OPENING_Y0, z: SINK_OPENING_Z },
    bMm: { x: SINK_OPENING_X1, y: SINK_OPENING_Y1, z: SINK_OPENING_Z },
    searchBandCanonicalPx: 4, contrastThreshold: 0.02,
    evidenceRefs: SINK_OPENING_EVIDENCE
  }
];

export function projectReadabilityProbe(probe: ReadabilityProbe): ProjectedReadabilityProbe {
  const profile = createScreenMetricProfile(CURRENT_FIDELITY_VIEWPORT, CURRENT_FIDELITY_SUPERSAMPLE);
  const projected = projectMetricSegment(currentFixedCamera, profile, probe.aMm, probe.bMm);
  return {
    ...probe,
    aPx4x: [projected.a.xPx, projected.a.yPx],
    bPx4x: [projected.b.xPx, projected.b.yPx],
    aCanonicalPx: [projected.a.canonicalXPx, projected.a.canonicalYPx],
    bCanonicalPx: [projected.b.canonicalXPx, projected.b.canonicalYPx],
    searchBandPx4x: probe.searchBandCanonicalPx * CURRENT_FIDELITY_SUPERSAMPLE
  };
}

export function currentProjectedReadabilityProbes(): readonly ProjectedReadabilityProbe[] {
  return currentReadabilityProbes.map(projectReadabilityProbe);
}
