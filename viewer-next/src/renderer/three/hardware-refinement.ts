import {
  applyTransform,
  currentHardwareAnchors,
  currentHardwareDefinitions,
  invertTransform,
  resolveHardwareAnchor,
  resolveWorldTransforms,
  type HardwareAnchor,
  type HardwareDefinition,
  type ScenePackage
} from "@mobilipresenter/scene-core";
import {
  BoxGeometry,
  CylinderGeometry,
  Group,
  Mesh,
  type Material,
  type Object3D
} from "three";
import { sceneVectorToThree } from "./coordinates.js";
import type { ThreeMaterialRegistry } from "./materials.js";
import type { ThreeSceneAdapter } from "./scene-adapter.js";

export const HARDWARE_REFINEMENT_ID = "hardware-anchors-parametric-v1" as const;
export const HARDWARE_RENDER_MATERIAL_ID = "dark-metal" as const;

const ROOT_PREFIX = "hardware:";
const EPSILON_MM = 1e-6;

export interface HardwareRefinementResult {
  readonly refinementId: typeof HARDWARE_REFINEMENT_ID;
  readonly materialDefinitionId: typeof HARDWARE_RENDER_MATERIAL_ID;
  readonly anchorCount: number;
  readonly createdCount: number;
  readonly reusedCount: number;
  readonly hardwareDefinitionIds: readonly string[];
}

function meshPart(geometry: BoxGeometry | CylinderGeometry, material: Material, name: string): Mesh {
  const mesh = new Mesh(geometry, material);
  mesh.name = name;
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  mesh.userData.hardwarePart = true;
  return mesh;
}

function createBarHandle(
  definition: Extract<HardwareDefinition, { family: "bar-handle" }>,
  anchor: HardwareAnchor,
  material: Material
): Group {
  const root = new Group();
  const panelPlaneZ = -anchor.normalOffsetMm;
  const barRearZ = panelPlaneZ + definition.standoffDepthMm;
  const supportDepth = definition.standoffDepthMm;
  const supportCenterZ = panelPlaneZ + supportDepth / 2;

  const bar = meshPart(
    new BoxGeometry(definition.barLengthMm, definition.barWidthMm, definition.barDepthMm),
    material,
    "bar"
  );
  bar.position.z = barRearZ + definition.barDepthMm / 2;
  root.add(bar);

  for (const side of [-1, 1] as const) {
    const support = meshPart(
      new BoxGeometry(definition.supportWidthMm, definition.supportWidthMm, supportDepth),
      material,
      side < 0 ? "support-a" : "support-b"
    );
    support.position.x = side * definition.mountSpacingMm / 2;
    support.position.z = supportCenterZ;
    root.add(support);
  }

  if (anchor.orientation === "vertical") root.rotation.z = Math.PI / 2;
  root.userData.mountSpacingMm = definition.mountSpacingMm;
  root.userData.barLengthMm = definition.barLengthMm;
  root.userData.standoffDepthMm = definition.standoffDepthMm;
  return root;
}

function createPointHandle(
  definition: Extract<HardwareDefinition, { family: "point-handle" }>,
  anchor: HardwareAnchor,
  material: Material
): Group {
  const root = new Group();
  const panelPlaneZ = -anchor.normalOffsetMm;
  const knob = meshPart(
    new CylinderGeometry(definition.radiusMm, definition.radiusMm, definition.depthMm, 24, 1, false),
    material,
    "knob"
  );
  knob.rotation.x = Math.PI / 2;
  knob.position.z = panelPlaneZ + definition.depthMm / 2;
  root.add(knob);
  root.userData.radiusMm = definition.radiusMm;
  root.userData.depthMm = definition.depthMm;
  return root;
}

export function createHardwareHandle(
  definition: HardwareDefinition,
  anchor: HardwareAnchor,
  material: Material
): Group {
  const root = definition.family === "bar-handle"
    ? createBarHandle(definition, anchor, material)
    : createPointHandle(definition, anchor, material);
  root.userData.hardwareDefinitionId = definition.id;
  root.userData.hardwareFamily = definition.family;
  root.userData.hardwareOrientation = anchor.orientation;
  root.userData.anchorNormalOffsetMm = anchor.normalOffsetMm;
  return root;
}

