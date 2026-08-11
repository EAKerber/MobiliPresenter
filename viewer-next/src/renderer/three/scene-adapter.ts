import type {
  GeometryPrimitive,
  SceneEntityBase,
  ScenePackage
} from "@mobilipresenter/scene-core";
import {
  allSceneEntities,
  resolveEffectiveVisibility,
  resolveItemPlacementTransform,
  resolveWorldTransforms
} from "@mobilipresenter/scene-core";
import {
  BoxGeometry,
  BufferGeometry,
  Float32BufferAttribute,
  Group,
  Material,
  Mesh,
  MeshBasicMaterial,
  Object3D,
  Scene,
  Vector3
} from "three";
import { applySceneTransform, sceneVectorToThree } from "./coordinates.js";

export type MaterialFactory = (entityId: string, materialSlot: string) => Material;

export interface ThreeSceneAdapter {
  readonly scene: Scene;
  readonly entityGroups: ReadonlyMap<string, Group>;
}

const defaultMaterialFactory: MaterialFactory = () => new MeshBasicMaterial({ color: 0xb8b6b0 });

function materialSlotFor(primitive: GeometryPrimitive): string {
  return primitive.materialSlot ?? "__unassigned__";
}

function createBoxMesh(
  entityId: string,
  primitive: Extract<GeometryPrimitive, { primitive: "box" }>,
  materialFactory: MaterialFactory
): Object3D {
  const group = new Group();
  group.name = primitive.id;
  applySceneTransform(group, primitive.localTransform);
  const geometry = new BoxGeometry(primitive.sizeMm.width, primitive.sizeMm.height, primitive.sizeMm.depth);
  const mesh = new Mesh(geometry, materialFactory(entityId, materialSlotFor(primitive)));
  mesh.name = `${primitive.id}/mesh`;
  mesh.position.set(
    primitive.sizeMm.width / 2,
    primitive.sizeMm.height / 2,
    -primitive.sizeMm.depth / 2
  );
  mesh.userData.geometryId = primitive.id;
  mesh.userData.materialSlot = materialSlotFor(primitive);
  group.add(mesh);
  return group;
}

function createFaceMesh(
  entityId: string,
  primitive: Extract<GeometryPrimitive, { primitive: "face" }>,
  materialFactory: MaterialFactory
): Object3D {
  const group = new Group();
  group.name = primitive.id;
  applySceneTransform(group, primitive.localTransform);

  const u = sceneVectorToThree(primitive.uAxis).multiplyScalar(primitive.sizeMm[0]);
  const v = sceneVectorToThree(primitive.vAxis).multiplyScalar(primitive.sizeMm[1]);
  const p0 = new Vector3(0, 0, 0);
  const p1 = u.clone();
  const p3 = v.clone();
  const p2 = u.clone().add(v);
  const positions = [p0, p1, p2, p0, p2, p3].flatMap(point => [point.x, point.y, point.z]);
  const geometry = new BufferGeometry();
  geometry.setAttribute("position", new Float32BufferAttribute(positions, 3));
  geometry.computeVertexNormals();
  geometry.computeBoundingBox();
  geometry.computeBoundingSphere();

  const mesh = new Mesh(geometry, materialFactory(entityId, materialSlotFor(primitive)));
  mesh.name = `${primitive.id}/mesh`;
  mesh.userData.geometryId = primitive.id;
  mesh.userData.materialSlot = materialSlotFor(primitive);
  group.add(mesh);
  return group;
}

function geometryOf(entity: SceneEntityBase & { readonly geometry?: readonly GeometryPrimitive[] }): readonly GeometryPrimitive[] {
  return entity.geometry ?? [];
}

export function buildThreeScene(
  source: ScenePackage,
  materialFactory: MaterialFactory = defaultMaterialFactory
): ThreeSceneAdapter {
  const scene = new Scene();
  scene.name = `scene:${source.sceneId}`;
  const entityGroups = new Map<string, Group>();
  const visibility = resolveEffectiveVisibility(source);
  const worldTransforms = resolveWorldTransforms(source);

  for (const entity of [...allSceneEntities(source)].sort((a, b) => a.id.localeCompare(b.id))) {
    const group = new Group();
    group.name = entity.id;
    group.userData.entityId = entity.id;
    group.userData.entityKind = entity.kind;
    group.visible = visibility.get(entity.id)?.effectiveVisible ?? false;

    const transform = entity.kind === "appliance" || entity.kind === "fixture" || entity.kind === "accessory"
      ? resolveItemPlacementTransform(source, entity)
      : worldTransforms.get(entity.id);
    if (!transform) throw new Error(`WORLD_TRANSFORM_NOT_FOUND:${entity.id}`);
    applySceneTransform(group, transform);

    for (const primitive of geometryOf(entity)) {
      group.add(
        primitive.primitive === "box"
          ? createBoxMesh(entity.id, primitive, materialFactory)
          : createFaceMesh(entity.id, primitive, materialFactory)
      );
    }
    entityGroups.set(entity.id, group);
    scene.add(group);
  }

  return { scene, entityGroups };
}

export function syncThreeVisibility(adapter: ThreeSceneAdapter, source: ScenePackage): void {
  const visibility = resolveEffectiveVisibility(source);
  for (const [entityId, group] of adapter.entityGroups) {
    const state = visibility.get(entityId);
    if (!state) throw new Error(`ENTITY_STATE_NOT_FOUND:${entityId}`);
    group.visible = state.effectiveVisible;
  }
}
