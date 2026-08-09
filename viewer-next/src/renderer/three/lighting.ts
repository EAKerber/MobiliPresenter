import type {
  AppearancePackage,
  SceneItem,
  ScenePackage,
  SemanticEmitterDefinition,
  Vec3
} from "@mobilipresenter/scene-core";
import {
  applyTransform,
  resolveItemPlacementTransform,
  resolveLighting,
  rotateVector,
  vec3
} from "@mobilipresenter/scene-core";
import {
  AmbientLight,
  Color,
  DirectionalLight,
  Group,
  Mesh,
  MeshBasicMaterial,
  PlaneGeometry,
  PointLight,
  RectAreaLight,
  Scene,
  WebGLRenderer
} from "three";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { PMREMGenerator } from "three";
import { resolveApplianceFit } from "./appliances.js";
import { sceneDirectionToThree, sceneVectorToThree } from "./coordinates.js";
import { configureDirectionalShadowForScene } from "./shadows.js";

export const BLOOM_LAYER = 1;

export interface ThreeLightingAdapter {
  readonly root: Group;
  readonly baseLights: ReadonlyMap<string, AmbientLight | DirectionalLight | RectAreaLight>;
  readonly semanticGroups: ReadonlyMap<string, Group>;
}

export interface RoomEnvironmentHandle {
  dispose(): void;
}

function clamp255(value: number): number {
  return Math.max(0, Math.min(255, Math.round(value)));
}

export function kelvinToColor(kelvin: number): Color {
  const temperature = Math.max(1000, Math.min(40000, kelvin)) / 100;
  let red: number;
  let green: number;
  let blue: number;
  if (temperature <= 66) {
    red = 255;
    green = 99.4708025861 * Math.log(temperature) - 161.1195681661;
    blue = temperature <= 19 ? 0 : 138.5177312231 * Math.log(temperature - 10) - 305.0447927307;
  } else {
    red = 329.698727446 * Math.pow(temperature - 60, -0.1332047592);
    green = 288.1221695283 * Math.pow(temperature - 60, -0.0755148492);
    blue = 255;
  }
  return new Color(`rgb(${clamp255(red)}, ${clamp255(green)}, ${clamp255(blue)})`);
}

function scenePointAdd(origin: Vec3, direction: Vec3, scale: number): Vec3 {
  return { x: origin.x + direction.x * scale, y: origin.y + direction.y * scale, z: origin.z + direction.z * scale };
}

function createBaseRig(scenePackage: ScenePackage, appearance: AppearancePackage): {
  root: Group;
  lights: Map<string, AmbientLight | DirectionalLight | RectAreaLight>;
} {
  const root = new Group();
  root.name = "__lighting/base";
  const lights = new Map<string, AmbientLight | DirectionalLight | RectAreaLight>();
  const targetScene = scenePackage.camera.targetMm;
  const targetThree = sceneVectorToThree(targetScene);

  for (const definition of appearance.lighting.baseRig) {
    const color = kelvinToColor(definition.colorTemperatureK);
    if (definition.type === "ambient") {
      const light = new AmbientLight(color, definition.relativeIntensity);
      light.name = `light:${definition.id}`;
      lights.set(definition.id, light);
      root.add(light);
      continue;
    }

    if (definition.type === "directional") {
      const direction = definition.direction ?? vec3(0, 1, -1);
      const sourcePosition = scenePointAdd(targetScene, direction, -5000);
      const light = new DirectionalLight(color, definition.relativeIntensity * 2);
      light.name = `light:${definition.id}`;
      light.position.copy(sceneVectorToThree(sourcePosition));
      light.target.position.copy(targetThree);
      light.castShadow = definition.id === "key-front-high";
      if (light.castShadow) {
        light.shadow.mapSize.set(2048, 2048);
        light.shadow.bias = -0.00015;
        light.shadow.normalBias = 0.8;
        configureDirectionalShadowForScene(light, scenePackage);
      }
      lights.set(definition.id, light);
      root.add(light, light.target);
      continue;
    }

    const light = new RectAreaLight(color, definition.relativeIntensity * 100, 1500, 900);
    light.name = `light:${definition.id}`;
    light.position.copy(sceneVectorToThree(scenePointAdd(targetScene, definition.direction ?? vec3(0, 1, -1), -2500)));
    light.lookAt(targetThree);
    lights.set(definition.id, light);
    root.add(light);
  }
  return { root, lights };
}

interface EmitterFrame {
  readonly originMm: Vec3;
  readonly sizeMm: { readonly width: number; readonly height: number; readonly depth: number };
}

function localAccessoryFrame(item: SceneItem): EmitterFrame {
  const boxes = (item.geometry ?? []).filter(primitive => primitive.primitive === "box");
  if (boxes.length === 0) return { originMm: vec3(), sizeMm: { width: 1, height: 1, depth: 1 } };
  let minX = Infinity, minY = Infinity, minZ = Infinity;
  let maxX = -Infinity, maxY = -Infinity, maxZ = -Infinity;
  for (const primitive of boxes) {
    const p = primitive.localTransform.translationMm;
    minX = Math.min(minX, p.x); minY = Math.min(minY, p.y); minZ = Math.min(minZ, p.z);
    maxX = Math.max(maxX, p.x + primitive.sizeMm.width);
    maxY = Math.max(maxY, p.y + primitive.sizeMm.depth);
    maxZ = Math.max(maxZ, p.z + primitive.sizeMm.height);
  }
  return {
    originMm: { x: minX, y: minY, z: minZ },
    sizeMm: { width: maxX-minX, height: maxZ-minZ, depth: maxY-minY }
  };
}

