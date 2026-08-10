import type { ScenePackage, UnderCabLightContract, Vec3 } from "@mobilipresenter/scene-core";
import {
  composeTransforms,
  resolveWorldTransforms
} from "@mobilipresenter/scene-core";
import {
  BufferGeometry,
  DoubleSide,
  Float32BufferAttribute,
  Mesh,
  MeshStandardMaterial,
  RectAreaLight,
  type Object3D
} from "three";
import { applySceneTransform, sceneDirectionToThree, sceneVectorToThree } from "./coordinates.js";
import { BLOOM_LAYER, kelvinToColor } from "./lighting.js";
import type { ThreeMaterialRegistry } from "./materials.js";
import type { ThreeSceneAdapter } from "./scene-adapter.js";

const DIFFUSER_EDGE_INSET = 0.08;
const DIFFUSER_OUTWARD_OFFSET_MM = 0.35;

function disposeGeometryTree(root: Object3D): void {
  root.traverse(object => {
    if (object instanceof Mesh) object.geometry.dispose();
  });
}

function geometryFromSceneVertices(vertices: readonly Vec3[], indices: readonly number[]): BufferGeometry {
  const positions = vertices.flatMap(vertex => {
    const point = sceneVectorToThree(vertex);
    return [point.x, point.y, point.z];
  });
  const geometry = new BufferGeometry();
  geometry.setAttribute("position", new Float32BufferAttribute(positions, 3));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();
  geometry.computeBoundingBox();
  geometry.computeBoundingSphere();
  return geometry;
}

function triangularPrism(widthMm: number, depthMm: number, heightMm: number): BufferGeometry {
  const vertices: Vec3[] = [
    { x: 0, y: 0, z: heightMm },
    { x: 0, y: depthMm, z: heightMm },
    { x: 0, y: depthMm, z: 0 },
    { x: widthMm, y: 0, z: heightMm },
    { x: widthMm, y: depthMm, z: heightMm },
    { x: widthMm, y: depthMm, z: 0 }
  ];
  const indices = [
    0, 2, 1,
    3, 4, 5,
    0, 1, 4, 0, 4, 3,
    1, 2, 5, 1, 5, 4,
    2, 0, 3, 2, 3, 5
  ];
  const geometry = geometryFromSceneVertices(vertices, indices);
  geometry.userData.profileCrossSection = "right-triangle-18x18";
  geometry.userData.hypotenuseAngleDeg = 45;
  return geometry;
}

function diffuserGeometry(contract: UnderCabLightContract): BufferGeometry {
  const { width, height, depth } = contract.visualSizeMm;
  const t0 = DIFFUSER_EDGE_INSET;
  const t1 = 1 - DIFFUSER_EDGE_INSET;
  const outward = contract.emitter.localDirection;
  const point = (x: number, t: number): Vec3 => ({
    x,
    y: depth * t + outward.y * DIFFUSER_OUTWARD_OFFSET_MM,
    z: height * (1 - t) + outward.z * DIFFUSER_OUTWARD_OFFSET_MM
  });
  const marginX = (width - contract.emitter.emittingWidthMm) / 2;
  const vertices = [
    point(marginX, t0),
    point(width - marginX, t0),
    point(width - marginX, t1),
    point(marginX, t1)
  ];
  const geometry = geometryFromSceneVertices(vertices, [0, 1, 2, 0, 2, 3]);
  geometry.userData.diffuser = "opal-hypotenuse";
  geometry.userData.angleDeg = contract.profileAngleDeg;
  return geometry;
}

function localEmitterPoint(contract: UnderCabLightContract): Vec3 {
  return {
    x: contract.visualSizeMm.width * contract.emitter.localPositionNormalized[0],
    y: contract.visualSizeMm.depth * contract.emitter.localPositionNormalized[1],
    z: contract.visualSizeMm.height * contract.emitter.localPositionNormalized[2]
  };
}

export interface UnderCabProfileResult {
  readonly itemId: string;
  readonly hostModuleId: string;
  readonly profileDefinitionId: string;
  readonly mount: string;
  readonly profileAngleDeg: number;
  readonly visualSizeMm: { readonly width: number; readonly height: number; readonly depth: number };
  readonly colorTemperatureK: number;
  readonly emitterDirection: Vec3;
  readonly worldOriginMm: Vec3;
  readonly worldRearTopMm: Vec3;
  readonly hasActualAreaLight: true;
  readonly bloomIsSupplementary: true;
}

