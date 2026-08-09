import type { Aabb3, RigidTransform, ScenePackage, Vec3 } from "@mobilipresenter/scene-core";
import {
  applyTransform,
  resolveItemPlacementTransform,
  resolveWorldTransforms
} from "@mobilipresenter/scene-core";
import { DirectionalLight } from "three";

function corners(aabb: Aabb3): readonly Vec3[] {
  const { min, max } = aabb;
  return [
    { x:min.x,y:min.y,z:min.z }, { x:max.x,y:min.y,z:min.z },
    { x:min.x,y:max.y,z:min.z }, { x:max.x,y:max.y,z:min.z },
    { x:min.x,y:min.y,z:max.z }, { x:max.x,y:min.y,z:max.z },
    { x:min.x,y:max.y,z:max.z }, { x:max.x,y:max.y,z:max.z }
  ];
}

function transformedCorners(aabb: Aabb3, transform: RigidTransform): readonly Vec3[] {
  return corners(aabb).map(point => applyTransform(transform, point));
}

function itemEnvelopeCorners(scene: ScenePackage): readonly Vec3[] {
  const result: Vec3[] = [];
  for (const item of scene.items) {
    if (!item.targetEnvelopeMm) continue;
    const placement = resolveItemPlacementTransform(scene, item);
    const aabb: Aabb3 = {
      min: { x:0,y:0,z:0 },
      max: {
        x:item.targetEnvelopeMm.width,
        y:item.targetEnvelopeMm.depth,
        z:item.targetEnvelopeMm.height
      }
    };
    result.push(...transformedCorners(aabb, placement));
  }
  return result;
}

export function sceneShadowRadiusMm(scene: ScenePackage): number {
  const world = resolveWorldTransforms(scene);
  const points: Vec3[] = [];
  for (const environment of scene.environment) {
    const transform = world.get(environment.id);
    if (transform) points.push(...transformedCorners(environment.structuralEnvelope, transform));
  }
  for (const module of scene.modules) {
    const transform = world.get(module.id);
    if (transform) points.push(...transformedCorners(module.renderEnvelope, transform));
  }
  points.push(...itemEnvelopeCorners(scene));

  const target = scene.camera.targetMm;
  let radius = 0;
  for (const point of points) {
    const dx=point.x-target.x, dy=point.y-target.y, dz=point.z-target.z;
    radius = Math.max(radius, Math.hypot(dx,dy,dz));
  }
  return Math.max(1000, Math.ceil(radius / 250) * 250);
}

export function configureDirectionalShadowForScene(light: DirectionalLight, scene: ScenePackage): number {
  const span = sceneShadowRadiusMm(scene);
  const camera = light.shadow.camera;
  camera.left = -span;
  camera.right = span;
  camera.top = span;
  camera.bottom = -span;
  camera.near = 100;
  camera.far = Math.max(5000, light.position.distanceTo(light.target.position) + span * 2);
  camera.updateProjectionMatrix();
  return span;
}
