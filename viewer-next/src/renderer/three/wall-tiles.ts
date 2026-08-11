import {
  add,
  composeTransforms,
  dot,
  mul,
  resolveWorldTransforms,
  rotateVector,
  type ScenePackage,
  type Vec3
} from "@mobilipresenter/scene-core";
import {
  BufferGeometry,
  Float32BufferAttribute,
  Group,
  Mesh,
  MeshStandardMaterial
} from "three";
import { sceneVectorToThree } from "./coordinates.js";
import type { ThreeSceneAdapter } from "./scene-adapter.js";

const TILE_SIZE_MM = 400;
const GROUT_MM = 2;
const SURFACE_OFFSET_MM = 0.8;
const GROUT_OFFSET_MM = 1.05;

interface TileSurface {
  readonly id: string;
  readonly originMm: Vec3;
  readonly uAxis: Vec3;
  readonly vAxis: Vec3;
  readonly normal: Vec3;
  readonly uLengthMm: number;
  readonly vLengthMm: number;
  readonly status: "confirmed" | "inferred";
  readonly evidenceRefs: readonly string[];
}

function pointOnSurface(surface: TileSurface, uMm: number, vMm: number, normalOffsetMm: number): Vec3 {
  return add(
    add(
      add(surface.originMm, mul(surface.uAxis, uMm)),
      mul(surface.vAxis, vMm)
    ),
    mul(surface.normal, normalOffsetMm)
  );
}

function quadGeometry(points: readonly [Vec3, Vec3, Vec3, Vec3]): BufferGeometry {
  const [p0, p1, p2, p3] = points.map(sceneVectorToThree) as [
    ReturnType<typeof sceneVectorToThree>,
    ReturnType<typeof sceneVectorToThree>,
    ReturnType<typeof sceneVectorToThree>,
    ReturnType<typeof sceneVectorToThree>
  ];
  const positions = [p0, p1, p2, p0, p2, p3].flatMap(point => [point.x, point.y, point.z]);
  const geometry = new BufferGeometry();
  geometry.setAttribute("position", new Float32BufferAttribute(positions, 3));
  geometry.computeVertexNormals();
  geometry.computeBoundingBox();
  geometry.computeBoundingSphere();
  return geometry;
}

function surfaceQuad(
  surface: TileSurface,
  u0: number,
  u1: number,
  v0: number,
  v1: number,
  normalOffsetMm: number
): BufferGeometry {
  return quadGeometry([
    pointOnSurface(surface, u0, v0, normalOffsetMm),
    pointOnSurface(surface, u1, v0, normalOffsetMm),
    pointOnSurface(surface, u1, v1, normalOffsetMm),
    pointOnSurface(surface, u0, v1, normalOffsetMm)
  ]);
}

function firstWorldGridOffset(origin: Vec3, axis: Vec3, sizeMm: number): number {
  const coordinate = dot(origin, axis);
  const firstWorldCoordinate = Math.ceil((coordinate + 1e-7) / sizeMm) * sizeMm;
  return firstWorldCoordinate - coordinate;
}

function environmentTileSurfaces(scene: ScenePackage): TileSurface[] {
  const world = resolveWorldTransforms(scene);
  const surfaces: TileSurface[] = [];
  for (const environment of scene.environment) {
    const environmentWorld = world.get(environment.id);
    if (!environmentWorld) throw new Error(`TILE_ENVIRONMENT_WORLD_MISSING:${environment.id}`);
    for (const primitive of environment.geometry) {
      if (primitive.primitive !== "face" || primitive.materialSlot !== "wall") continue;
      const primitiveWorld = composeTransforms(environmentWorld, primitive.localTransform);
      surfaces.push({
        id: `${primitive.id}/tile-surface`,
        originMm: primitiveWorld.translationMm,
        uAxis: rotateVector(primitiveWorld.rotation, primitive.uAxis),
        vAxis: rotateVector(primitiveWorld.rotation, primitive.vAxis),
        normal: rotateVector(primitiveWorld.rotation, primitive.normal),
        uLengthMm: primitive.sizeMm[0],
        vLengthMm: primitive.sizeMm[1],
        status: "confirmed",
        evidenceRefs: primitive.sourceBindingIds
      });
    }
  }
  return surfaces;
}