export function applyFh06UnderCabProfile(
  adapter: ThreeSceneAdapter,
  registry: ThreeMaterialRegistry,
  scene: ScenePackage,
  contract: UnderCabLightContract
): UnderCabProfileResult {
  const entityGroup = adapter.entityGroups.get(contract.itemId);
  if (!entityGroup) throw new Error(`UNDERCAB_ENTITY_GROUP_MISSING:${contract.itemId}`);
  const hostWorld = resolveWorldTransforms(scene).get(contract.hostModuleId);
  if (!hostWorld) throw new Error(`UNDERCAB_HOST_WORLD_MISSING:${contract.hostModuleId}`);

  disposeGeometryTree(entityGroup);
  entityGroup.clear();
  const worldTransform = composeTransforms(hostWorld, contract.localTransform);
  applySceneTransform(entityGroup, worldTransform);
  entityGroup.userData.visualRefinement = "fh06-2-rear-corner-profile-v1";
  entityGroup.userData.profileDefinitionId = contract.profileDefinitionId;
  entityGroup.userData.profileMount = contract.mount;
  entityGroup.userData.profileAngleDeg = contract.profileAngleDeg;
  entityGroup.userData.legacyEnvelopeMm = { ...contract.provenance.legacyEnvelopeMm };

  const sourceInox = registry.materialByDefinitionId("inox-brushed") as MeshStandardMaterial;
  const housingMaterial = sourceInox.clone();
  housingMaterial.name = `${contract.profileDefinitionId}/aluminum`;
  housingMaterial.side = DoubleSide;
  const housing = new Mesh(
    triangularPrism(contract.visualSizeMm.width, contract.visualSizeMm.depth, contract.visualSizeMm.height),
    housingMaterial
  );
  housing.name = `${contract.profileDefinitionId}/housing`;
  housing.castShadow = true;
  housing.receiveShadow = true;
  entityGroup.add(housing);

  const sourceOpal = registry.materialByDefinitionId("under-cab-opal-3000k") as MeshStandardMaterial;
  const opalMaterial = sourceOpal.clone();
  opalMaterial.name = `${contract.profileDefinitionId}/opal-diffuser`;
  opalMaterial.side = DoubleSide;
  const diffuser = new Mesh(diffuserGeometry(contract), opalMaterial);
  diffuser.name = `${contract.profileDefinitionId}/diffuser`;
  diffuser.layers.enable(BLOOM_LAYER);
  diffuser.userData.semanticEmitterSurface = true;
  diffuser.userData.bloomSupplementary = true;
  entityGroup.add(diffuser);

  const color = kelvinToColor(contract.emitter.colorTemperatureK);
  const light = new RectAreaLight(
    color,
    contract.emitter.relativeIntensity * 140,
    contract.emitter.emittingWidthMm,
    contract.emitter.emittingHeightMm
  );
  light.name = `${contract.profileDefinitionId}/area-light`;
  light.castShadow = false;
  light.position.copy(sceneVectorToThree(localEmitterPoint(contract)));
  const directionThree = sceneDirectionToThree(contract.emitter.localDirection);
  light.lookAt(light.position.clone().add(directionThree));
  light.userData.colorTemperatureK = contract.emitter.colorTemperatureK;
  light.userData.localDirection = { ...contract.emitter.localDirection };
  light.userData.bloomIndependent = true;
  entityGroup.add(light);

  const worldOriginMm = worldTransform.translationMm;
  const worldRearTopMm = {
    x: worldOriginMm.x + contract.visualSizeMm.width,
    y: worldOriginMm.y + contract.visualSizeMm.depth,
    z: worldOriginMm.z + contract.visualSizeMm.height
  };
  return {
    itemId: contract.itemId,
    hostModuleId: contract.hostModuleId,
    profileDefinitionId: contract.profileDefinitionId,
    mount: contract.mount,
    profileAngleDeg: contract.profileAngleDeg,
    visualSizeMm: { ...contract.visualSizeMm },
    colorTemperatureK: contract.emitter.colorTemperatureK,
    emitterDirection: { ...contract.emitter.localDirection },
    worldOriginMm,
    worldRearTopMm,
    hasActualAreaLight: true,
    bloomIsSupplementary: true
  };
}
