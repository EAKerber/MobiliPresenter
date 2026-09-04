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
const STONE_SPECKLE_SHADER_VERSION = "world-mm-v1" as const;
export const SURFACE_FIDELITY_STONE_SHADER_VERSION = "world-mm-v2" as const;
const STONE_SPECKLE_SEED = 37.137;

export const WOOD_GRAIN_MATERIAL_ID = "front-wood" as const;
export const WOOD_GRAIN_SHADER_VERSION = "module-mm-world-z-v2" as const;
export const SURFACE_FIDELITY_WOOD_SHADER_VERSION = "module-mm-world-z-v3" as const;
const WOOD_GRAIN_TWO_PI = Math.PI * 2;

export const BRUSHED_METAL_MATERIAL_ID = "inox-brushed" as const;
export const BRUSHED_METAL_RESPONSE_VERSION = "anisotropic-pbr-v1" as const;
export const BRUSHED_METAL_RESPONSE = {
  anisotropy: 0.62,
  anisotropyRotationRad: 0
} as const;

export interface ThreeMaterialRegistryOptions {
  readonly surfaceFidelity?: boolean;
}

type WoodShaderVersion =
  | typeof WOOD_GRAIN_SHADER_VERSION
  | typeof SURFACE_FIDELITY_WOOD_SHADER_VERSION;

interface ProceduralWoodMetadata {
  readonly version: WoodShaderVersion;
  readonly mappingPolicy: "module-continuous";
  readonly grainDirection: "world-z";
  readonly physicalScaleMm: readonly [number, number];
  readonly macroCellMm: readonly [number, number];
  readonly fiberBandMm: number;
  readonly fineCellMm: readonly [number, number];
  readonly colorAmplitude: number;
  readonly roughnessAmplitude: number;
  readonly microNormalStrength: number;
  readonly surfaceFidelity: boolean;
  readonly rasterMaps: false;
  readonly worldToModule: Matrix4;
}

function glslColor(color: Color): string {
  return `vec3(${color.r.toFixed(6)}, ${color.g.toFixed(6)}, ${color.b.toFixed(6)})`;
}

