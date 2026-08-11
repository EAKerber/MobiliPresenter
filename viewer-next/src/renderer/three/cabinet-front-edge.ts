import {
  sceneGeometryDigest,
  type BoxGeometry,
  type ModuleGeometry,
  type ScenePackage
} from "@mobilipresenter/scene-core";
import { Box3, Group, Mesh, Vector3 } from "three";
import { RoundedBoxGeometry } from "three/examples/jsm/geometries/RoundedBoxGeometry.js";
import type { ThreeSceneAdapter } from "./scene-adapter.js";

export const CABINET_FRONT_EDGE_RESPONSE_ID = "cabinet-front-edge-bevel-v1" as const;
export const CABINET_FRONT_EDGE_BEVEL_MM = 1.25 as const;
const CABINET_FRONT_EDGE_SEGMENTS = 3;
const EXISTING_S8_BEVEL_ID = "fh06-s8-front-bevel-v1";

interface FrontBoxPrimitive extends BoxGeometry {
  readonly primitive: "box";
  readonly role: "front";
}

interface FrontBoxBinding {
  readonly module: ModuleGeometry;
  readonly primitive: FrontBoxPrimitive;
}

function frontBoxes(scene: ScenePackage): readonly FrontBoxBinding[] {
  return scene.modules
    .flatMap(module => module.geometry
      .filter((primitive): primitive is FrontBoxPrimitive =>
        primitive.primitive === "box" && primitive.role === "front"
      )
      .map(primitive => ({ module, primitive })))
    .sort((a, b) => a.primitive.id.localeCompare(b.primitive.id));
}

function primitiveMesh(adapter: ThreeSceneAdapter, module: ModuleGeometry, primitive: FrontBoxPrimitive): Mesh {
  const moduleGroup = adapter.entityGroups.get(module.id);
  if (!(moduleGroup instanceof Group)) throw new Error(`CABINET_FRONT_MODULE_GROUP_MISSING:${module.id}`);
  const primitiveGroup = moduleGroup.getObjectByName(primitive.id);
  if (!(primitiveGroup instanceof Group)) throw new Error(`CABINET_FRONT_PRIMITIVE_GROUP_MISSING:${primitive.id}`);
  const mesh = primitiveGroup.getObjectByName(`${primitive.id}/mesh`);
  if (!(mesh instanceof Mesh)) throw new Error(`CABINET_FRONT_MESH_MISSING:${primitive.id}`);
  return mesh;
}

function assertEnvelope(mesh: Mesh, primitive: FrontBoxPrimitive): void {
  mesh.geometry.computeBoundingBox();
  const box = mesh.geometry.boundingBox;
  if (!(box instanceof Box3)) throw new Error(`CABINET_FRONT_BOUNDING_BOX_MISSING:${primitive.id}`);
  const size = box.getSize(new Vector3());
  const expected = primitive.sizeMm;
  const tolerance = 1e-6;
  if (
    Math.abs(size.x - expected.width) > tolerance ||
    Math.abs(size.y - expected.height) > tolerance ||
    Math.abs(size.z - expected.depth) > tolerance
  ) {
    throw new Error(
      `CABINET_FRONT_ENVELOPE_CHANGED:${primitive.id}:${size.x},${size.y},${size.z}`
    );
  }
}

export interface CabinetFrontEdgeResponseResult {
  readonly refinementId: typeof CABINET_FRONT_EDGE_RESPONSE_ID;
  readonly bevelMm: typeof CABINET_FRONT_EDGE_BEVEL_MM;
  readonly totalFrontCount: number;
  readonly refinedFrontCount: number;
  readonly preservedExistingBevelCount: number;
  readonly alreadyRefinedCount: number;
  readonly moduleIds: readonly string[];
  readonly geometryDigestUnchanged: boolean;
}

export function applyCabinetFrontEdgeResponse(
  adapter: ThreeSceneAdapter,
  scene: ScenePackage
): CabinetFrontEdgeResponseResult {
  const before = sceneGeometryDigest(scene);
  const bindings = frontBoxes(scene);
  const moduleIds = new Set<string>();
  let refinedFrontCount = 0;
  let preservedExistingBevelCount = 0;
  let alreadyRefinedCount = 0;

  for (const { module, primitive } of bindings) {
    const mesh = primitiveMesh(adapter, module, primitive);
    moduleIds.add(module.id);

    if (mesh.userData.visualRefinement === EXISTING_S8_BEVEL_ID) {
      assertEnvelope(mesh, primitive);
      preservedExistingBevelCount += 1;
      continue;
    }

    if (mesh.userData.cabinetFrontEdgeResponse === CABINET_FRONT_EDGE_RESPONSE_ID) {
      assertEnvelope(mesh, primitive);
      alreadyRefinedCount += 1;
      continue;
    }

    mesh.geometry.dispose();
    const geometry = new RoundedBoxGeometry(
      primitive.sizeMm.width,
      primitive.sizeMm.height,
      primitive.sizeMm.depth,
      CABINET_FRONT_EDGE_SEGMENTS,
      CABINET_FRONT_EDGE_BEVEL_MM
    );
    geometry.userData.visualRefinement = CABINET_FRONT_EDGE_RESPONSE_ID;
    geometry.userData.bevelMm = CABINET_FRONT_EDGE_BEVEL_MM;
    geometry.userData.authoritativeSizeMm = { ...primitive.sizeMm };
    mesh.geometry = geometry;
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    mesh.userData.cabinetFrontEdgeResponse = CABINET_FRONT_EDGE_RESPONSE_ID;
    mesh.userData.cabinetFrontEdgeBevelMm = CABINET_FRONT_EDGE_BEVEL_MM;
    assertEnvelope(mesh, primitive);
    refinedFrontCount += 1;
  }

  const unchanged = sceneGeometryDigest(scene) === before;
  if (!unchanged) throw new Error("CABINET_FRONT_EDGE_MUTATED_SCENE_CORE_GEOMETRY");

  return {
    refinementId: CABINET_FRONT_EDGE_RESPONSE_ID,
    bevelMm: CABINET_FRONT_EDGE_BEVEL_MM,
    totalFrontCount: bindings.length,
    refinedFrontCount,
    preservedExistingBevelCount,
    alreadyRefinedCount,
    moduleIds: [...moduleIds].sort(),
    geometryDigestUnchanged: unchanged
  };
}
