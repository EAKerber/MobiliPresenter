import assert from "node:assert/strict";
import test from "node:test";
import {
  currentAppearance,
  currentHardwareAnchors,
  currentSceneBase,
  sceneGeometryDigest
} from "@mobilipresenter/scene-core";
import { Group, Mesh, Vector3 } from "three";
import {
  CABINET_FRONT_EDGE_BEVEL_MM,
  CABINET_FRONT_EDGE_ENVELOPE_TOLERANCE_MM,
  CABINET_FRONT_EDGE_RESPONSE_ID,
  applyCabinetFrontEdgeResponse
} from "../dist-ts/src/renderer/three/cabinet-front-edge.js";
import { applyFh06FrontReadability } from "../dist-ts/src/renderer/three/front-readability.js";
import { attachCurrentHardware } from "../dist-ts/src/renderer/three/hardware.js";
import { ThreeMaterialRegistry } from "../dist-ts/src/renderer/three/materials.js";
import { buildThreeScene } from "../dist-ts/src/renderer/three/scene-adapter.js";

function frontBindings() {
  return currentSceneBase.modules.flatMap(module =>
    module.geometry
      .filter(primitive => primitive.primitive === "box" && primitive.role === "front")
      .map(primitive => ({ module, primitive }))
  );
}

function meshFor(adapter, moduleId, primitiveId) {
  const moduleGroup = adapter.entityGroups.get(moduleId);
  assert.ok(moduleGroup instanceof Group, `missing module group ${moduleId}`);
  const primitiveGroup = moduleGroup.getObjectByName(primitiveId);
  assert.ok(primitiveGroup instanceof Group, `missing primitive group ${primitiveId}`);
  const mesh = primitiveGroup.getObjectByName(`${primitiveId}/mesh`);
  assert.ok(mesh instanceof Mesh, `missing mesh ${primitiveId}`);
  return mesh;
}

test("cabinet front edge response preserves every authoritative front envelope and Scene Core digest", () => {
  const registry = new ThreeMaterialRegistry(currentAppearance);
  const adapter = buildThreeScene(currentSceneBase, (entityId, slot) => registry.resolve(entityId, slot));
  const before = sceneGeometryDigest(currentSceneBase);
  const bindings = frontBindings();
  const result = applyCabinetFrontEdgeResponse(adapter, currentSceneBase);

  assert.equal(result.refinementId, CABINET_FRONT_EDGE_RESPONSE_ID);
  assert.equal(result.bevelMm, CABINET_FRONT_EDGE_BEVEL_MM);
  assert.equal(result.envelopeToleranceMm, CABINET_FRONT_EDGE_ENVELOPE_TOLERANCE_MM);
  assert.ok(CABINET_FRONT_EDGE_ENVELOPE_TOLERANCE_MM < 0.01);
  assert.equal(result.totalFrontCount, bindings.length);
  assert.equal(result.refinedFrontCount, bindings.length);
  assert.equal(result.preservedExistingBevelCount, 0);
  assert.equal(result.alreadyRefinedCount, 0);
  assert.equal(result.geometryDigestUnchanged, true);
  assert.equal(sceneGeometryDigest(currentSceneBase), before);

  for (const { module, primitive } of bindings) {
    const mesh = meshFor(adapter, module.id, primitive.id);
    mesh.geometry.computeBoundingBox();
    const size = mesh.geometry.boundingBox.getSize(new Vector3());
    assert.ok(
      Math.abs(size.x - primitive.sizeMm.width) <= CABINET_FRONT_EDGE_ENVELOPE_TOLERANCE_MM,
      `${primitive.id}: width changed`
    );
    assert.ok(
      Math.abs(size.y - primitive.sizeMm.height) <= CABINET_FRONT_EDGE_ENVELOPE_TOLERANCE_MM,
      `${primitive.id}: height changed`
    );
    assert.ok(
      Math.abs(size.z - primitive.sizeMm.depth) <= CABINET_FRONT_EDGE_ENVELOPE_TOLERANCE_MM,
      `${primitive.id}: depth changed`
    );
    assert.equal(mesh.userData.cabinetFrontEdgeResponse, CABINET_FRONT_EDGE_RESPONSE_ID);
    assert.equal(mesh.userData.cabinetFrontEdgeBevelMm, CABINET_FRONT_EDGE_BEVEL_MM);
  }

  registry.dispose();
});

test("composition order preserves S8 drawer bevels and makes H6 idempotent on all remaining fronts", () => {
  const registry = new ThreeMaterialRegistry(currentAppearance);
  const adapter = buildThreeScene(currentSceneBase, (entityId, slot) => registry.resolve(entityId, slot));
  applyFh06FrontReadability(adapter, registry, currentSceneBase);

  const bindings = frontBindings();
  const geometryByPrimitive = new Map(
    bindings.map(({ module, primitive }) => [primitive.id, meshFor(adapter, module.id, primitive.id).geometry])
  );
  const second = applyCabinetFrontEdgeResponse(adapter, currentSceneBase);

  assert.equal(second.totalFrontCount, bindings.length);
  assert.equal(second.refinedFrontCount, 0);
  assert.equal(second.preservedExistingBevelCount, 4);
  assert.equal(second.alreadyRefinedCount, bindings.length - 4);

  for (const { module, primitive } of bindings) {
    const mesh = meshFor(adapter, module.id, primitive.id);
    assert.equal(mesh.geometry, geometryByPrimitive.get(primitive.id), `${primitive.id}: geometry rebuilt on second pass`);
    if (primitive.id.includes("/front/drawer-")) {
      assert.equal(mesh.userData.visualRefinement, "fh06-s8-front-bevel-v1");
    } else {
      assert.equal(mesh.userData.cabinetFrontEdgeResponse, CABINET_FRONT_EDGE_RESPONSE_ID);
    }
  }

  registry.dispose();
});

test("hardware still attaches after generalized front edge refinement without moving anchor authority", () => {
  const registry = new ThreeMaterialRegistry(currentAppearance);
  const adapter = buildThreeScene(currentSceneBase, (entityId, slot) => registry.resolve(entityId, slot));
  applyFh06FrontReadability(adapter, registry, currentSceneBase);
  const hardware = attachCurrentHardware(adapter, currentSceneBase, registry);

  assert.equal(hardware.handleCount, currentHardwareAnchors.length);
  assert.equal(hardware.refinementId, "hardware-anchors-parametric-v1");
  registry.dispose();
});
