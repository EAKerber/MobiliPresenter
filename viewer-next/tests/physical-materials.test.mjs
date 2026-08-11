import assert from "node:assert/strict";
import test from "node:test";
import {
  currentSceneBase,
  module02,
  module03WithSink
} from "@mobilipresenter/scene-core";
import { Matrix4, Mesh, MeshStandardMaterial, Vector3 } from "three";
import { styleAnchorAppearance } from "../dist-ts/src/fixtures/style-anchor.js";
import {
  WOOD_GRAIN_MATERIAL_ID,
  WOOD_GRAIN_SHADER_VERSION,
  ThreeMaterialRegistry,
  bindModuleContinuousMaterialMappings
} from "../dist-ts/src/renderer/three/materials.js";
import { buildThreeScene } from "../dist-ts/src/renderer/three/scene-adapter.js";

test("front-wood honors physical scale and world-z grain without raster textures", () => {
  const registry = new ThreeMaterialRegistry(styleAnchorAppearance);
  const material = registry.materialByDefinitionId(WOOD_GRAIN_MATERIAL_ID);
  const metadata = material.userData.proceduralWoodGrain;

  assert.ok(material instanceof MeshStandardMaterial);
  assert.equal(metadata.version, WOOD_GRAIN_SHADER_VERSION);
  assert.equal(metadata.mappingPolicy, "module-continuous");
  assert.equal(metadata.grainDirection, "world-z");
  assert.deepEqual(metadata.physicalScaleMm, [600, 1200]);
  assert.deepEqual(metadata.macroCellMm, [75, 1200 / 1.8]);
  assert.equal(metadata.fiberBandMm, 600 / 52);
  assert.deepEqual(metadata.fineCellMm, [6.25, 240]);
  assert.ok(metadata.colorAmplitude <= 0.05);
  assert.ok(metadata.worldToModule instanceof Matrix4);
  assert.equal(material.map, null);
  assert.equal(material.normalMap, null);
  assert.equal(material.roughnessMap, null);
  assert.match(material.customProgramCacheKey(), /module-mm-world-z-v2:front-wood/);
  registry.dispose();
});

test("wood shader injects deterministic anisotropic noise in metric module/world coordinates", () => {
  const registry = new ThreeMaterialRegistry(styleAnchorAppearance);
  const material = registry.materialByDefinitionId(WOOD_GRAIN_MATERIAL_ID);
  const shader = {
    vertexShader: "void main(){\n#include <worldpos_vertex>\n}",
    fragmentShader: "void main(){\n#include <color_fragment>\n}",
    uniforms: {}
  };
  material.onBeforeCompile(shader);

  assert.ok(shader.uniforms.mpWoodWorldToModule);
  assert.match(shader.vertexShader, /vMpWoodWorldPosition/);
  assert.match(shader.vertexShader, /vMpWoodModulePosition/);
  assert.match(shader.vertexShader, /mpWoodWorldToModule \* worldPosition/);
  assert.match(shader.fragmentShader, /mpWoodHash/);
  assert.match(shader.fragmentShader, /mpWoodNoise/);
  assert.match(shader.fragmentShader, /mpWoodAlongMm = vMpWoodWorldPosition\.y/);
  assert.match(shader.fragmentShader, /mpWoodAcrossMm = vMpWoodModulePosition\.x/);
  assert.match(shader.fragmentShader, /75\.000000/);
  assert.match(shader.fragmentShader, /666\.666667/);
  assert.match(shader.fragmentShader, /11\.538462/);
  assert.match(shader.fragmentShader, /6\.250000/);
  assert.doesNotMatch(shader.fragmentShader, /mpWoodCoarse/);

  const second = {
    vertexShader: "void main(){\n#include <worldpos_vertex>\n}",
    fragmentShader: "void main(){\n#include <color_fragment>\n}",
    uniforms: {}
  };
  material.onBeforeCompile(second);
  assert.equal(shader.vertexShader, second.vertexShader);
  assert.equal(shader.fragmentShader, second.fragmentShader);
  registry.dispose();
});

test("module-continuous binding keeps one shared material while resetting mapping at each module", () => {
  const registry = new ThreeMaterialRegistry(styleAnchorAppearance);
  const adapter = buildThreeScene(currentSceneBase, (entityId, slot) => registry.resolve(entityId, slot));
  const result = bindModuleContinuousMaterialMappings(adapter);
  assert.equal(result.bindingId, "module-continuous-material-mapping-v1");
  assert.ok(result.boundMeshCount >= 10);
  assert.deepEqual(result.moduleIds, [module02.id, module03WithSink.id].sort());

  const wood = registry.materialByDefinitionId(WOOD_GRAIN_MATERIAL_ID);
  const metadata = wood.userData.proceduralWoodGrain;
  const module02Group = adapter.entityGroups.get(module02.id);
  const module03Group = adapter.entityGroups.get(module03WithSink.id);
  assert.ok(module02Group && module03Group);

  const woodMesh02 = [];
  const woodMesh03 = [];
  module02Group.traverse(object => {
    if (object instanceof Mesh && object.material === wood && object.userData.moduleContinuousMaterialOwner === module02.id) woodMesh02.push(object);
  });
  module03Group.traverse(object => {
    if (object instanceof Mesh && object.material === wood && object.userData.moduleContinuousMaterialOwner === module03WithSink.id) woodMesh03.push(object);
  });
  assert.ok(woodMesh02.length > 0);
  assert.ok(woodMesh03.length > 0);

  woodMesh02[0].onBeforeRender();
  const worldOrigin02 = new Vector3(0, 0, 0).applyMatrix4(module02Group.matrixWorld);
  const mapped02 = worldOrigin02.clone().applyMatrix4(metadata.worldToModule);
  assert.ok(mapped02.length() <= 1e-9);

  woodMesh03[0].onBeforeRender();
  const worldOrigin03 = new Vector3(0, 0, 0).applyMatrix4(module03Group.matrixWorld);
  const mapped03 = worldOrigin03.clone().applyMatrix4(metadata.worldToModule);
  assert.ok(mapped03.length() <= 1e-9);
  assert.equal(woodMesh02[0].material, woodMesh03[0].material);

  const second = bindModuleContinuousMaterialMappings(adapter);
  assert.equal(second.boundMeshCount, 0);
  registry.dispose();
});