function definitionById(definitions: readonly HardwareDefinition[], id: string): HardwareDefinition {
  const definition = definitions.find(candidate => candidate.id === id);
  if (!definition) throw new Error(`HARDWARE_DEFINITION_NOT_FOUND:${id}`);
  return definition;
}

function moduleLocalAnchorPosition(scene: ScenePackage, anchor: HardwareAnchor): ReturnType<typeof sceneVectorToThree> {
  const resolved = resolveHardwareAnchor(scene, anchor);
  const moduleWorld = resolveWorldTransforms(scene).get(anchor.hostEntityId);
  if (!moduleWorld) throw new Error(`HARDWARE_HOST_WORLD_NOT_FOUND:${anchor.hostEntityId}`);
  const localScene = applyTransform(invertTransform(moduleWorld), resolved.worldMm);
  return sceneVectorToThree(localScene);
}

function assertHandleRoot(root: Object3D, anchor: HardwareAnchor): void {
  if (root.userData.anchorId !== anchor.id) throw new Error(`HARDWARE_ROOT_ANCHOR_MISMATCH:${anchor.id}`);
  if (root.userData.hardwareDefinitionId !== anchor.hardwareDefinitionId) {
    throw new Error(`HARDWARE_ROOT_DEFINITION_MISMATCH:${anchor.id}`);
  }
}

export function applyHardwareRefinement(
  adapter: ThreeSceneAdapter,
  registry: ThreeMaterialRegistry,
  scene: ScenePackage,
  anchors: readonly HardwareAnchor[] = currentHardwareAnchors,
  definitions: readonly HardwareDefinition[] = currentHardwareDefinitions
): HardwareRefinementResult {
  const material = registry.materialByDefinitionId(HARDWARE_RENDER_MATERIAL_ID);
  const definitionIds = new Set<string>();
  let createdCount = 0;
  let reusedCount = 0;

  for (const anchor of anchors) {
    const host = adapter.entityGroups.get(anchor.hostEntityId);
    if (!host) throw new Error(`HARDWARE_RENDER_HOST_NOT_FOUND:${anchor.hostEntityId}`);
    const definition = definitionById(definitions, anchor.hardwareDefinitionId);
    definitionIds.add(definition.id);
    const name = `${ROOT_PREFIX}${anchor.id}`;
    const existing = host.getObjectByName(name);
    if (existing) {
      assertHandleRoot(existing, anchor);
      reusedCount += 1;
      continue;
    }

    const root = createHardwareHandle(definition, anchor, material);
    root.name = name;
    root.position.copy(moduleLocalAnchorPosition(scene, anchor));
    root.userData.anchorId = anchor.id;
    root.userData.hostEntityId = anchor.hostEntityId;
    root.userData.hostGeometryId = anchor.hostGeometryId;
    root.userData.refinementId = HARDWARE_REFINEMENT_ID;
    root.userData.interactionOwnedByHost = true;
    host.add(root);
    createdCount += 1;

    const resolved = resolveHardwareAnchor(scene, anchor);
    host.updateWorldMatrix(true, true);
    root.updateWorldMatrix(true, true);
    const actual = root.getWorldPosition(sceneVectorToThree({ x: 0, y: 0, z: 0 }));
    const expected = sceneVectorToThree(resolved.worldMm);
    if (actual.distanceTo(expected) > EPSILON_MM) {
      host.remove(root);
      throw new Error(`HARDWARE_RENDER_ANCHOR_DRIFT:${anchor.id}:${actual.distanceTo(expected)}`);
    }
  }

  return {
    refinementId: HARDWARE_REFINEMENT_ID,
    materialDefinitionId: HARDWARE_RENDER_MATERIAL_ID,
    anchorCount: anchors.length,
    createdCount,
    reusedCount,
    hardwareDefinitionIds: [...definitionIds].sort()
  };
}
