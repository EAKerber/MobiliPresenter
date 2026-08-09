import type {
  ApplianceDefinition,
  AppearancePackage,
  DimensionTripleMm,
  SceneItem,
  ScenePackage
} from "@mobilipresenter/scene-core";
import {
  Box3,
  BoxGeometry,
  CylinderGeometry,
  Group,
  Mesh,
  MeshPhysicalMaterial,
  MeshStandardMaterial,
  Object3D,
  TorusGeometry,
  Vector3
} from "three";
import type { ThreeSceneAdapter } from "./scene-adapter.js";
import type { ThreeMaterialRegistry } from "./materials.js";

export interface ApplianceFit {
  readonly envelopeMm: DimensionTripleMm;
  readonly fittedMm: DimensionTripleMm;
  readonly offsetMm: readonly [number, number, number];
}

function hostedEnvelope(scene: ScenePackage, item: SceneItem): DimensionTripleMm {
  if (!item.hostId || !item.slotId) throw new Error(`HOSTED_ITEM_SLOT_REQUIRED:${item.id}`);
  const host = scene.modules.find(module => module.id === item.hostId);
  if (!host) throw new Error(`APPLIANCE_HOST_MODULE_NOT_FOUND:${item.hostId}`);
  const slot = host.applianceSlots.find(candidate => candidate.id === item.slotId);
  if (!slot) throw new Error(`APPLIANCE_SLOT_NOT_FOUND:${item.slotId}`);
  return slot.clearSizeMm;
}

function fitUniform(
  nominal: DimensionTripleMm,
  envelope: DimensionTripleMm,
  axes: readonly (keyof DimensionTripleMm)[] = ["width", "height", "depth"]
): DimensionTripleMm {
  const scale = Math.min(...axes.map(axis => envelope[axis] / nominal[axis]));
  return {
    width: nominal.width * scale,
    height: nominal.height * scale,
    depth: nominal.depth * scale
  };
}

export function resolveApplianceFit(
  scene: ScenePackage,
  item: SceneItem,
  definition: ApplianceDefinition
): ApplianceFit {
  const envelope = item.mountPolicy === "hosted"
    ? hostedEnvelope(scene, item)
    : item.targetEnvelopeMm;
  if (!envelope) throw new Error(`APPLIANCE_TARGET_ENVELOPE_REQUIRED:${item.id}`);
  const nominal = definition.nominalAppearanceMm;

  let fitted: DimensionTripleMm;
  switch (definition.fitPolicy) {
    case "fit-to-slot-front-authoritative":
      fitted = {
        width: Math.min(nominal.width, envelope.width),
        height: Math.min(nominal.height, envelope.height),
        depth: Math.min(nominal.depth, envelope.depth)
      };
      break;
    case "letterbox-allowed-within-slot":
    case "stone-cutout-dependent":
    case "fixture-adjustable-preserve-basin-language":
      fitted = fitUniform(nominal, envelope);
      break;
    case "under-cab-fit":
    case "top-surface-fit":
      fitted = {
        width: Math.min(nominal.width, envelope.width),
        height: Math.min(nominal.height, envelope.height),
        depth: Math.min(nominal.depth, envelope.depth)
      };
      break;
    case "fit-to-source-envelope-preserve-front-proportions": {
      const frontScale = Math.min(envelope.width / nominal.width, envelope.height / nominal.height);
      fitted = {
        width: nominal.width * frontScale,
        height: nominal.height * frontScale,
        depth: Math.min(nominal.depth * frontScale, envelope.depth)
      };
      break;
    }
    case "fit-to-environment-envelope":
      fitted = { ...envelope };
      break;
    case "allow-small-nonuniform-scale-depth<=3%": {
      const uniform = fitUniform(nominal, envelope, ["width", "height"]);
      const depthScale = envelope.depth / nominal.depth;
      if (Math.abs(depthScale - 1) > 0.03) throw new Error(`APPLIANCE_DEPTH_SCALE_EXCEEDS_POLICY:${item.id}`);
      fitted = { width: uniform.width, height: uniform.height, depth: envelope.depth };
      break;
    }
  }

  const offsetX = (envelope.width - fitted.width) / 2;
  const offsetDepth = (envelope.depth - fitted.depth) / 2;
  const centerVertically = definition.fitPolicy === "letterbox-allowed-within-slot" || definition.role === "kitchen-sink";
  const offsetZ = centerVertically ? (envelope.height - fitted.height) / 2 : 0;
  return {
    envelopeMm: envelope,
    fittedMm: fitted,
    offsetMm: [offsetX, offsetDepth, offsetZ]
  };
}

