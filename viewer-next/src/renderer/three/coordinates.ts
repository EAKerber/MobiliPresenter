import type { RigidTransform, Vec3 } from "@mobilipresenter/scene-core";
import { Matrix4, Object3D, Vector3 } from "three";

const SCENE_TO_THREE = new Matrix4().makeRotationX(-Math.PI / 2);
const THREE_TO_SCENE = SCENE_TO_THREE.clone().invert();

export function sceneVectorToThree(value: Vec3): Vector3 {
  return new Vector3(value.x, value.z, -value.y);
}

export function threeVectorToScene(value: Vector3): Vec3 {
  return { x: value.x, y: -value.z, z: value.y };
}

export function sceneTransformToThreeMatrix(transform: RigidTransform): Matrix4 {
  const sceneMatrix = new Matrix4().compose(
    new Vector3(transform.translationMm.x, transform.translationMm.y, transform.translationMm.z),
    { x: transform.rotation.x, y: transform.rotation.y, z: transform.rotation.z, w: transform.rotation.w } as never,
    new Vector3(1, 1, 1)
  );
  return SCENE_TO_THREE.clone().multiply(sceneMatrix).multiply(THREE_TO_SCENE);
}

export function applySceneTransform(object: Object3D, transform: RigidTransform): void {
  object.matrixAutoUpdate = false;
  object.matrix.copy(sceneTransformToThreeMatrix(transform));
  object.matrixWorldNeedsUpdate = true;
}

export function sceneDirectionToThree(value: Vec3): Vector3 {
  return sceneVectorToThree(value).normalize();
}
