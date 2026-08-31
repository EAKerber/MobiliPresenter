import assert from "node:assert/strict";
import test from "node:test";
import { currentAppearance } from "@mobilipresenter/scene-core";
import { withStonePreset } from "../dist-ts/src/fixtures/stone-presets.js";
import {
  SURFACE_FIDELITY_STONE_SHADER_VERSION,
  SURFACE_FIDELITY_WOOD_SHADER_VERSION,
  ThreeMaterialRegistry,
  WOOD_GRAIN_SHADER_VERSION
} from "../dist-ts/src/renderer/three/materials.js";

function compileProbe(material, { enhanced = false } = {}) {
  const shader = {
    uniforms: {},
    vertexShader: "#include <worldpos_vertex>",
    fragmentShader: [
      "#include <color_fragment>",
      ...(enhanced ? ["#include <roughnessmap_fragment>", "#include <normal_fragment_maps>"] : [])
    ].join("\n")
  };
  material.onBeforeCompile(shader);
  return shader;
}

test("Surface Fidelity keeps the legacy wood shader when realism is off", () => {
  const registry = new ThreeMaterialRegistry(currentAppearance);
  const wood = registry.materialByDefinitionId("front-wood");
  const metadata = wood.userData.proceduralWoodGrain;

  assert.equal(registry.surfaceFidelityEnabled, false);
  assert.equal(registry.woodGrainShaderVersion, WOOD_GRAIN_SHADER_VERSION);
  assert.equal(metadata.version, WOOD_GRAIN_SHADER_VERSION);
  assert.equal(metadata.surfaceFidelity, false);
  assert.equal(metadata.roughnessAmplitude, 0);
  assert.equal(metadata.microNormalStrength, 0);
  assert.equal(metadata.rasterMaps, false);

  const shader = compileProbe(wood);
  assert.match(shader.fragmentShader, /mpWoodTone/);
  assert.doesNotMatch(shader.fragmentShader, /mpWoodRoughnessDelta/);
  assert.doesNotMatch(shader.fragmentShader, /mpWoodMicroHeight/);
  registry.dispose();
});

test("Surface Fidelity v0.2 makes wood materially expressive without raster maps", () => {
  const registry = new ThreeMaterialRegistry(currentAppearance, { surfaceFidelity: true });
  const wood = registry.materialByDefinitionId("front-wood");
  const metadata = wood.userData.proceduralWoodGrain;

  assert.equal(registry.surfaceFidelityEnabled, true);
  assert.equal(registry.woodGrainShaderVersion, SURFACE_FIDELITY_WOOD_SHADER_VERSION);
  assert.equal(metadata.version, SURFACE_FIDELITY_WOOD_SHADER_VERSION);
  assert.equal(metadata.surfaceFidelity, true);
  assert.ok(metadata.colorAmplitude >= 0.15);
  assert.ok(metadata.roughnessAmplitude > 0);
  assert.ok(metadata.microNormalStrength > 0);
  assert.equal(metadata.rasterMaps, false);
  assert.equal(wood.map, null);
  assert.equal(wood.roughnessMap, null);
  assert.equal(wood.normalMap, null);

  const shader = compileProbe(wood, { enhanced: true });
  assert.match(shader.fragmentShader, /mpWoodMacro/);
  assert.match(shader.fragmentShader, /mpWoodFiber/);
  assert.match(shader.fragmentShader, /mpWoodFine/);
  assert.match(shader.fragmentShader, /mpWoodPore/);
  assert.match(shader.fragmentShader, /mpWoodRoughnessDelta/);
  assert.match(shader.fragmentShader, /roughnessFactor = clamp/);
  assert.match(shader.fragmentShader, /mpWoodMicroHeight/);
  assert.match(shader.fragmentShader, /dFdx\(mpWoodMicroHeight\)/);
  assert.match(shader.fragmentShader, /normal = normalize/);
  assert.match(wood.customProgramCacheKey(), new RegExp(SURFACE_FIDELITY_WOOD_SHADER_VERSION));
  registry.dispose();
});

test("Surface Fidelity adds bounded stone roughness response while preserving world-mm speckle", () => {
  const appearance = withStonePreset(currentAppearance, "light-speckled");
  const registry = new ThreeMaterialRegistry(appearance, { surfaceFidelity: true });
  const stone = registry.materialByDefinitionId("stone-speckled-light");
  const metadata = stone.userData.proceduralStoneSpeckle;

  assert.equal(metadata.version, SURFACE_FIDELITY_STONE_SHADER_VERSION);
  assert.equal(metadata.worldSpaceMm, true);
  assert.equal(metadata.surfaceFidelity, true);
  assert.ok(metadata.roughnessAmplitude > 0);
  assert.equal(metadata.rasterMaps, false);
  assert.equal(stone.map, null);
  assert.equal(stone.roughnessMap, null);
  assert.equal(stone.normalMap, null);

  const shader = compileProbe(stone, { enhanced: true });
  assert.match(shader.fragmentShader, /mpStoneRoughnessDelta/);
  assert.match(shader.fragmentShader, /roughnessFactor = clamp/);
  assert.match(shader.vertexShader, /vMpWorldPosition = worldPosition\.xyz/);
  registry.dispose();
});

test("Surface Fidelity does not reinterpret neutral solid MDF as wood", () => {
  const registry = new ThreeMaterialRegistry(currentAppearance, { surfaceFidelity: true });
  const neutral = registry.materialByDefinitionId("front-primary");

  assert.equal(neutral.userData.surfaceFidelity, true);
  assert.equal(neutral.userData.proceduralWoodGrain, undefined);
  assert.equal(neutral.map, null);
  assert.equal(neutral.normalMap, null);
  registry.dispose();
});
