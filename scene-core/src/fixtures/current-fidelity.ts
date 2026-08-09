import type { FidelityLine3 } from "../fidelity/overlay.js";
import {
  createAxesOverlay,
  createDimensionLine,
  createPlanarMetricGrid,
  createSceneAabbs,
  createSceneWireframe
} from "../fidelity/overlay.js";
import { resolveWorldTransforms } from "../state/scene-state.js";
import { currentSceneBase } from "./current-scene.js";

export const CURRENT_FIDELITY_VIEWPORT = { widthPx: 1865, heightPx: 967 } as const;
export const CURRENT_FIDELITY_SUPERSAMPLE = 4 as const;

export function createCurrentFidelityOverlayLines(): readonly FidelityLine3[] {
  const lines: FidelityLine3[] = [];

  lines.push(...createPlanarMetricGrid({
    id: "scene/traditional/fidelity/grid/wall-main",
    originMm: { x: 3071.739, y: 8650.44, z: 0 },
    uAxis: { x: 1, y: 0, z: 0 },
    vAxis: { x: 0, y: 0, z: 1 },
    uLengthMm: 2834.688,
    vLengthMm: 2601.63,
    minorStepMm: 100,
    majorStepMm: 500
  }));

  lines.push(...createPlanarMetricGrid({
    id: "scene/traditional/fidelity/grid/lower-front",
    originMm: { x: 3071.739, y: 8102.44, z: 0 },
    uAxis: { x: 1, y: 0, z: 0 },
    vAxis: { x: 0, y: 0, z: 1 },
    uLengthMm: 2007.688,
    vLengthMm: 1000,
    minorStepMm: 100,
    majorStepMm: 500
  }));

  lines.push(...createPlanarMetricGrid({
    id: "scene/traditional/fidelity/grid/upper-front",
    originMm: { x: 3079.427, y: 8232.44, z: 1600 },
    uAxis: { x: 1, y: 0, z: 0 },
    vAxis: { x: 0, y: 0, z: 1 },
    uLengthMm: 2000,
    vLengthMm: 800,
    minorStepMm: 100,
    majorStepMm: 500
  }));

  lines.push(...createPlanarMetricGrid({
    id: "scene/traditional/fidelity/grid/fridge-front",
    originMm: { x: 5097.427, y: 8040.44, z: 0 },
    uAxis: { x: 1, y: 0, z: 0 },
    vAxis: { x: 0, y: 0, z: 1 },
    uLengthMm: 809,
    vLengthMm: 2400,
    minorStepMm: 100,
    majorStepMm: 500
  }));

  lines.push(...createSceneAabbs(currentSceneBase));
  lines.push(...createSceneWireframe(currentSceneBase));

  const world = resolveWorldTransforms(currentSceneBase);
  for (const module of currentSceneBase.modules) {
    const transform = world.get(module.id);
    if (!transform) throw new Error(`WORLD_TRANSFORM_NOT_FOUND:${module.id}`);
    lines.push(...createAxesOverlay(`${module.id}/axes`, transform, 250, module.id));
  }

  lines.push(createDimensionLine(
    "scene/traditional/fidelity/dimension/module02-plus-module03",
    { x: 3071.739, y: 8102.44, z: 50 },
    { x: 5079.427, y: 8102.44, z: 50 },
    2007.688,
    "scene/traditional/module/lower-stove+lower-sink"
  ));

  return lines;
}