function emitterFrame(scene: ScenePackage, appearance: AppearancePackage, item: SceneItem): EmitterFrame {
  if (item.kind === "accessory") return localAccessoryFrame(item);
  const definition = appearance.applianceDefinitions.find(candidate => candidate.id === item.definitionId);
  if (!definition) throw new Error(`APPLIANCE_DEFINITION_NOT_FOUND:${item.definitionId}`);
  const fit = resolveApplianceFit(scene, item, definition);
  return {
    originMm: { x: fit.offsetMm[0], y: fit.offsetMm[1], z: fit.offsetMm[2] },
    sizeMm: fit.fittedMm
  };
}

function emitterWorldPoint(scene: ScenePackage, appearance: AppearancePackage, item: SceneItem, emitter: SemanticEmitterDefinition): Vec3 {
  const frame = emitterFrame(scene, appearance, item);
  const local = {
    x: frame.originMm.x + frame.sizeMm.width * emitter.localPositionNormalized[0],
    y: frame.originMm.y + frame.sizeMm.depth * emitter.localPositionNormalized[1],
    z: frame.originMm.z + frame.sizeMm.height * emitter.localPositionNormalized[2]
  };
  return applyTransform(resolveItemPlacementTransform(scene, item), local);
}

function emitterWorldDirection(scene: ScenePackage, item: SceneItem, emitter: SemanticEmitterDefinition): Vec3 {
  const localDirection = emitter.localDirection ?? vec3(0, -1, 0);
  return rotateVector(resolveItemPlacementTransform(scene, item).rotation, localDirection);
}

function createEmitterVisual(widthMm: number, heightMm: number, color: Color): Mesh {
  const material = new MeshBasicMaterial({ color, toneMapped: false, depthWrite: false });
  const mesh = new Mesh(new PlaneGeometry(widthMm, heightMm), material);
  mesh.name = "emitter-surface";
  mesh.layers.enable(BLOOM_LAYER);
  mesh.userData.semanticEmitter = true;
  return mesh;
}

function createSemanticGroup(
  scene: ScenePackage,
  appearance: AppearancePackage,
  item: SceneItem,
  emitter: SemanticEmitterDefinition,
  instanceId: string
): Group {
  const group = new Group();
  group.name = `emitter:${instanceId}`;
  group.userData.emitterInstanceId = instanceId;
  const color = kelvinToColor(emitter.colorTemperatureK);
  const worldPoint = emitterWorldPoint(scene, appearance, item, emitter);
  const worldDirection = emitterWorldDirection(scene, item, emitter);
  const positionThree = sceneVectorToThree(worldPoint);
  const targetThree = positionThree.clone().add(sceneDirectionToThree(worldDirection));
  group.position.copy(positionThree);

  if (emitter.type === "point") {
    const light = new PointLight(color, emitter.relativeIntensity * 2000, 1600, 2);
    light.name = "semantic-light";
    light.castShadow = false;
    group.add(light);
  } else {
    const frame = emitterFrame(scene, appearance, item);
    const width = emitter.type === "line" ? Math.max(80, frame.sizeMm.width * 0.72) : Math.max(80, frame.sizeMm.width * 0.45);
    const height = emitter.type === "line" ? 12 : Math.max(30, frame.sizeMm.height * 0.25);
    const light = new RectAreaLight(color, emitter.relativeIntensity * 120, width, height);
    light.name = "semantic-light";
    light.lookAt(targetThree.clone().sub(positionThree));
    const visual = createEmitterVisual(width, height, color);
    visual.lookAt(targetThree.clone().sub(positionThree));
    group.add(light, visual);
  }
  return group;
}

export function buildThreeLighting(scenePackage: ScenePackage, appearance: AppearancePackage): ThreeLightingAdapter {
  const root = new Group();
  root.name = "__lighting";
  const base = createBaseRig(scenePackage, appearance);
  root.add(base.root);
  const semanticGroups = new Map<string, Group>();
  const resolved = resolveLighting(scenePackage, appearance);

  for (const emitter of resolved.semanticEmitters) {
    const item = scenePackage.items.find(candidate => candidate.id === emitter.entityId);
    if (!item) throw new Error(`EMITTER_ENTITY_NOT_FOUND:${emitter.entityId}`);
    const group = createSemanticGroup(scenePackage, appearance, item, emitter, emitter.instanceId);
    semanticGroups.set(emitter.instanceId, group);
    root.add(group);
  }
  return { root, baseLights: base.lights, semanticGroups };
}

export function installNeutralRoomEnvironment(
  renderer: WebGLRenderer,
  scene: Scene,
  relativeIntensity: number
): RoomEnvironmentHandle {
  const room = new RoomEnvironment();
  const pmrem = new PMREMGenerator(renderer);
  const target = pmrem.fromScene(room, 0.04);
  scene.environment = target.texture;
  scene.environmentIntensity = relativeIntensity;
  return {
    dispose(): void {
      scene.environment = null;
      target.dispose();
      pmrem.dispose();
      room.clear();
    }
  };
}
