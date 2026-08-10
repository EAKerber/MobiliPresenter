import {
  BoxGeometry,
  Group,
  Mesh,
  type Material
} from "three";
import type { ThreeSceneAdapter } from "./scene-adapter.js";
import type { ThreeMaterialRegistry } from "./materials.js";

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
  const housingHeight = Math.min(92, height * 0.46);
  const housingDepth = depth * 0.54;
  proxy.add(part(width * 0.94, housingHeight, housingDepth, inox, width * 0.03, depth - housingDepth, height - housingHeight));

  const visorHeight = Math.min(34, height * 0.18);
  const visorDepth = depth * 0.58;
  proxy.add(part(width, visorHeight, visorDepth, inox, 0, -12, height * 0.34));
  proxy.add(part(width * 0.96, Math.min(18, visorHeight * 0.55), 18, dark, width * 0.02, -30, height * 0.34 + 3));

  const filterDepth = depth * 0.48;
  const filterWidth = width * 0.43;
  const filterZ = height * 0.28;
  proxy.add(part(filterWidth, 7, filterDepth, dark, width * 0.05, depth * 0.03, filterZ));
  proxy.add(part(filterWidth, 7, filterDepth, dark, width * 0.52, depth * 0.03, filterZ));

  const ledWidth = Math.max(28, width * 0.055);
  proxy.add(part(ledWidth, 4, 12, emissive, width * 0.18, -2, filterZ - 1));
  proxy.add(part(ledWidth, 4, 12, emissive, width * 0.76, -2, filterZ - 1));
  proxy.userData.visualRefinement = "fh06-slim-retractable-hood-v1";
}

export function applyFh06VisualRefinements(
  adapter: ThreeSceneAdapter,
  registry: ThreeMaterialRegistry
): void {
  refineHood(adapter, registry);
}
