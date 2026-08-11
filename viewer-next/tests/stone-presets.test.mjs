import assert from "node:assert/strict";
import test from "node:test";
import {
  STONE02_ID,
  STONE03_ID,
  currentAppearance,
  currentSceneBase,
  resolveMaterialId,
  sceneGeometryDigest
} from "@mobilipresenter/scene-core";
import { MeshStandardMaterial } from "three";
import {
  DEFAULT_STONE_PRESET_ID,
  STONE_PRESET_IDS,
  STONE_PRESETS,
  withStonePreset
} from "../dist-ts/src/fixtures/stone-presets.js";
import { ThreeMaterialRegistry } from "../dist-ts/src/renderer/three/materials.js";

function appearanceFor(id) {
  return withStonePreset(currentAppearance, id);
}

test("stone catalog exposes exactly three stable presets with light as default", () => {
  assert.deepEqual(STONE_PRESET_IDS, [
    "light-speckled",
    "warm-beige-speckled",
    "graphite-speckled"
  ]);
  assert.equal(DEFAULT_STONE_PRESET_ID, "light-speckled");
  assert.equal(STONE_PRESETS["light-speckled"].label, "Claro salpicado");
  assert.equal(STONE_PRESETS["warm-beige-speckled"].label, "Bege quente salpicado");
  assert.equal(STONE_PRESETS["graphite-speckled"].label, "Grafite salpicado");
});

test("each preset assigns the same material to stone-02 and stone-03 without touching geometry", () => {
  const before = sceneGeometryDigest(currentSceneBase);
  for (const id of STONE_PRESET_IDS) {
    const appearance = appearanceFor(id);
    const expectedMaterial = STONE_PRESETS[id].materialId;
    assert.equal(resolveMaterialId(appearance, STONE02_ID, "stone"), expectedMaterial);
    assert.equal(resolveMaterialId(appearance, STONE03_ID, "stone"), expectedMaterial);
    assert.equal(sceneGeometryDigest(currentSceneBase), before);
  }
});

test("stone preset material installs deterministic world-space millimeter speckle", () => {
  const appearance = appearanceFor("light-speckled");
  const registry = new ThreeMaterialRegistry(appearance);
  const stone02 = registry.resolve(STONE02_ID, "stone");
  const stone03 = registry.resolve(STONE03_ID, "stone");
  assert.equal(stone02, stone03);
  assert.ok(stone02 instanceof MeshStandardMaterial);
  assert.equal(stone02.name, "stone-speckled-light");
  assert.equal(stone02.userData.mappingPolicy, "world-continuous");
  assert.deepEqual(stone02.userData.physicalTextureScaleMm, [600, 600]);
  assert.deepEqual(stone02.userData.proceduralStoneSpeckle, {
    version: "world-mm-v1",
    worldSpaceMm: true,
    macroScaleMm: 600,
    coarseCellMm: 20,
    fineCellMm: 5,
    seed: 37.137
  });
  assert.equal(stone02.customProgramCacheKey(), "mobilipresenter:world-mm-v1:stone-speckled-light");
  registry.dispose();
});

test("stone shader injects world-position mapping and keeps pattern phase independent of entity id", () => {
  const registry = new ThreeMaterialRegistry(appearanceFor("graphite-speckled"));
  const stone = registry.resolve(STONE02_ID, "stone");
  const shader = {
    vertexShader: "void main() {\n#include <worldpos_vertex>\n}",
    fragmentShader: "void main() {\nvec4 diffuseColor = vec4(1.0);\n#include <color_fragment>\n}",
    uniforms: {}
  };
  stone.onBeforeCompile(shader, {});
  assert.match(shader.vertexShader, /vMpWorldPosition = worldPosition\.xyz/);
  assert.match(shader.fragmentShader, /mpStoneHash/);
  assert.match(shader.fragmentShader, /vMpWorldPosition \/ 20\.000000/);
  assert.match(shader.fragmentShader, /vMpWorldPosition \/ 5\.000000/);
  registry.dispose();
});