function inferredLaundryWall(): TileSurface {
  return {
    id: "scene/traditional/environment/inferred-laundry-wall/tile-surface",
    originMm: { x: 1568.684, y: 8638.827, z: 0 },
    uAxis: { x: 1, y: 0, z: 0 },
    vAxis: { x: 0, y: 0, z: 1 },
    normal: { x: 0, y: -1, z: 0 },
    uLengthMm: 763.25,
    vLengthMm: 2601.63,
    status: "inferred",
    evidenceRefs: [
      "promob-dxf:module01-back-plane-y8638.827",
      "promob-envelope:washer-back-plane-y8638.81",
      "user-rule:tile-covers-complete-wall"
    ]
  };
}

function buildSurfaceGroup(
  surface: TileSurface,
  tileMaterial: MeshStandardMaterial,
  groutMaterial: MeshStandardMaterial
): Group {
  const group = new Group();
  group.name = surface.id;
  group.userData.tileSurfaceId = surface.id;
  group.userData.status = surface.status;
  group.userData.evidenceRefs = [...surface.evidenceRefs];
  group.userData.tileGridMm = TILE_SIZE_MM;
  group.userData.groutMm = GROUT_MM;

  const base = new Mesh(
    surfaceQuad(surface, 0, surface.uLengthMm, 0, surface.vLengthMm, SURFACE_OFFSET_MM),
    tileMaterial
  );
  base.name = `${surface.id}/tile-base`;
  base.receiveShadow = true;
  group.add(base);

  for (
    let u = firstWorldGridOffset(surface.originMm, surface.uAxis, TILE_SIZE_MM);
    u > 0 && u < surface.uLengthMm;
    u += TILE_SIZE_MM
  ) {
    const u0 = Math.max(0, u - GROUT_MM / 2);
    const u1 = Math.min(surface.uLengthMm, u + GROUT_MM / 2);
    const grout = new Mesh(
      surfaceQuad(surface, u0, u1, 0, surface.vLengthMm, GROUT_OFFSET_MM),
      groutMaterial
    );
    grout.name = `${surface.id}/grout-u-${Math.round(u * 1000)}`;
    group.add(grout);
  }

  for (
    let v = firstWorldGridOffset(surface.originMm, surface.vAxis, TILE_SIZE_MM);
    v > 0 && v < surface.vLengthMm;
    v += TILE_SIZE_MM
  ) {
    const v0 = Math.max(0, v - GROUT_MM / 2);
    const v1 = Math.min(surface.vLengthMm, v + GROUT_MM / 2);
    const grout = new Mesh(
      surfaceQuad(surface, 0, surface.uLengthMm, v0, v1, GROUT_OFFSET_MM),
      groutMaterial
    );
    grout.name = `${surface.id}/grout-v-${Math.round(v * 1000)}`;
    group.add(grout);
  }
  return group;
}

export interface FullWallTileResult {
  readonly groupName: string;
  readonly surfaceCount: number;
  readonly confirmedSurfaceCount: number;
  readonly inferredSurfaceCount: number;
  readonly tileGridMm: number;
  readonly groutMm: number;
  readonly surfaceIds: readonly string[];
}

export function applyFh06FullWallTiles(
  adapter: ThreeSceneAdapter,
  scene: ScenePackage
): FullWallTileResult {
  const previous = adapter.scene.getObjectByName("fh06-full-wall-tile");
  if (previous) adapter.scene.remove(previous);

  const surfaces = [...environmentTileSurfaces(scene), inferredLaundryWall()];
  const tileMaterial = new MeshStandardMaterial({
    color: 0xebe7df,
    roughness: 0.62,
    metalness: 0
  });
  tileMaterial.name = "fh06-full-wall-tile/ceramic";
  const groutMaterial = new MeshStandardMaterial({
    color: 0xb7b0a6,
    roughness: 0.96,
    metalness: 0
  });
  groutMaterial.name = "fh06-full-wall-tile/grout";

  const root = new Group();
  root.name = "fh06-full-wall-tile";
  root.userData.appearanceOnly = true;
  root.userData.fullWallCoverage = true;
  root.userData.tileGridMm = TILE_SIZE_MM;
  root.userData.groutMm = GROUT_MM;
  root.userData.mappingPolicy = "world-phase-continuous-per-surface-axis";

  for (const surface of surfaces) root.add(buildSurfaceGroup(surface, tileMaterial, groutMaterial));
  adapter.scene.add(root);

  return {
    groupName: root.name,
    surfaceCount: surfaces.length,
    confirmedSurfaceCount: surfaces.filter(surface => surface.status === "confirmed").length,
    inferredSurfaceCount: surfaces.filter(surface => surface.status === "inferred").length,
    tileGridMm: TILE_SIZE_MM,
    groutMm: GROUT_MM,
    surfaceIds: surfaces.map(surface => surface.id)
  };
}
