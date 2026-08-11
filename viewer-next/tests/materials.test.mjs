import assert from "node:assert/strict";
import test from "node:test";
import {
  currentAppearance,
  currentSceneBase,
  module03WithSink,
  module06,
  setEntityMaterialOverride
} from "@mobilipresenter/scene-core";
import { Mesh, MeshPhysicalMaterial, MeshStandardMaterial } from "three";
import {
  BRUSHED_METAL_MATERIAL_ID,
  BRUSHED_METAL_RESPONSE,
  BRUSHED_METAL_RESPONSE_VERSION,
  ThreeMaterialRegistry,
  syncThreeMaterials
} from "../dist-ts/src/renderer/three/materials.js";
import { buildThreeScene } from "../dist-ts/src/renderer/three/scene-adapter.js";

function meshForSlot(group, slot) {
  let found;
  group.traverse(object => {
    if (!found && object instanceof Mesh && object.userData.materialSlot === slot) found = object;
  });
  assert.ok(found, `mesh with slot ${slot} not found in ${group.name}`);
  return found;
}

test("opaque MDF stays MeshStandardMaterial while glass and brushed inox use explicit physical response", () => {
  const registry = new ThreeMaterialRegistry(currentAppearance);
  const front = registry.resolve(module03WithSink.id, "front");
  const glass = registry.resolve("scene/traditional/environment/glass-divider", "glass");
  const inox = registry.materialByDefinitionId(BRUSHED_METAL_MATERIAL_ID);

  assert.ok(front instanceof MeshStandardMaterial);
  assert.equal(front instanceof MeshPhysicalMaterial, false);
  assert.equal(front.name, "front-primary");

  assert.ok(glass instanceof MeshPhysicalMaterial);
  assert.equal(glass.transmission, 0.92);
  assert.equal(glass.transparent, true);
  assert.equal(glass.depthWrite, false);

  assert.ok(inox instanceof MeshPhysicalMaterial);
  assert.equal(inox.name, "inox-brushed");
  assert.equal(inox.metalness, 0.9);
  assert.equal(inox.roughness, 0.36);
  assert.equal(inox.anisotropy, BRUSHED_METAL_RESPONSE.anisotropy);
  assert.equal(inox.anisotropyRotation, BRUSHED_METAL_RESPONSE.anisotropyRotationRad);
  assert.equal(inox.anisotropyMap, null);
  assert.equal(inox.userData.grainDirection, "u");
  assert.deepEqual(inox.userData.brushedMetalResponse, {
    version: BRUSHED_METAL_RESPONSE_VERSION,
    grainDirection: "u",
    anisotropy: BRUSHED_METAL_RESPONSE.anisotropy,
    anisotropyRotationRad: BRUSHED_METAL_RESPONSE.anisotropyRotationRad,
    rasterMap: false
  });
  registry.dispose();
});

test("emissive material remains explicit PBR material", () => {
  const registry = new ThreeMaterialRegistry(currentAppearance);
  const emissive = registry.resolve("scene/traditional/accessory/under-cab-led-06", "emissive");
  assert.ok(emissive instanceof MeshStandardMaterial);
  assert.equal(emissive.name, "emissive-warm");
  assert.equal(emissive.emissiveIntensity, 1);
  registry.dispose();
});

test("entity material override changes only targeted module material without recreating geometry", () => {
  const baseRegistry = new ThreeMaterialRegistry(currentAppearance);
  const adapter = buildThreeScene(currentSceneBase, (entityId, slot) => baseRegistry.resolve(entityId, slot));
  const module03Group = adapter.entityGroups.get(module03WithSink.id);
  const module06Group = adapter.entityGroups.get(module06.id);
  assert.ok(module03Group && module06Group);
  const module03Mesh = meshForSlot(module03Group, "front");
  const module06Mesh = meshForSlot(module06Group, "front");
  const module03Geometry = module03Mesh.geometry;
  const module06Geometry = module06Mesh.geometry;
  assert.equal(module03Mesh.material.name, "front-primary");
  assert.equal(module06Mesh.material.name, "front-primary");

  const overriddenAppearance = setEntityMaterialOverride(currentAppearance, module03WithSink.id, "front", "front-wood");
  const overriddenRegistry = syncThreeMaterials(adapter, overriddenAppearance);

  assert.equal(module03Mesh.material.name, "front-wood");
  assert.equal(module06Mesh.material.name, "front-primary");
  assert.equal(module03Mesh.geometry, module03Geometry);
  assert.equal(module06Mesh.geometry, module06Geometry);
  baseRegistry.dispose();
  overriddenRegistry.dispose();
});

test("material mapping metadata survives adapter creation", () => {
  const registry = new ThreeMaterialRegistry(currentAppearance);
  const wood = registry.materialByDefinitionId("front-wood");
  assert.equal(wood.userData.mappingPolicy, "module-continuous");
  assert.deepEqual(wood.userData.physicalTextureScaleMm, [600, 1200]);
  assert.equal(wood.userData.grainDirection, "world-z");
  registry.dispose();
});