function installWorldSpaceStoneSpeckle(
  material: PbrMaterial,
  definition: MaterialDefinition,
  surfaceFidelity: boolean
): void {
  if (!definition.id.startsWith(STONE_SPECKLE_PREFIX)) return;
  const macroScaleMm = definition.physicalTextureScaleMm?.[0] ?? 600;
  const coarseCellMm = macroScaleMm / 30;
  const fineCellMm = macroScaleMm / 120;
  const base = new Color(definition.baseColorSrgb);
  const dark = base.clone().multiplyScalar(0.46);
  const light = base.clone().lerp(new Color(0xffffff), 0.32);
  const version = surfaceFidelity
    ? SURFACE_FIDELITY_STONE_SHADER_VERSION
    : STONE_SPECKLE_SHADER_VERSION;

  material.userData.proceduralStoneSpeckle = {
    version,
    worldSpaceMm: true,
    macroScaleMm,
    coarseCellMm,
    fineCellMm,
    seed: STONE_SPECKLE_SEED,
    surfaceFidelity,
    roughnessAmplitude: surfaceFidelity ? 0.055 : 0,
    rasterMaps: false
  };

  material.onBeforeCompile = shader => {
    const worldToken = "#include <worldpos_vertex>";
    const colorToken = "#include <color_fragment>";
    const roughnessToken = "#include <roughnessmap_fragment>";
    if (
      !shader.vertexShader.includes(worldToken) ||
      !shader.fragmentShader.includes(colorToken) ||
      (surfaceFidelity && !shader.fragmentShader.includes(roughnessToken))
    ) {
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
    const speckle = surfaceFidelity
      ? `
vec3 mpCoarseCell = floor(vMpWorldPosition / ${coarseCellMm.toFixed(6)} + ${STONE_SPECKLE_SEED.toFixed(6)});
vec3 mpFineCell = floor(vMpWorldPosition / ${fineCellMm.toFixed(6)} + ${STONE_SPECKLE_SEED.toFixed(6)} * 1.731);
float mpCoarseNoise = mpStoneHash(mpCoarseCell);
float mpFineNoise = mpStoneHash(mpFineCell + 19.17);
float mpDarkMask = smoothstep(0.885, 0.995, mpCoarseNoise) * 0.58;
float mpLightMask = smoothstep(0.925, 0.999, mpFineNoise) * 0.34;
float mpStoneRoughnessDelta =
  (mpCoarseNoise - 0.5) * 0.070 +
  (mpFineNoise - 0.5) * 0.040;
diffuseColor.rgb = mix(diffuseColor.rgb, ${glslColor(dark)}, mpDarkMask);
diffuseColor.rgb = mix(diffuseColor.rgb, ${glslColor(light)}, mpLightMask);
`
      : `
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
    if (surfaceFidelity) {
      shader.fragmentShader = shader.fragmentShader.replace(
        roughnessToken,
        `${roughnessToken}
roughnessFactor = clamp(roughnessFactor + mpStoneRoughnessDelta, 0.18, 0.96);`
      );
    }
  };
  material.customProgramCacheKey = () => `mobilipresenter:${version}:${definition.id}`;
  material.needsUpdate = true;
}

function installModuleContinuousWoodGrain(
  material: PbrMaterial,
  definition: MaterialDefinition,
  surfaceFidelity: boolean
): void {
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
  const version = surfaceFidelity
    ? SURFACE_FIDELITY_WOOD_SHADER_VERSION
    : WOOD_GRAIN_SHADER_VERSION;
  const colorAmplitude = surfaceFidelity ? 0.17 : 0.044;
  const roughnessAmplitude = surfaceFidelity ? 0.07 : 0;
  const microNormalStrength = surfaceFidelity ? 0.12 : 0;
  const worldToModule = new Matrix4();
  const metadata: ProceduralWoodMetadata = {
    version,
    mappingPolicy: "module-continuous",
    grainDirection: "world-z",
    physicalScaleMm: [acrossScaleMm, alongScaleMm],
    macroCellMm,
    fiberBandMm,
    fineCellMm,
    colorAmplitude,
    roughnessAmplitude,
    microNormalStrength,
    surfaceFidelity,
    rasterMaps: false,
    worldToModule
  };
  material.userData.proceduralWoodGrain = metadata;

  material.onBeforeCompile = shader => {
    const worldToken = "#include <worldpos_vertex>";
    const colorToken = "#include <color_fragment>";
    const roughnessToken = "#include <roughnessmap_fragment>";
    const normalToken = "#include <normal_fragment_maps>";
    if (
      !shader.vertexShader.includes(worldToken) ||
      !shader.fragmentShader.includes(colorToken) ||
      (surfaceFidelity && (
        !shader.fragmentShader.includes(roughnessToken) ||
        !shader.fragmentShader.includes(normalToken)
      ))
    ) {
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
    const grain = surfaceFidelity
      ? `
float mpWoodAlongMm = vMpWoodWorldPosition.y;
float mpWoodAcrossMm = vMpWoodModulePosition.x;
float mpWoodMacro = mpWoodNoise(
  vec2(mpWoodAcrossMm / ${macroCellMm[0].toFixed(6)}, mpWoodAlongMm / ${macroCellMm[1].toFixed(6)}) + vec2(3.17, 11.43)
);
float mpWoodWarp = mpWoodNoise(
  vec2(mpWoodAcrossMm / ${(macroCellMm[0] * 1.7).toFixed(6)}, mpWoodAlongMm / ${(macroCellMm[1] * 0.55).toFixed(6)}) + vec2(19.2, 4.7)
) - 0.5;
float mpWoodFlow = mpWoodNoise(
  vec2(mpWoodAcrossMm / ${(macroCellMm[0] * 3.6).toFixed(6)}, mpWoodAlongMm / ${(macroCellMm[1] * 0.31).toFixed(6)}) + vec2(57.4, 13.8)
) - 0.5;
float mpWoodDrift = mpWoodNoise(
  vec2(mpWoodAcrossMm / ${(macroCellMm[0] * 5.4).toFixed(6)}, mpWoodAlongMm / ${(macroCellMm[1] * 0.17).toFixed(6)}) + vec2(8.9, 67.1)
) - 0.5;
float mpWoodFrequency = 1.0 + mpWoodFlow * 0.16 + mpWoodDrift * 0.07;
float mpWoodPhase =
  (mpWoodAcrossMm / ${fiberBandMm.toFixed(6)}) * mpWoodFrequency +
  (mpWoodMacro - 0.5) * 1.45 +
  mpWoodWarp * 1.55 +
  mpWoodFlow * 2.10 +
  mpWoodDrift * 1.25;
float mpWoodFiber = 0.5 + 0.5 * sin(mpWoodPhase * ${WOOD_GRAIN_TWO_PI.toFixed(6)});
float mpWoodFine = mpWoodNoise(
  vec2(mpWoodAcrossMm / ${fineCellMm[0].toFixed(6)}, mpWoodAlongMm / ${fineCellMm[1].toFixed(6)}) + vec2(41.7, 7.3)
);
float mpWoodPore = mpWoodNoise(
  vec2(
    mpWoodAcrossMm / ${(fineCellMm[0] * 0.55).toFixed(6)},
    mpWoodAlongMm / ${(fineCellMm[1] * 0.65).toFixed(6)}
  ) + vec2(73.1, 29.4)
);
float mpWoodFiberPresence = smoothstep(0.16, 0.84, mpWoodNoise(
  vec2(mpWoodAcrossMm / ${(macroCellMm[0] * 0.72).toFixed(6)}, mpWoodAlongMm / ${(macroCellMm[1] * 0.42).toFixed(6)}) + vec2(31.6, 91.2)
));
float mpWoodTone =
  (mpWoodMacro - 0.5) * 0.185 +
  (mpWoodFiber - 0.5) * mix(0.035, 0.070, mpWoodFiberPresence) +
  (mpWoodFine - 0.5) * 0.042 +
  mpWoodFlow * 0.025;
vec3 mpWoodCool = vec3(0.970, 0.985, 1.012);
vec3 mpWoodWarm = vec3(1.035, 1.002, 0.962);
diffuseColor.rgb *= mix(mpWoodCool, mpWoodWarm, clamp(mpWoodMacro, 0.0, 1.0));
diffuseColor.rgb = clamp(diffuseColor.rgb * (1.0 + mpWoodTone), 0.0, 1.0);
float mpWoodRoughnessDelta =
  (0.5 - mpWoodFiber) * mix(0.055, 0.090, mpWoodFiberPresence) +
  (mpWoodFine - 0.5) * 0.045 +
  (mpWoodPore - 0.5) * 0.026 +
  mpWoodFlow * 0.018;
float mpWoodMicroHeight =
  (mpWoodFiber - 0.5) * mix(0.26, 0.40, mpWoodFiberPresence) +
  (mpWoodFine - 0.5) * 0.28 +
  (mpWoodPore - 0.5) * 0.12;
`
      : `
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

    if (surfaceFidelity) {
      shader.fragmentShader = shader.fragmentShader
        .replace(
          roughnessToken,
          `${roughnessToken}
roughnessFactor = clamp(roughnessFactor + mpWoodRoughnessDelta, 0.16, 0.94);`
        )
        .replace(
          normalToken,
          `${normalToken}
vec3 mpWoodDpdx = dFdx(vViewPosition);
vec3 mpWoodDpdy = dFdy(vViewPosition);
float mpWoodDhdx = dFdx(mpWoodMicroHeight);
float mpWoodDhdy = dFdy(mpWoodMicroHeight);
vec3 mpWoodR1 = cross(mpWoodDpdy, normal);
vec3 mpWoodR2 = cross(normal, mpWoodDpdx);
float mpWoodDet = dot(mpWoodDpdx, mpWoodR1);
vec3 mpWoodGradient = sign(mpWoodDet) * (mpWoodDhdx * mpWoodR1 + mpWoodDhdy * mpWoodR2);
normal = normalize(abs(mpWoodDet) * normal - ${microNormalStrength.toFixed(6)} * mpWoodGradient);`
        );
    }
  };
  material.customProgramCacheKey = () => `mobilipresenter:${version}:${definition.id}`;
  material.needsUpdate = true;
}

function installBrushedMetalResponse(material: PbrMaterial, definition: MaterialDefinition): void {
  if (definition.id !== BRUSHED_METAL_MATERIAL_ID) return;
  if (!(material instanceof MeshPhysicalMaterial)) {
    throw new Error(`BRUSHED_METAL_REQUIRES_PHYSICAL_MATERIAL:${definition.id}`);
  }
  if (definition.grainDirection !== "u") {
    throw new Error(`BRUSHED_METAL_DIRECTION_INVALID:${definition.grainDirection ?? "missing"}`);
  }
  material.anisotropy = BRUSHED_METAL_RESPONSE.anisotropy;
  material.anisotropyRotation = BRUSHED_METAL_RESPONSE.anisotropyRotationRad;
  material.userData.brushedMetalResponse = {
    version: BRUSHED_METAL_RESPONSE_VERSION,
    grainDirection: definition.grainDirection,
    anisotropy: BRUSHED_METAL_RESPONSE.anisotropy,
    anisotropyRotationRad: BRUSHED_METAL_RESPONSE.anisotropyRotationRad,
    rasterMap: false
  };
}

function createThreeMaterial(
  definition: MaterialDefinition,
  surfaceFidelity: boolean
): PbrMaterial {
  const physical =
    definition.transmission > 0 ||
    definition.opacity < 1 ||
    definition.id === BRUSHED_METAL_MATERIAL_ID;
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
  material.userData.surfaceFidelity = surfaceFidelity;
  if (definition.physicalTextureScaleMm) {
    material.userData.physicalTextureScaleMm = [...definition.physicalTextureScaleMm];
  }
  if (definition.grainDirection) material.userData.grainDirection = definition.grainDirection;
  installWorldSpaceStoneSpeckle(material, definition, surfaceFidelity);
  installModuleContinuousWoodGrain(material, definition, surfaceFidelity);
  installBrushedMetalResponse(material, definition);
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
  readonly #surfaceFidelity: boolean;

  constructor(
    appearance: AppearancePackage,
    options: ThreeMaterialRegistryOptions = {}
  ) {
    this.#appearance = appearance;
    this.#surfaceFidelity = options.surfaceFidelity === true;
  }

  get surfaceFidelityEnabled(): boolean {
    return this.#surfaceFidelity;
  }

  get woodGrainShaderVersion(): WoodShaderVersion {
    return this.#surfaceFidelity
      ? SURFACE_FIDELITY_WOOD_SHADER_VERSION
      : WOOD_GRAIN_SHADER_VERSION;
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
    const material = createThreeMaterial(definition, this.#surfaceFidelity);
    this.#cache.set(id, material);
    return material;
  }

  materialByDefinitionId(id: string): PbrMaterial {
    const cached = this.#cache.get(id);
    if (cached) return cached;
    const definition = materialDefinitionById(this.#appearance, id);
    const material = createThreeMaterial(definition, this.#surfaceFidelity);
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
      if (object.userData.moduleContinuousMaterialMapping === metadata.version) return;

      const prior = object.onBeforeRender;
      object.onBeforeRender = function (...args): void {
        metadata.worldToModule.copy(worldToModule);
        prior.call(this, ...args);
      };
      object.userData.moduleContinuousMaterialMapping = metadata.version;
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
