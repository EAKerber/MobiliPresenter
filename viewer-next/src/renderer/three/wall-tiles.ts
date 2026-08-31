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
const RELIEF_TILE_OFFSET_MM = 1.05;
const RELIEF_GROUT_OFFSET_MM = 0.35;
const RELIEF_MM = RELIEF_TILE_OFFSET_MM - RELIEF_GROUT_OFFSET_MM;

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

export interface FullWallTileOptions {
  readonly microRelief?: boolean;
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

function gridCuts(origin: Vec3, axis: Vec3, lengthMm: number): number[] {
  const cuts = [0];
  let value = firstWorldGridOffset(origin, axis, TILE_SIZE_MM);
  while (value <= 0) value += TILE_SIZE_MM;
  for (; value < lengthMm; value += TILE_SIZE_MM) cuts.push(value);
  cuts.push(lengthMm);
  return cuts;
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

function buildLegacySurfaceGroup(
  surface: TileSurface,
  tileMaterial: MeshStandardMaterial,
  groutMaterial: MeshStandardMaterial
): Group {
  const group = new Group();
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

function buildReliefSurfaceGroup(
  surface: TileSurface,
  tileMaterial: MeshStandardMaterial,
  groutMaterial: MeshStandardMaterial
): Group {
  const group = new Group();
  const backing = new Mesh(
    surfaceQuad(surface, 0, surface.uLengthMm, 0, surface.vLengthMm, RELIEF_GROUT_OFFSET_MM),
    groutMaterial
  );
  backing.name = `${surface.id}/tile-base`;
  backing.receiveShadow = true;
  group.add(backing);

  const uCuts = gridCuts(surface.originMm, surface.uAxis, surface.uLengthMm);
  const vCuts = gridCuts(surface.originMm, surface.vAxis, surface.vLengthMm);
  for (let uIndex = 0; uIndex < uCuts.length - 1; uIndex += 1) {
    for (let vIndex = 0; vIndex < vCuts.length - 1; vIndex += 1) {
      const u0 = uCuts[uIndex]! + GROUT_MM / 2;
      const u1 = uCuts[uIndex + 1]! - GROUT_MM / 2;
      const v0 = vCuts[vIndex]! + GROUT_MM / 2;
      const v1 = vCuts[vIndex + 1]! - GROUT_MM / 2;
      if (u1 <= u0 || v1 <= v0) continue;
      const tile = new Mesh(
        surfaceQuad(surface, u0, u1, v0, v1, RELIEF_TILE_OFFSET_MM),
        tileMaterial
      );
      tile.name = `${surface.id}/tile-${uIndex}-${vIndex}`;
      tile.receiveShadow = true;
      group.add(tile);
    }
  }
  return group;
}

function buildSurfaceGroup(
  surface: TileSurface,
  tileMaterial: MeshStandardMaterial,
  groutMaterial: MeshStandardMaterial,
  microRelief: boolean
): Group {
  const group = microRelief
    ? buildReliefSurfaceGroup(surface, tileMaterial, groutMaterial)
    : buildLegacySurfaceGroup(surface, tileMaterial, groutMaterial);
  group.name = surface.id;
  group.userData.tileSurfaceId = surface.id;
  group.userData.status = surface.status;
  group.userData.evidenceRefs = [...surface.evidenceRefs];
  group.userData.tileGridMm = TILE_SIZE_MM;
  group.userData.groutMm = GROUT_MM;
  group.userData.microRelief = microRelief;
  group.userData.reliefMm = microRelief ? RELIEF_MM : 0;
  return group;
}

export interface FullWallTileResult {
  readonly groupName: string;
  readonly surfaceCount: number;
  readonly confirmedSurfaceCount: number;
  readonly inferredSurfaceCount: number;
  readonly tileGridMm: number;
  readonly groutMm: number;
  readonly microRelief: boolean;
  readonly reliefMm: number;
  readonly surfaceIds: readonly string[];
}

export function applyFh06FullWallTiles(
  adapter: ThreeSceneAdapter,
  scene: ScenePackage,
  options: FullWallTileOptions = {}
): FullWallTileResult {
  const previous = adapter.scene.getObjectByName("fh06-full-wall-tile");
  if (previous) adapter.scene.remove(previous);

  const microRelief = options.microRelief === true;
  const surfaces = [...environmentTileSurfaces(scene), inferredLaundryWall()];
  const tileMaterial = new MeshStandardMaterial({
    color: 0xebe7df,
    roughness: microRelief ? 0.54 : 0.62,
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
  root.userData.microRelief = microRelief;
  root.userData.reliefMm = microRelief ? RELIEF_MM : 0;
  root.userData.mappingPolicy = "world-phase-continuous-per-surface-axis";

  for (const surface of surfaces) root.add(buildSurfaceGroup(surface, tileMaterial, groutMaterial, microRelief));
  adapter.scene.add(root);

  return {
    groupName: root.name,
    surfaceCount: surfaces.length,
    confirmedSurfaceCount: surfaces.filter(surface => surface.status === "confirmed").length,
    inferredSurfaceCount: surfaces.filter(surface => surface.status === "inferred").length,
    tileGridMm: TILE_SIZE_MM,
    groutMm: GROUT_MM,
    microRelief,
    reliefMm: microRelief ? RELIEF_MM : 0,
    surfaceIds: surfaces.map(surface => surface.id)
  };
}
