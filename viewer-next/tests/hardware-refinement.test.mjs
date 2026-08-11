import assert from "node:assert/strict";
import test from "node:test";
import {
  currentHardwareAnchors,
  currentHardwareDefinitions,
  currentSceneBase,
  module03WithSink,
  resolveHardwareAnchors,
  setVisibilityIntent
} from "@mobilipresenter/scene-core";
import { BoxGeometry, MeshBasicMaterial, Vector3 } from "three";
import { styleAnchorAppearance } from "../dist-ts/src/fixtures/style-anchor.js";
import {
  HARDWARE_REFINEMENT_ID,
  applyHardwareRefinement,
  createHardwareHandle
} from "../dist-ts/src/renderer/three/hardware-refinement.js";
import { ThreeMaterialRegistry } from "../dist-ts/src/renderer/three/materials.js";
import { auditRenderOwnership } from "../dist-ts/src/renderer/three/ownership.js";
import { buildThreeScene, syncThreeVisibility } from "../dist-ts/src/renderer/three/scene-adapter.js";
import { sceneVectorToThree } from "../dist-ts/src/renderer/three/coordinates.js";

function build() {
  const registry = new ThreeMaterialRegistry(styleAnchorAppearance);
  const adapter = buildThreeScene(currentSceneBase, (entityId, slot) => registry.resolve(entityId, slot));
  return { registry, adapter };
}

function effectivelyVisible(object) {
  let current = object;
  while (current) {
    if (!current.visible) return false;
    current = current.parent;
  }
  return true;
}

test("current hardware anchors materialize one owned Tango handle each at the exact metric anchor", () => {
  const { registry, adapter } = build();
  const result = applyHardwareRefinement(adapter, registry, currentSceneBase);
  assert.equal(result.refinementId, HARDWARE_REFINEMENT_ID);
  assert.equal(result.anchorCount, 6);
  assert.equal(result.createdCount, 6);
  assert.equal(result.reusedCount, 0);
  assert.deepEqual(result.hardwareDefinitionIds, ["tango-128"]);

  const host = adapter.entityGroups.get(module03WithSink.id);
  assert.ok(host);
  const expected = new Map(resolveHardwareAnchors(currentSceneBase, currentHardwareAnchors).map(value => [value.anchorId, value]));
  for (const anchor of currentHardwareAnchors) {
    const root = host.getObjectByName(`hardware:${anchor.id}`);
    assert.ok(root, anchor.id);
    assert.equal(root.parent, host);
    assert.equal(root.userData.hardwareDefinitionId, "tango-128");
    assert.equal(root.children.length, 3);
    root.updateWorldMatrix(true, true);
    const actualWorld = root.getWorldPosition(new Vector3());
    const expectedWorld = sceneVectorToThree(expected.get(anchor.id).worldMm);
    assert.ok(actualWorld.distanceTo(expectedWorld) <= 0.01, `${anchor.id}: ${actualWorld.distanceTo(expectedWorld)} mm`);
  }
  assert.equal(auditRenderOwnership(adapter).pass, true);
  registry.dispose();
});

test("Tango geometry preserves 128mm mounts, 160mm bar and 22mm physical standoff", () => {
  const definition = currentHardwareDefinitions.find(value => value.id === "tango-128");
  const anchor = currentHardwareAnchors[0];
  assert.ok(definition && definition.family === "bar-handle");
  assert.ok(anchor);
  const material = new MeshBasicMaterial();
  const root = createHardwareHandle(definition, anchor, material);
  const bar = root.getObjectByName("bar");
  const supportA = root.getObjectByName("support-a");
  const supportB = root.getObjectByName("support-b");
  assert.ok(bar?.geometry instanceof BoxGeometry);
  assert.ok(supportA?.geometry instanceof BoxGeometry);
  assert.ok(supportB?.geometry instanceof BoxGeometry);
  assert.equal(bar.geometry.parameters.width, 160);
  assert.equal(bar.geometry.parameters.height, 11);
  assert.equal(bar.geometry.parameters.depth, 7);
  assert.equal(Math.abs(supportB.position.x - supportA.position.x), 128);
  const panelPlaneZ = -anchor.normalOffsetMm;
  assert.equal(supportA.position.z - definition.standoffDepthMm / 2, panelPlaneZ);
  assert.equal(bar.position.z - definition.barDepthMm / 2, panelPlaneZ + 22);
  root.traverse(object => object.geometry?.dispose?.());
  material.dispose();
});

test("Rigato point family is renderable without activating it in the current anchor set", () => {
  const definition = currentHardwareDefinitions.find(value => value.id === "rigato-point");
  const baseAnchor = currentHardwareAnchors[0];
  assert.ok(definition && definition.family === "point-handle");
  assert.ok(baseAnchor);
  assert.equal(currentHardwareAnchors.some(anchor => anchor.hardwareDefinitionId === "rigato-point"), false);
  const anchor = { ...baseAnchor, hardwareDefinitionId: "rigato-point" };
  const material = new MeshBasicMaterial();
  const root = createHardwareHandle(definition, anchor, material);
  assert.equal(root.children.length, 1);
  assert.equal(root.userData.hardwareFamily, "point-handle");
  assert.equal(root.userData.radiusMm, 10);
  assert.equal(root.userData.depthMm, 25);
  root.traverse(object => object.geometry?.dispose?.());
  material.dispose();
});

test("hardware refinement is idempotent and host visibility controls every handle", () => {
  const { registry, adapter } = build();
  const first = applyHardwareRefinement(adapter, registry, currentSceneBase);
  const host = adapter.entityGroups.get(module03WithSink.id);
  assert.ok(host);
  const childCount = host.children.length;
  const second = applyHardwareRefinement(adapter, registry, currentSceneBase);
  assert.equal(first.createdCount, 6);
  assert.equal(second.createdCount, 0);
  assert.equal(second.reusedCount, 6);
  assert.equal(host.children.length, childCount);

  const hidden = setVisibilityIntent(currentSceneBase, module03WithSink.id, "off");
  syncThreeVisibility(adapter, hidden);
  for (const anchor of currentHardwareAnchors) {
    const root = host.getObjectByName(`hardware:${anchor.id}`);
    assert.ok(root);
    assert.equal(effectivelyVisible(root), false);
  }
  registry.dispose();
});
