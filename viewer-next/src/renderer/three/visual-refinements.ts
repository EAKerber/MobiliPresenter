import {
  BoxGeometry,
  Group,
  Mesh,
  MeshStandardMaterial,
  type Material,
  type Object3D
} from "three";
import type { ThreeSceneAdapter } from "./scene-adapter.js";
import type { ThreeMaterialRegistry } from "./materials.js";
import { sceneVectorToThree } from "./coordinates.js";

const HOOD_ID = "scene/traditional/appliance/hood";

interface FitData {
  readonly fittedMm: { readonly width: number; readonly height: number; readonly depth: number };
}

function part(
  width: number,
  height: number,
  depth: number,
  material: Material,
  x: number,
  y: number,
  z: number
): Mesh {
  const mesh = new Mesh(new BoxGeometry(width, height, depth), material);
  mesh.position.set(x + width / 2, z + height / 2, -(y + depth / 2));
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  return mesh;
}

function refineHood(adapter: ThreeSceneAdapter, registry: ThreeMaterialRegistry): void {
  const entity = adapter.entityGroups.get(HOOD_ID);
  if (!entity) return;
  const proxy = entity.getObjectByName(`${HOOD_ID}/parametric`) as Group | undefined;
  if (!proxy) return;
  const fit = proxy.userData.fit as FitData | undefined;
  if (!fit) return;

  const { width, height, depth } = fit.fittedMm;
  const inox = registry.materialByDefinitionId("inox-brushed");
  const dark = registry.materialByDefinitionId("dark-metal");
  const emissive = registry.materialByDefinitionId("emissive-warm");

  proxy.clear();

  // Compact rear housing: visually hidden beneath the upper cabinet instead of
  // reading as a full appliance box.
  const housingHeight = Math.min(92, height * 0.46);
  const housingDepth = depth * 0.54;
  proxy.add(part(width * 0.94, housingHeight, housingDepth, inox, width * 0.03, depth - housingDepth, height - housingHeight));

  // Retractable visor/front fascia, the characteristic silhouette of a slim hood.
  const visorHeight = Math.min(34, height * 0.18);
  const visorDepth = depth * 0.58;
  proxy.add(part(width, visorHeight, visorDepth, inox, 0, -12, height * 0.34));
  proxy.add(part(width * 0.96, Math.min(18, visorHeight * 0.55), 18, dark, width * 0.02, -30, height * 0.34 + 3));

  // Two filter panels underneath; a small central gap keeps the object readable.
  const filterDepth = depth * 0.48;
  const filterWidth = width * 0.43;
  const filterZ = height * 0.28;
  proxy.add(part(filterWidth, 7, filterDepth, dark, width * 0.05, depth * 0.03, filterZ));
  proxy.add(part(filterWidth, 7, filterDepth, dark, width * 0.52, depth * 0.03, filterZ));

  // Physical emissive surfaces are small; the semantic emitter still owns the
  // actual light contribution and selective bloom.
  const ledWidth = Math.max(28, width * 0.055);
  proxy.add(part(ledWidth, 4, 12, emissive, width * 0.18, -2, filterZ - 1));
  proxy.add(part(ledWidth, 4, 12, emissive, width * 0.76, -2, filterZ - 1));

  proxy.userData.visualRefinement = "fh06-slim-retractable-hood-v1";
}

function addWallTiles(root: Object3D): void {
  const group = new Group();
  group.name = "fh06-wall-tile-guide";
  group.userData.appearanceOnly = true;
  group.userData.status = "style-inferred";
  group.userData.tileGridMm = 400;

  const material = new MeshStandardMaterial({
    color: 0xd8d5cd,
    roughness: 0.96,
    metalness: 0,
    transparent: true,
    opacity: 0.62,
    depthWrite: false
  });

  const x0 = 3071.739;
  const x1 = 5906.427;
  const z0 = 0;
  const z1 = 2601.63;
  const wallY = 8649.55; // camera-facing side of the authoritative wall plane
  const step = 400;
  const grout = 3;

  for (let x = x0 + step; x < x1; x += step) {
    const mesh = new Mesh(new BoxGeometry(grout, z1 - z0, 1.2), material);
    mesh.position.copy(sceneVectorToThree({ x, y: wallY, z: (z0 + z1) / 2 }));
    mesh.receiveShadow = false;
    group.add(mesh);
  }
  for (let z = z0 + step; z < z1; z += step) {
    const mesh = new Mesh(new BoxGeometry(x1 - x0, grout, 1.2), material);
    mesh.position.copy(sceneVectorToThree({ x: (x0 + x1) / 2, y: wallY, z }));
    mesh.receiveShadow = false;
    group.add(mesh);
  }

  root.add(group);
}

export function applyFh06VisualRefinements(
  adapter: ThreeSceneAdapter,
  registry: ThreeMaterialRegistry
): void {
  refineHood(adapter, registry);
  addWallTiles(adapter.scene);
}
