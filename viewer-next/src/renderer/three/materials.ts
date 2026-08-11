import type { AppearancePackage, MaterialDefinition } from "@mobilipresenter/scene-core";
import { resolveMaterial, resolveMaterialId } from "@mobilipresenter/scene-core";
import {
  Color,
  DoubleSide,
  FrontSide,
  Material,
  Matrix4,
  Mesh,
  MeshPhysicalMaterial,
  MeshStandardMaterial
} from "three";
import type { ThreeSceneAdapter } from "./scene-adapter.js";

export type PbrMaterial = MeshStandardMaterial | MeshPhysicalMaterial;

const STONE_SPECKLE_PREFIX = "stone-speckled-";
const STONE_SPECKLE_SHADER_VERSION = "world-mm-v1";
const STONE_SPECKLE_SEED = 37.137;

export const WOOD_GRAIN_MATERIAL_ID = "front-wood" as const;
export const WOOD_GRAIN_SHADER_VERSION = "module-mm-world-z-v2" as const;
const WOOD_GRAIN_TWO_PI = Math.PI * 2;

interface ProceduralWoodMetadata {
  readonly version: typeof WOOD_GRAIN_SHADER_VERSION;
  readonly mappingPolicy: "module-continuous";
  readonly grainDirection: "world-z";
  readonly physicalScaleMm: readonly [number, number];
  readonly macroCellMm: readonly [number, number];
  readonly fiberBandMm: number;
  readonly fineCellMm: readonly [number, number];
  readonly colorAmplitude: number;
  readonly worldToModule: Matrix4;
}

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

