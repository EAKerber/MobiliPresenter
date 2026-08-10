import {
  STONE03_ID,
  module02,
  module03WithSink,
  resolveLighting,
  type AppearancePackage,
  type ScenePackage
} from "@mobilipresenter/scene-core";
import {
  AmbientLight,
  DirectionalLight,
  Material,
  Mesh,
  MeshStandardMaterial,
  RectAreaLight,
  Scene
} from "three";
import { kelvinToColor, type ThreeLightingAdapter } from "../renderer/three/lighting.js";
import { ThreeMaterialRegistry } from "../renderer/three/materials.js";
import type { SelectiveBloomPipeline } from "../renderer/three/post.js";
import { syncThreeVisibility, type ThreeSceneAdapter } from "../renderer/three/scene-adapter.js";

const SINK_STONE_REFINEMENT = "fh06-1-s9-stone-hole-readability-v1";
const SINK_CUTOUT_DARKENING = 0.62;
const MODULE03_REVEALS = "fh06-s8/module03-drawer-reveals";
const MODULE02_REVEALS = "fh06-s10/module02-oven-reveals";

function firstMaterial(material: Material | readonly Material[]): Material {
  return Array.isArray(material) ? material[0]! : material;
}

function syncSinkStoneMaterial(mesh: Mesh, cap: Material): void {
  if (mesh.userData.visualRefinement !== SINK_STONE_REFINEMENT) {
    mesh.material = cap;
    return;
  }
  const existing = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
  const side = existing[1];
  if (!(cap instanceof MeshStandardMaterial) || !(side instanceof MeshStandardMaterial)) {
    throw new Error("VIEWER_SINK_STONE_MATERIAL_SHAPE_INVALID");
  }
  side.color.copy(cap.color).multiplyScalar(SINK_CUTOUT_DARKENING);
  side.roughness = Math.min(1, cap.roughness + 0.14);
  side.metalness = 0;
  mesh.material = [cap, side];
}

function syncRevealMaterial(
  adapter: ThreeSceneAdapter,
  registry: ThreeMaterialRegistry,
  moduleId: string,
  groupName: string,
  darkening: number
): void {
  const moduleGroup = adapter.entityGroups.get(moduleId);
  const revealGroup = moduleGroup?.getObjectByName(groupName);
  if (!revealGroup) return;
  const front = registry.resolve(moduleId, "front");
  if (!(front instanceof MeshStandardMaterial)) throw new Error(`VIEWER_FRONT_STANDARD_MATERIAL_REQUIRED:${moduleId}`);
  const updated = new Set<MeshStandardMaterial>();
  revealGroup.traverse(object => {
    if (!(object instanceof Mesh)) return;
    const material = firstMaterial(object.material);
    if (!(material instanceof MeshStandardMaterial) || updated.has(material)) return;
    material.color.copy(front.color).multiplyScalar(darkening);
    material.roughness = 0.95;
    material.metalness = 0;
    updated.add(material);
  });
}

export function syncRuntimeMaterials(
  adapter: ThreeSceneAdapter,
  registry: ThreeMaterialRegistry,
  appearance: AppearancePackage
): void {
  registry.updateAppearance(appearance);
  for (const [entityId, group] of adapter.entityGroups) {
    group.traverse(object => {
      if (!(object instanceof Mesh)) return;
      const slot = object.userData.materialSlot;
      if (typeof slot !== "string") return;
      const next = registry.resolve(entityId, slot);
      if (entityId === STONE03_ID && slot === "stone") syncSinkStoneMaterial(object, next);
      else object.material = next;
    });
  }
  syncRevealMaterial(adapter, registry, module03WithSink.id, MODULE03_REVEALS, 0.28);
  syncRevealMaterial(adapter, registry, module02.id, MODULE02_REVEALS, 0.22);
}

export function syncRuntimeVisibility(
  adapter: ThreeSceneAdapter,
  lighting: ThreeLightingAdapter,
  scenePackage: ScenePackage,
  appearance: AppearancePackage
): void {
  syncThreeVisibility(adapter, scenePackage);
  const activeEmitters = new Set(resolveLighting(scenePackage, appearance).semanticEmitters.map(emitter => emitter.instanceId));
  for (const [instanceId, group] of lighting.semanticGroups) {
    group.visible = activeEmitters.has(instanceId);
  }
}

export function syncRuntimeLighting(
  scene: Scene,
  lighting: ThreeLightingAdapter,
  post: SelectiveBloomPipeline,
  scenePackage: ScenePackage,
  appearance: AppearancePackage
): void {
  const definitions = new Map(appearance.lighting.baseRig.map(definition => [definition.id, definition] as const));
  for (const [id, light] of lighting.baseLights) {
    const definition = definitions.get(id);
    if (!definition) throw new Error(`VIEWER_LIGHT_DEFINITION_NOT_FOUND:${id}`);
    light.color.copy(kelvinToColor(definition.colorTemperatureK));
    if (light instanceof AmbientLight) light.intensity = definition.relativeIntensity;
    else if (light instanceof DirectionalLight) light.intensity = definition.relativeIntensity * 2;
    else if (light instanceof RectAreaLight) light.intensity = definition.relativeIntensity * 100;
  }
  scene.environmentIntensity = appearance.lighting.environment.relativeIntensity;
  post.setAppearance(appearance);
  syncRuntimeVisibility({ scene, entityGroups: new Map() }, lighting, scenePackage, appearance);
}
