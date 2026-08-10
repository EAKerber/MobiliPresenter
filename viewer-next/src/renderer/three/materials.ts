import type { AppearancePackage, MaterialDefinition } from "@mobilipresenter/scene-core";
import { resolveMaterial, resolveMaterialId } from "@mobilipresenter/scene-core";
import {
  Color,
  DoubleSide,
  FrontSide,
  Material,
  Mesh,
  MeshPhysicalMaterial,
  MeshStandardMaterial
} from "three";
import type { ThreeSceneAdapter } from "./scene-adapter.js";

export type PbrMaterial = MeshStandardMaterial | MeshPhysicalMaterial;

const STONE_SPECKLE_PREFIX = "stone-speckled-";
const STONE_SPECKLE_SHADER_VERSION = "world-mm-v1";
const STONE_SPECKLE_SEED = 37.137;

function glslColor(color: Color): string {
  return `vec3(${color.r.toFixed(6)}, ${color.g.toFixed(6)}, ${color.b.toFixed(6)})`;
}

function installWorldSpaceStoneSpeckle(material: PbrMaterial, definition: MaterialDefinition): void {
  if (!definition.id.startsWith(STONE_SPECKLE_PREFIX)) return;
  const macroScaleMm = definition.physicalTextureScaleMm?.[0] ?? 600;
  const coarseCellMm = macroScaleMm / 30;
  const fineCellMm = macroScaleMm / 120;
  const base = new Color(definition.baseColorSrgb);
  const dark = base.clone().multiplyScalar(0.46);
  const light = base.clone().lerp(new Color(0xffffff), 0.32);

  material.userData.proceduralStoneSpeckle = {
    version: STONE_SPECKLE_SHADER_VERSION,
    worldSpaceMm: true,
    macroScaleMm,
    coarseCellMm,
    fineCellMm,
    seed: STONE_SPECKLE_SEED
  };

  material.onBeforeCompile = shader => {
    const worldToken = "#include <worldpos_vertex>";
    const colorToken = "#include <color_fragment>";
    if (!shader.vertexShader.includes(worldToken) || !shader.fragmentShader.includes(colorToken)) {
      throw new Error(`STONE_SPECKLE_SHADER_HOOK_MISSING:${definition.id}`);
    }

    shader.vertexShader = `varying vec3 vMpWorldPosition;\n${shader.vertexShader}`.replace(
      worldToken,
      `${worldToken}\nvMpWorldPosition = worldPosition.xyz;`
    );

    const fragmentHeader = `
varying vec3 vMpWorldPosition;
float mpStoneHash(vec3 p) {
  p = fract(p * 0.1031);
  p += dot(p, p.yzx + 33.33);
  return fract((p.x + p.y) * p.z);
}
`;
    const speckle = `
vec3 mpCoarseCell = floor(vMpWorldPosition / ${coarseCellMm.toFixed(6)} + ${STONE_SPECKLE_SEED.toFixed(6)});
vec3 mpFineCell = floor(vMpWorldPosition / ${fineCellMm.toFixed(6)} + ${STONE_SPECKLE_SEED.toFixed(6)} * 1.731);
float mpCoarseNoise = mpStoneHash(mpCoarseCell);
float mpFineNoise = mpStoneHash(mpFineCell + 19.17);
float mpDarkMask = smoothstep(0.885, 0.995, mpCoarseNoise) * 0.58;
float mpLightMask = smoothstep(0.925, 0.999, mpFineNoise) * 0.34;
diffuseColor.rgb = mix(diffuseColor.rgb, ${glslColor(dark)}, mpDarkMask);
diffuseColor.rgb = mix(diffuseColor.rgb, ${glslColor(light)}, mpLightMask);
`;
    shader.fragmentShader = fragmentHeader + shader.fragmentShader.replace(
      colorToken,
      `${colorToken}\n${speckle}`
    );
  };
  material.customProgramCacheKey = () => `mobilipresenter:${STONE_SPECKLE_SHADER_VERSION}:${definition.id}`;
  material.needsUpdate = true;
}

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
  installWorldSpaceStoneSpeckle(material, definition);
  return material;
}

function materialDefinitionById(appearance: AppearancePackage, id: string): MaterialDefinition {
  const definition = appearance.materials.find(material => material.id === id);
  if (!definition) throw new Error(`MATERIAL_NOT_FOUND:${id}`);
  return definition;
}

export class ThreeMaterialRegistry {
  #appearance: AppearancePackage;
  readonly #cache = new Map<string, PbrMaterial>();

  constructor(appearance: AppearancePackage) {
    this.#appearance = appearance;
  }

  updateAppearance(next: AppearancePackage): void {
    for (const id of this.#cache.keys()) {
      const before = materialDefinitionById(this.#appearance, id);
      const after = materialDefinitionById(next, id);
      if (JSON.stringify(before) !== JSON.stringify(after)) {
        throw new Error(`MATERIAL_DEFINITION_MUTATION_REQUIRES_REBUILD:${id}`);
      }
    }
    this.#appearance = next;
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
    const definition = materialDefinitionById(this.#appearance, id);
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
  registry.updateAppearance(appearance);
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
