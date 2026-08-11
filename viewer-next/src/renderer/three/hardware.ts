import {
  currentHardwareAnchors,
  currentHardwareDefinitions,
  hardwareAnchorUvMm,
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
import type { ThreeMaterialRegistry } from "./materials.js";
import type { ThreeSceneAdapter } from "./scene-adapter.js";

export interface HardwareRenderDiagnostics {
  readonly refinementId: "hardware-anchors-v0.1";
  readonly handleCount: number;
  readonly anchorIds: readonly string[];
}

function mesh(geometry: BoxGeometry | CylinderGeometry, material: Material, name: string): Mesh {
  const result = new Mesh(geometry, material);
  result.name = name;
  result.castShadow = true;
  result.receiveShadow = true;
  result.userData.hardwareVisual = true;
  return result;
}

function barHandle(definition: Extract<HardwareDefinition, { family: "bar-handle" }>, orientation: HardwareAnchor["orientation"], material: Material): Group {
  const root = new Group();
  root.userData.hardwareDefinitionId = definition.id;
  root.userData.hardwareFamily = definition.family;

  const horizontal = orientation === "horizontal";
  const bar = mesh(
    new BoxGeometry(
      horizontal ? definition.barLengthMm : definition.barWidthMm,
      horizontal ? definition.barWidthMm : definition.barLengthMm,
      definition.barDepthMm
    ),
    material,
    "bar"
  );
  bar.position.z = definition.standoffDepthMm + definition.barDepthMm / 2;
  root.add(bar);

  const halfSpacing = definition.mountSpacingMm / 2;
  for (const sign of [-1, 1] as const) {
    const support = mesh(
      new BoxGeometry(definition.supportWidthMm, definition.supportWidthMm, definition.standoffDepthMm),
      material,
      sign < 0 ? "support-a" : "support-b"
    );
    support.position.set(
      horizontal ? sign * halfSpacing : 0,
      horizontal ? 0 : sign * halfSpacing,
      definition.standoffDepthMm / 2
    );
    root.add(support);
  }
  return root;
}

function pointHandle(definition: Extract<HardwareDefinition, { family: "point-handle" }>, material: Material): Group {
  const root = new Group();
  root.userData.hardwareDefinitionId = definition.id;
  root.userData.hardwareFamily = definition.family;
  const knob = mesh(
    new CylinderGeometry(definition.radiusMm, definition.radiusMm, definition.depthMm, 24, 1, false),
    material,
    "knob"
  );
  knob.rotation.x = Math.PI / 2;
  knob.position.z = definition.depthMm / 2;
  root.add(knob);
  return root;
}

export function createHardwareVisual(
  definition: HardwareDefinition,
  orientation: HardwareAnchor["orientation"],
  material: Material
): Group {
  return definition.family === "bar-handle"
    ? barHandle(definition, orientation, material)
    : pointHandle(definition, material);
}

function frontPrimitiveGroup(adapter: ThreeSceneAdapter, anchor: HardwareAnchor): Object3D {
  const host = adapter.entityGroups.get(anchor.hostEntityId);
  if (!host) throw new Error(`HARDWARE_RENDER_HOST_NOT_FOUND:${anchor.hostEntityId}`);
  const primitive = host.getObjectByName(anchor.hostGeometryId);
  if (!primitive) throw new Error(`HARDWARE_RENDER_PRIMITIVE_NOT_FOUND:${anchor.hostGeometryId}`);
  return primitive;
}

function definitionById(id: string): HardwareDefinition {
  const definition = currentHardwareDefinitions.find(candidate => candidate.id === id);
  if (!definition) throw new Error(`HARDWARE_RENDER_DEFINITION_NOT_FOUND:${id}`);
  return definition;
}

function anchorUv(scene: ScenePackage, anchor: HardwareAnchor): readonly [number, number] {
  const module = scene.modules.find(candidate => candidate.id === anchor.hostEntityId);
  if (!module) throw new Error(`HARDWARE_RENDER_HOST_NOT_FOUND:${anchor.hostEntityId}`);
  const primitive = module.geometry.find(candidate => candidate.id === anchor.hostGeometryId);
  if (!primitive || primitive.primitive !== "box" || primitive.role !== "front") {
    throw new Error(`HARDWARE_RENDER_FRONT_NOT_FOUND:${anchor.hostGeometryId}`);
  }
  return hardwareAnchorUvMm(primitive, anchor);
}

export function attachCurrentHardware(
  adapter: ThreeSceneAdapter,
  scene: ScenePackage,
  registry: ThreeMaterialRegistry
): HardwareRenderDiagnostics {
  const material = registry.materialByDefinitionId("dark-metal");
  const anchorIds: string[] = [];

  for (const anchor of currentHardwareAnchors) {
    const definition = definitionById(anchor.hardwareDefinitionId);
    const primitive = frontPrimitiveGroup(adapter, anchor);
    const [uMm, vMm] = anchorUv(scene, anchor);
    const visual = createHardwareVisual(definition, anchor.orientation, material);
    visual.name = anchor.id;
    visual.position.set(uMm, vMm, anchor.normalOffsetMm);
    visual.userData.hardwareAnchorId = anchor.id;
    visual.userData.hardwareDefinitionId = definition.id;
    visual.userData.hardwareOrientation = anchor.orientation;
    visual.userData.hardwareAnchorStatus = anchor.status;
    primitive.add(visual);
    anchorIds.push(anchor.id);
  }

  return {
    refinementId: "hardware-anchors-v0.1",
    handleCount: anchorIds.length,
    anchorIds
  };
}
