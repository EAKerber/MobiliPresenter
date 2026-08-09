import type { Vec3 } from "../core/math.js";
import { currentFixedCamera } from "../fixtures/current-camera.js";
import { CURRENT_FIDELITY_SUPERSAMPLE, CURRENT_FIDELITY_VIEWPORT } from "../fixtures/current-fidelity.js";
import { createScreenMetricProfile, projectMetricSegment } from "./projection.js";

export interface ReadabilityProbe {
  readonly id: string;
  readonly role: "front-seam" | "oven-surround" | "module-boundary";
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
    id: "module02/oven-surround-left", role: "oven-surround",
    aMm: { x: 3089.739, y: 8120.44, z: 117 }, bMm: { x: 3089.739, y: 8120.44, z: 841 },
    searchBandCanonicalPx: 4, contrastThreshold: 0.02,
    evidenceRefs: ["scene-core:module02-oven-slot"]
  },
  {
    id: "module02/oven-surround-right", role: "oven-surround",
    aMm: { x: 3844.749, y: 8120.44, z: 117 }, bMm: { x: 3844.749, y: 8120.44, z: 841 },
    searchBandCanonicalPx: 4, contrastThreshold: 0.02,
    evidenceRefs: ["scene-core:module02-oven-slot"]
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