function boxPart(
  width: number,
  height: number,
  depth: number,
  material: MeshStandardMaterial | MeshPhysicalMaterial,
  x = 0,
  y = 0,
  z = 0
): Mesh {
  const mesh = new Mesh(new BoxGeometry(width, height, depth), material);
  mesh.position.set(x + width / 2, z + height / 2, -(y + depth / 2));
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  return mesh;
}

function frontDisc(
  radius: number,
  thickness: number,
  material: MeshStandardMaterial | MeshPhysicalMaterial,
  x: number,
  z: number,
  frontY = -2
): Mesh {
  const mesh = new Mesh(new CylinderGeometry(radius, radius, thickness, 48), material);
  mesh.rotation.x = Math.PI / 2;
  mesh.position.set(x, z, -frontY);
  mesh.castShadow = true;
  return mesh;
}

function frontRing(
  majorRadius: number,
  tube: number,
  material: MeshStandardMaterial | MeshPhysicalMaterial,
  x: number,
  z: number,
  frontY = -4
): Mesh {
  const mesh = new Mesh(new TorusGeometry(majorRadius, tube, 16, 64), material);
  mesh.position.set(x, z, -frontY);
  mesh.castShadow = true;
  return mesh;
}

function material(registry: ThreeMaterialRegistry, id: string): MeshStandardMaterial | MeshPhysicalMaterial {
  return registry.materialByDefinitionId(id);
}

function buildWasher(size: DimensionTripleMm, registry: ThreeMaterialRegistry): Object3D {
  const group = new Group();
  const body = material(registry, "inox-brushed");
  const glass = material(registry, "black-glass");
  const dark = material(registry, "dark-plastic");
  group.add(boxPart(size.width, size.height, size.depth, body));
  const centerX = size.width * 0.5;
  const centerZ = size.height * 0.48;
  const radius = Math.min(size.width, size.height) * 0.29;
  group.add(frontDisc(radius * 0.88, 10, glass, centerX, centerZ));
  group.add(frontRing(radius, Math.max(8, radius * 0.08), dark, centerX, centerZ));
  group.add(boxPart(size.width * 0.72, size.height * 0.11, 18, dark, size.width * 0.23, -18, size.height * 0.83));
  return group;
}

function buildFridge(size: DimensionTripleMm, registry: ThreeMaterialRegistry): Object3D {
  const group = new Group();
  const inox = material(registry, "inox-brushed");
  const dark = material(registry, "dark-plastic");
  group.add(boxPart(size.width, size.height, size.depth, inox));
  const splitZ = size.height * 0.38;
  group.add(boxPart(size.width * 0.96, 8, 14, dark, size.width * 0.02, -14, splitZ));
  group.add(boxPart(size.width * 0.22, size.height * 0.22, 18, dark, size.width * 0.57, -20, size.height * 0.54));
  group.add(boxPart(14, size.height * 0.38, 18, dark, size.width * 0.09, -20, size.height * 0.49));
  return group;
}

function buildOven(size: DimensionTripleMm, registry: ThreeMaterialRegistry): Object3D {
  const group = new Group();
  const inox = material(registry, "inox-brushed");
  const glass = material(registry, "black-glass");
  group.add(boxPart(size.width, size.height, size.depth, inox));
  group.add(boxPart(size.width * 0.82, size.height * 0.64, 18, glass, size.width * 0.09, -20, size.height * 0.12));
  group.add(boxPart(size.width * 0.72, 18, 22, inox, size.width * 0.14, -26, size.height * 0.78));
  group.add(boxPart(size.width * 0.7, size.height * 0.09, 16, glass, size.width * 0.15, -18, size.height * 0.87));
  return group;
}

function buildMicrowave(size: DimensionTripleMm, registry: ThreeMaterialRegistry): Object3D {
  const group = new Group();
  const inox = material(registry, "inox-brushed");
  const glass = material(registry, "black-glass");
  const dark = material(registry, "dark-plastic");
  group.add(boxPart(size.width, size.height, size.depth, inox));
  group.add(boxPart(size.width * 0.76, size.height * 0.82, 16, glass, size.width * 0.03, -18, size.height * 0.09));
  group.add(boxPart(size.width * 0.15, size.height * 0.82, 18, dark, size.width * 0.82, -20, size.height * 0.09));
  return group;
}

function buildHood(size: DimensionTripleMm, registry: ThreeMaterialRegistry): Object3D {
  const group = new Group();
  const inox = material(registry, "inox-brushed");
  const dark = material(registry, "dark-metal");
  group.add(boxPart(size.width, size.height, size.depth, inox));
  group.add(boxPart(size.width * 0.86, 10, size.depth * 0.72, dark, size.width * 0.07, size.depth * 0.12, 6));
  return group;
}

