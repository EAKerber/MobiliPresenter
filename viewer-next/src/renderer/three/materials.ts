import type { AppearancePackage, MaterialDefinition } from "@mobilipresenter/scene-core";
import { resolveMaterial, resolveMaterialId } from "@mobilipresenter/scene-core";
import {
  DoubleSide,
  FrontSide,
  Material,
  Mesh,
  MeshPhysicalMaterial,
  MeshStandardMaterial
} from "three";
import type { ThreeSceneAdapter } from "./scene-adapter.js";

export type PbrMaterial = MeshStandardMaterial | MeshPhysicalMaterial;

function createThreeMaterial(definition: MaterialDefinition): PbrMaterial {
  const physical = definition.transmission > 0 || definition.opacity < 1;
  const common = {
    color: definition.baseColorSrgb,
    roughness: definition.roughness,
    metalness: definition.metallic,
    transparent: definition.opacity < 1 || definition.transmission > 0,
    opacity: definition.opacity,
    depthWrite: !(definition.transmission > 0 || definition.opacity < 0.5),
    side: definition.transmission > 0 ? DoubleSide : FrontSide
  };

  const material = physical
    ? new MeshPhysicalMaterial({
        ...common,
        transmission: definition.transmission,
        thickness: definition.transmission > 0 ? 6 : 0,
        ior: definition.transmission > 0 ? 1.5 : 1.45,
        envMapIntensity: 1
      })
    : new MeshStandardMaterial({
        ...common,
        envMapIntensity: 1
      });

  material.name = definition.id;
  if (definition.emissiveSrgb) {
    material.emissive.set(definition.emissiveSrgb);
    material.emissiveIntensity = definition.emissiveIntensity ?? 1;
  }
  material.userData.materialDefinitionId = definition.id;
  material.userData.mappingPolicy = definition.mappingPolicy;
  if (definition.physicalTextureScaleMm) {
    material.userData.physicalTextureScaleMm = [...definition.physicalTextureScaleMm];
  }
  if (definition.grainDirection) material.userData.grainDirection = definition.grainDirection;
  return material;
}

export class ThreeMaterialRegistry {
  readonly #appearance: AppearancePackage;
  readonly #cache = new Map<string, PbrMaterial>();

  constructor(appearance: AppearancePackage) {
    this.#appearance = appearance;
  }

  resolve(entityId: string, materialSlot: string): PbrMaterial {
    const id = resolveMaterialId(this.#appearance, entityId, materialSlot);
    const cached = this.#cache.get(id);
    if (cached) return cached;
    const definition = resolveMaterial(this.#appearance, entityId, materialSlot);
    const material = createThreeMaterial(definition);
    this.#cache.set(id, material);
    return material;
  }

  materialByDefinitionId(id: string): PbrMaterial {
    const cached = this.#cache.get(id);
    if (cached) return cached;
    const definition = this.#appearance.materials.find(material => material.id === id);
    if (!definition) throw new Error(`MATERIAL_NOT_FOUND:${id}`);
    const material = createThreeMaterial(definition);
    this.#cache.set(id, material);
    return material;
  }

  dispose(): void {
    for (const material of this.#cache.values()) material.dispose();
    this.#cache.clear();
  }
}

export function syncThreeMaterials(
  adapter: ThreeSceneAdapter,
  appearance: AppearancePackage,
  registry = new ThreeMaterialRegistry(appearance)
): ThreeMaterialRegistry {
  for (const [entityId, group] of adapter.entityGroups) {
    group.traverse(object => {
      if (!(object instanceof Mesh)) return;
      const slot = object.userData.materialSlot;
      if (typeof slot !== "string") return;
      const next = registry.resolve(entityId, slot);
      object.material = next as Material;
    });
  }
  return registry;
}