function installModuleContinuousWoodGrain(material: PbrMaterial, definition: MaterialDefinition): void {
  if (definition.id !== WOOD_GRAIN_MATERIAL_ID) return;
  if (definition.mappingPolicy !== "module-continuous") {
    throw new Error(`WOOD_GRAIN_MAPPING_POLICY_INVALID:${definition.mappingPolicy}`);
  }
  if (definition.grainDirection !== "world-z") {
    throw new Error(`WOOD_GRAIN_DIRECTION_INVALID:${definition.grainDirection ?? "missing"}`);
  }
  const physicalScaleMm = definition.physicalTextureScaleMm;
  if (!physicalScaleMm) throw new Error("WOOD_GRAIN_PHYSICAL_SCALE_MISSING");

  const [acrossScaleMm, alongScaleMm] = physicalScaleMm;
  const macroCellMm = [acrossScaleMm / 8, alongScaleMm / 1.8] as const;
  const fiberBandMm = acrossScaleMm / 52;
  const fineCellMm = [acrossScaleMm / 96, alongScaleMm / 5] as const;
  const colorAmplitude = 0.044;
  const worldToModule = new Matrix4();
  const metadata: ProceduralWoodMetadata = {
    version: WOOD_GRAIN_SHADER_VERSION,
    mappingPolicy: "module-continuous",
    grainDirection: "world-z",
    physicalScaleMm: [acrossScaleMm, alongScaleMm],
    macroCellMm,
    fiberBandMm,
    fineCellMm,
    colorAmplitude,
    worldToModule
  };
  material.userData.proceduralWoodGrain = metadata;

  material.onBeforeCompile = shader => {
    const worldToken = "#include <worldpos_vertex>";
    const colorToken = "#include <color_fragment>";
    if (!shader.vertexShader.includes(worldToken) || !shader.fragmentShader.includes(colorToken)) {
      throw new Error(`WOOD_GRAIN_SHADER_HOOK_MISSING:${definition.id}`);
    }

    shader.uniforms.mpWoodWorldToModule = { value: worldToModule };
    shader.vertexShader = `
uniform mat4 mpWoodWorldToModule;
varying vec3 vMpWoodWorldPosition;
varying vec3 vMpWoodModulePosition;
${shader.vertexShader}`.replace(
      worldToken,
      `${worldToken}
vMpWoodWorldPosition = worldPosition.xyz;
vMpWoodModulePosition = (mpWoodWorldToModule * worldPosition).xyz;`
    );

    const fragmentHeader = `
varying vec3 vMpWoodWorldPosition;
varying vec3 vMpWoodModulePosition;
float mpWoodHash(vec2 p) {
  vec3 p3 = fract(p.xyx * vec3(0.1031, 0.1030, 0.0973));
  p3 += dot(p3, p3.yzx + 33.33);
  return fract((p3.x + p3.y) * p3.z);
}
float mpWoodNoise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  return mix(
    mix(mpWoodHash(i), mpWoodHash(i + vec2(1.0, 0.0)), f.x),
    mix(mpWoodHash(i + vec2(0.0, 1.0)), mpWoodHash(i + vec2(1.0, 1.0)), f.x),
    f.y
  );
}
`;
    const grain = `
float mpWoodAlongMm = vMpWoodWorldPosition.y;
float mpWoodAcrossMm = vMpWoodModulePosition.x;
float mpWoodMacro = mpWoodNoise(
  vec2(mpWoodAcrossMm / ${macroCellMm[0].toFixed(6)}, mpWoodAlongMm / ${macroCellMm[1].toFixed(6)}) + vec2(3.17, 11.43)
);
float mpWoodWarp = mpWoodNoise(
  vec2(mpWoodAcrossMm / ${(macroCellMm[0] * 1.7).toFixed(6)}, mpWoodAlongMm / ${(macroCellMm[1] * 0.55).toFixed(6)}) + vec2(19.2, 4.7)
) - 0.5;
float mpWoodFiber = 0.5 + 0.5 * sin(
  (mpWoodAcrossMm / ${fiberBandMm.toFixed(6)} + (mpWoodMacro - 0.5) * 1.35 + mpWoodWarp * 0.85) * ${WOOD_GRAIN_TWO_PI.toFixed(6)}
);
float mpWoodFine = mpWoodNoise(
  vec2(mpWoodAcrossMm / ${fineCellMm[0].toFixed(6)}, mpWoodAlongMm / ${fineCellMm[1].toFixed(6)}) + vec2(41.7, 7.3)
);
float mpWoodTone =
  (mpWoodMacro - 0.5) * 0.055 +
  (mpWoodFiber - 0.5) * 0.020 +
  (mpWoodFine - 0.5) * 0.012;
diffuseColor.rgb = clamp(diffuseColor.rgb * (1.0 + mpWoodTone), 0.0, 1.0);
`;
    shader.fragmentShader = fragmentHeader + shader.fragmentShader.replace(
      colorToken,
      `${colorToken}\n${grain}`
    );
  };
  material.customProgramCacheKey = () => `mobilipresenter:${WOOD_GRAIN_SHADER_VERSION}:${definition.id}`;
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
  installModuleContinuousWoodGrain(material, definition);
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

export interface ModuleContinuousMaterialBindingResult {
  readonly bindingId: "module-continuous-material-mapping-v1";
  readonly boundMeshCount: number;
  readonly moduleIds: readonly string[];
}

export function bindModuleContinuousMaterialMappings(
  adapter: ThreeSceneAdapter
): ModuleContinuousMaterialBindingResult {
  const moduleIds = new Set<string>();
  let boundMeshCount = 0;

  for (const [moduleId, group] of [...adapter.entityGroups.entries()].sort(([a], [b]) => a.localeCompare(b))) {
    if (group.userData.entityKind !== "module") continue;
    group.updateWorldMatrix(true, true);
    const worldToModule = group.matrixWorld.clone().invert();
    group.traverse(object => {
      if (!(object instanceof Mesh)) return;
      if (!(object.material instanceof MeshStandardMaterial || object.material instanceof MeshPhysicalMaterial)) return;
      if (object.material.name !== WOOD_GRAIN_MATERIAL_ID) return;
      const metadata = object.material.userData.proceduralWoodGrain as ProceduralWoodMetadata | undefined;
      if (!metadata || !(metadata.worldToModule instanceof Matrix4)) return;
      if (object.userData.moduleContinuousMaterialMapping === WOOD_GRAIN_SHADER_VERSION) return;

      const prior = object.onBeforeRender;
      object.onBeforeRender = function (...args): void {
        metadata.worldToModule.copy(worldToModule);
        prior.call(this, ...args);
      };
      object.userData.moduleContinuousMaterialMapping = WOOD_GRAIN_SHADER_VERSION;
      object.userData.moduleContinuousMaterialOwner = moduleId;
      boundMeshCount += 1;
      moduleIds.add(moduleId);
    });
  }

  return {
    bindingId: "module-continuous-material-mapping-v1",
    boundMeshCount,
    moduleIds: [...moduleIds].sort()
  };
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
