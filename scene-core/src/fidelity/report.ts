import type { ScenePackage } from "../contracts/model.js";
import { currentFixedCamera } from "../fixtures/current-camera.js";
import { module02, module06 } from "../fixtures/current-geometry.js";
import { module03WithSink } from "../fixtures/current-context.js";
import { currentHardwareAnchors } from "../fixtures/current-hardware.js";
import { currentSceneBase } from "../fixtures/current-scene.js";
import {
  CURRENT_FIDELITY_SUPERSAMPLE,
  CURRENT_FIDELITY_VIEWPORT
} from "../fixtures/current-fidelity.js";
import { resolveHardwareAnchors } from "../hardware/anchors.js";
import { createScreenMetricProfile, projectMetricSegment } from "./projection.js";

export type FidelityTier = "F0" | "F1" | "F2" | "F3" | "F4" | "F5" | "F6";
export type FidelityGate = "hard" | "soft" | "human";
export type FidelityCheckStatus = "pass" | "fail" | "pending" | "info";

export interface FidelityCheck {
  readonly id: string;
  readonly tier: FidelityTier;
  readonly gate: FidelityGate;
  readonly status: FidelityCheckStatus;
  readonly expected?: unknown;
  readonly observed?: unknown;
  readonly tolerance?: number;
  readonly unit?: "mm" | "px" | "count" | "boolean";
  readonly note?: string;
}

export interface FidelityReport {
  readonly schemaVersion: "FidelityReport 1.0";
  readonly sceneId: string;
  readonly cameraId: string;
  readonly canonicalViewportPx: readonly [number, number];
  readonly supersampleFactor: 1 | 4 | 8;
  readonly hardGatesPass: boolean;
  readonly checks: readonly FidelityCheck[];
}

const hasEntity = (scene: ScenePackage, id: string): boolean =>
  [...scene.environment, ...scene.items, ...scene.modules].some(entity => entity.id === id);

const check = (
  id: string,
  tier: FidelityTier,
  gate: FidelityGate,
  status: FidelityCheckStatus,
  extra: Omit<FidelityCheck, "id" | "tier" | "gate" | "status"> = {}
): FidelityCheck => ({ id, tier, gate, status, ...extra });