function buildCooktop(size: DimensionTripleMm, registry: ThreeMaterialRegistry): Object3D {
  const group = new Group();
  const glass = material(registry, "black-glass");
  const dark = material(registry, "dark-metal");
  group.add(boxPart(size.width, Math.min(size.height, 18), size.depth, glass, 0, 0, Math.max(0, size.height - 18)));
  const positions = [[0.28,0.3],[0.68,0.3],[0.28,0.72],[0.68,0.72]] as const;
  for (const [px,py] of positions) {
    const radius = Math.min(size.width, size.depth) * (px < 0.5 && py > 0.5 ? 0.11 : 0.085);
    const burner = frontRing(radius, Math.max(4, radius * 0.12), dark, size.width * px, size.height + 4, -(size.depth * py));
    burner.rotation.x = Math.PI / 2;
    burner.rotation.z = Math.PI / 2;
    group.add(burner);
  }
  return group;
}

function buildSink(size: DimensionTripleMm, registry: ThreeMaterialRegistry): Object3D {
  const group = new Group();
  const inox = material(registry, "inox-brushed");
  const chrome = material(registry, "chrome");
  const rim = Math.max(10, Math.min(size.width, size.depth) * 0.045);
  group.add(boxPart(size.width, rim, size.depth, inox, 0, 0, size.height - rim));
  group.add(boxPart(rim, size.height, size.depth, inox));
  group.add(boxPart(rim, size.height, size.depth, inox, size.width-rim));
  group.add(boxPart(size.width-2*rim, size.height, rim, inox, rim, size.depth-rim));
  const faucetStem = new Mesh(new CylinderGeometry(8, 8, size.height * 0.9, 20), chrome);
  faucetStem.position.set(size.width * 0.82, size.height * 1.2, -size.depth * 0.88);
  group.add(faucetStem);
  return group;
}

function buildTank(size: DimensionTripleMm, registry: ThreeMaterialRegistry): Object3D {
  const group = new Group();
  const ceramic = material(registry, "ceramic-white");
  group.add(boxPart(size.width, size.height * 0.36, size.depth, ceramic, 0, 0, size.height * 0.64));
  group.add(boxPart(size.width * 0.28, size.height * 0.64, size.depth * 0.34, ceramic, size.width * 0.36, size.depth * 0.33, 0));
  return group;
}

function buildDefinition(
  definition: ApplianceDefinition,
  size: DimensionTripleMm,
  registry: ThreeMaterialRegistry
): Object3D {
  switch (definition.role) {
    case "laundry-washer": return buildWasher(size, registry);
    case "refrigerator": return buildFridge(size, registry);
    case "built-in-oven": return buildOven(size, registry);
    case "built-in-microwave": return buildMicrowave(size, registry);
    case "hood": return buildHood(size, registry);
    case "cooktop": return buildCooktop(size, registry);
    case "kitchen-sink": return buildSink(size, registry);
    case "laundry-tank": return buildTank(size, registry);
  }
}

export function buildParametricAppliance(
  scene: ScenePackage,
  item: SceneItem,
  definition: ApplianceDefinition,
  registry: ThreeMaterialRegistry
): Object3D {
  const fit = resolveApplianceFit(scene, item, definition);
  const root = new Group();
  root.name = `${item.id}/parametric`;
  root.userData.applianceDefinitionId = definition.id;
  root.userData.fit = fit;
  const visual = buildDefinition(definition, fit.fittedMm, registry);
  visual.position.set(fit.offsetMm[0], fit.offsetMm[2], -fit.offsetMm[1]);
  root.add(visual);
  return root;
}

export function attachParametricAppliances(
  adapter: ThreeSceneAdapter,
  scene: ScenePackage,
  appearance: AppearancePackage,
  registry: ThreeMaterialRegistry
): void {
  const definitions = new Map(appearance.applianceDefinitions.map(definition => [definition.id, definition] as const));
  for (const item of scene.items) {
    if (item.kind === "accessory") continue;
    const definition = definitions.get(item.definitionId);
    if (!definition) throw new Error(`APPLIANCE_DEFINITION_NOT_FOUND:${item.definitionId}`);
    const group = adapter.entityGroups.get(item.id);
    if (!group) throw new Error(`APPLIANCE_ENTITY_GROUP_NOT_FOUND:${item.id}`);
    const existing = group.getObjectByName(`${item.id}/parametric`);
    if (existing) group.remove(existing);
    group.add(buildParametricAppliance(scene, item, definition, registry));
  }
}

export function applianceLocalBounds(object: Object3D): Box3 {
  object.updateWorldMatrix(true, true);
  return new Box3().setFromObject(object);
}
