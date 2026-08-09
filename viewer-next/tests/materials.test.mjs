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
import { ThreeMaterialRegistry, syncThreeMaterials } from "../dist-ts/src/renderer/three/materials.js";
import { buildThreeScene } from "../dist-ts/src/renderer/three/scene-adapter.js";

function meshForSlot(group, slot) {
  let found;
  group.traverse(object => {
    if (!found && object instanceof Mesh && object.userData.materialSlot === slot) found = object;
  });
  assert.ok(found, `mesh with slot ${slot} not found in ${group.name}`);
  return found;
}

test("opaque MDF uses MeshStandardMaterial and glass uses MeshPhysicalMaterial", () => {
  const registry = new ThreeMaterialRegistry(currentAppearance);
  const front = registry.resolve(module03WithSink.id, "front");
  const glass = registry.resolve("scene/traditional/environment/glass-divider", "glass");
  assert.ok(front instanceof MeshStandardMaterial);
  assert.equal(front instanceof MeshPhysicalMaterial, false);
  assert.equal(front.name, "front-primary");
  assert.ok(glass instanceof MeshPhysicalMaterial);
  assert.equal(glass.transmission, 0.92);
  assert.equal(glass.transparent, true);
  assert.equal(glass.depthWrite, false);
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