export function buildCurrentFidelityReport(scene: ScenePackage = currentSceneBase): FidelityReport {
  const checks: FidelityCheck[] = [];

  const requiredEntities = [
    "scene/traditional/module/upper-laundry",
    "scene/traditional/fixture/laundry-tank",
    "scene/traditional/appliance/freestanding-range"
  ] as const;
  for (const entityId of requiredEntities) {
    const present = hasEntity(scene, entityId);
    checks.push(check(`required-entity:${entityId}`, "F0", "hard", present ? "pass" : "fail", { expected: true, observed: present, unit: "boolean" }));
  }

  const m02 = scene.modules.find(module => module.id === module02.id);
  const m03 = scene.modules.find(module => module.id === module03WithSink.id);
  if (m02 && m03) {
    const width02 = m02.dimensions.geometryMm.width;
    const width03 = m03.dimensions.geometryMm.width;
    const end02 = m02.transform.translationMm.x + width02;
    const start03 = m03.transform.translationMm.x;
    const span = width02 + width03;
    checks.push(check("metric:module02-width", "F1", "hard", Math.abs(width02 - 791.01) <= 1e-6 ? "pass" : "fail", { expected: 791.01, observed: width02, tolerance: 1e-6, unit: "mm" }));
    checks.push(check("metric:module03-width", "F1", "hard", Math.abs(width03 - 1216.678) <= 1e-6 ? "pass" : "fail", { expected: 1216.678, observed: width03, tolerance: 1e-6, unit: "mm" }));
    checks.push(check("metric:module02-module03-adjacency", "F1", "hard", Math.abs(end02 - start03) <= 1e-6 ? "pass" : "fail", { expected: start03, observed: end02, tolerance: 1e-6, unit: "mm" }));
    checks.push(check("metric:module02-plus-module03-span", "F1", "hard", Math.abs(span - 2007.688) <= 1e-6 ? "pass" : "fail", { expected: 2007.688, observed: span, tolerance: 1e-6, unit: "mm" }));
  } else {
    checks.push(check("metric:module02-plus-module03-availability", "F1", "hard", "fail", { expected: true, observed: false, unit: "boolean" }));
  }

  const module03Fronts = m03?.geometry.filter(primitive => primitive.role === "front").length ?? 0;
  const m06 = scene.modules.find(module => module.id === module06.id);
  const module06Fronts = m06?.geometry.filter(primitive => primitive.role === "front").length ?? 0;
  checks.push(check("topology:module03-front-count", "F2", "hard", module03Fronts === 6 ? "pass" : "fail", { expected: 6, observed: module03Fronts, unit: "count" }));
  checks.push(check("topology:module06-front-count", "F2", "hard", module06Fronts === 3 ? "pass" : "fail", { expected: 3, observed: module06Fronts, unit: "count" }));

  const ovenSlot = m02?.applianceSlots.find(slot => slot.role === "built-in-oven");
  const hasRequiredSurroundParts = m02
    ? ["left-side", "right-side", "bottom", "top-front-rail"].every(suffix => m02.geometry.some(primitive => primitive.id.endsWith(`/${suffix}`)))
    : false;
  const surround = ovenSlot && m02 ? {
    left: ovenSlot.localTransform.translationMm.x,
    right: m02.dimensions.geometryMm.width - (ovenSlot.localTransform.translationMm.x + ovenSlot.clearSizeMm.width),
    bottom: ovenSlot.localTransform.translationMm.z,
    top: m02.dimensions.geometryMm.height - (ovenSlot.localTransform.translationMm.z + ovenSlot.clearSizeMm.height)
  } : null;
  const surroundOk = hasRequiredSurroundParts && surround !== null && Object.values(surround).every(value => Math.abs(value - 18) <= 1e-6);
  checks.push(check(
    "topology:module02-oven-surround",
    "F2",
    "hard",
    surroundOk ? "pass" : "fail",
    {
      expected: { left: 18, right: 18, bottom: 18, top: 18, structuralPartsPresent: true },
      observed: surround ? { ...surround, structuralPartsPresent: hasRequiredSurroundParts } : null,
      unit: "mm",
      note: "The MDF surround is structurally present; its poor baseline reading is an F5 render/readability problem, not missing front filler geometry."
    }
  ));

  const profile = createScreenMetricProfile(CURRENT_FIDELITY_VIEWPORT, CURRENT_FIDELITY_SUPERSAMPLE);
  const projectedSpan = projectMetricSegment(
    currentFixedCamera,
    profile,
    { x: 3071.739, y: 8102.44, z: 100 },
    { x: 5079.427, y: 8102.44, z: 100 }
  );
  const expectedSpanPx = 595.6223325672106;
  checks.push(check("projection:module02-plus-module03-span", "F3", "hard", Math.abs(projectedSpan.canonicalLengthPx - expectedSpanPx) <= 0.01 ? "pass" : "fail", { expected: expectedSpanPx, observed: projectedSpan.canonicalLengthPx, tolerance: 0.01, unit: "px" }));

  try {
    const anchors = resolveHardwareAnchors(scene, currentHardwareAnchors);
    checks.push(check("hardware:anchors-defined", "F4", "hard", anchors.length === currentHardwareAnchors.length ? "pass" : "fail", {
      expected: currentHardwareAnchors.length,
      observed: anchors.length,
      unit: "count",
      note: "V7 handle semantics were ported as centered/edge-offset rules; current values remain evidence-status inferred until visually/physically confirmed."
    }));
  } catch (error) {
    checks.push(check("hardware:anchors-defined", "F4", "hard", "fail", { expected: currentHardwareAnchors.length, observed: 0, unit: "count", note: error instanceof Error ? error.message : String(error) }));
  }

  checks.push(check("readability:module02-oven-surround", "F5", "soft", "pending", { note: "Geometry passes F2; measure projected local contrast/edge recall around the 18 mm surround." }));
  checks.push(check("readability:semantic-edge-baseline", "F5", "soft", "pending", { note: "Quantitative edge readability follows the 4x overlay artifact." }));
  checks.push(check("appearance:human-gate", "F6", "human", "info", { note: "R-07 was rejected as visually sufficient; style anchor remains non-golden." }));

  checks.sort((a, b) => `${a.tier}:${a.id}`.localeCompare(`${b.tier}:${b.id}`));
  const hardGatesPass = checks.filter(candidate => candidate.gate === "hard").every(candidate => candidate.status === "pass");

  return {
    schemaVersion: "FidelityReport 1.0",
    sceneId: scene.sceneId,
    cameraId: scene.camera.id,
    canonicalViewportPx: [CURRENT_FIDELITY_VIEWPORT.widthPx, CURRENT_FIDELITY_VIEWPORT.heightPx],
    supersampleFactor: CURRENT_FIDELITY_SUPERSAMPLE,
    hardGatesPass,
    checks
  };
}

export function compareFidelityReports(baseline: FidelityReport, candidate: FidelityReport): readonly FidelityCheck[] {
  const baselineById = new Map(baseline.checks.map(item => [item.id, item] as const));
  const regressions: FidelityCheck[] = [];
  for (const item of candidate.checks) {
    const previous = baselineById.get(item.id);
    if (!previous) continue;
    if (previous.gate === "hard" && previous.status === "pass" && item.status !== "pass") regressions.push(item);
  }
  return regressions.sort((a, b) => a.id.localeCompare(b.id));
}
