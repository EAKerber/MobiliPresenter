import assert from "node:assert/strict";
import test from "node:test";
import {
  currentHardwareAnchors,
  currentHardwareDefinitions,
  currentSceneBase,
  module03WithSink
} from "@mobilipresenter/scene-core";
import { Box3, Mesh, MeshStandardMaterial, Vector3 } from "three";
import { styleAnchorAppearance } from "../dist-ts/src/fixtures/style-anchor.js";
import {
  attachCurrentHardware,
  createHardwareVisual
} from "../dist-ts/src/renderer/three/hardware.js";
import { ThreeMaterialRegistry } from "../dist-ts/src/renderer/three/materials.js";
import { selectableModuleIdForObject } from "../dist-ts/src/renderer/three/ownership.js";
import { buildThreeScene } from "../dist-ts/src/renderer/three/scene-adapter.js";

function sizeOf(object) {
  return new Box3().setFromObject(object).getSize(new Vector3());
}

function disposeVisual(root) {
  root.traverse(object => {
    if (object instanceof Mesh) object.geometry.dispose();
  });
}

test("Tango 128 recipe preserves physical bar, mount spacing and standoff", () => {
  const definition = currentHardwareDefinitions.find(item => item.id === "tango-128");
  assert.ok(definition && definition.family === "bar-handle");
  const material = new MeshStandardMaterial();

  const horizontal = createHardwareVisual(definition, "horizontal", material);
  const horizontalSize = sizeOf(horizontal);
  assert.ok(Math.abs(horizontalSize.x - 160) < 1e-9);
  assert.ok(Math.abs(horizontalSize.y - 11) < 1e-9);
  assert.ok(Math.abs(horizontalSize.z - 29) < 1e-9);
  assert.deepEqual(
    horizontal.children.filter(child => child.name.startsWith("support")).map(child => child.position.x).sort((a, b) => a - b),
    [-64, 64]
  );

  const vertical = createHardwareVisual(definition, "vertical", material);
  const verticalSize = sizeOf(vertical);
  assert.ok(Math.abs(verticalSize.x - 11) < 1e-9);
  assert.ok(Math.abs(verticalSize.y - 160) < 1e-9);
  assert.ok(Math.abs(verticalSize.z - 29) < 1e-9);

  disposeVisual(horizontal);
  disposeVisual(vertical);
  material.dispose();
});

test("Rigato point recipe preserves 20 mm diameter and 25 mm projection", () => {
  const definition = currentHardwareDefinitions.find(item => item.id === "rigato-point");
  assert.ok(definition && definition.family === "point-handle");
  const material = new MeshStandardMaterial();
  const visual = createHardwareVisual(definition, "horizontal", material);
  const size = sizeOf(visual);
  assert.ok(Math.abs(size.x - 20) < 1e-9);
  assert.ok(Math.abs(size.y - 20) < 1e-9);
  assert.ok(Math.abs(size.z - 25) < 1e-9);
  disposeVisual(visual);
  material.dispose();
});

test("current hardware is attached to front primitive groups at metric UV anchors", () => {
  const registry = new ThreeMaterialRegistry(styleAnchorAppearance);
  const adapter = buildThreeScene(currentSceneBase, (entityId, slot) => registry.resolve(entityId, slot));
  const diagnostics = attachCurrentHardware(adapter, currentSceneBase, registry);

  assert.equal(diagnostics.handleCount, 6);
  assert.deepEqual(diagnostics.anchorIds, currentHardwareAnchors.map(anchor => anchor.id));

  const drawerAnchor = currentHardwareAnchors.find(anchor => anchor.id.endsWith("drawer-1"));
  assert.ok(drawerAnchor);
  const moduleGroup = adapter.entityGroups.get(module03WithSink.id);
  assert.ok(moduleGroup);
  const drawerFront = moduleGroup.getObjectByName(drawerAnchor.hostGeometryId);
  assert.ok(drawerFront);
  const drawerHandle = drawerFront.getObjectByName(drawerAnchor.id);
  assert.ok(drawerHandle);
  assert.deepEqual(drawerHandle.position.toArray(), [198, 93.5, 4]);

  const doorAnchor = currentHardwareAnchors.find(anchor => anchor.id.endsWith("door-center"));
  assert.ok(doorAnchor);
  const doorFront = moduleGroup.getObjectByName(doorAnchor.hostGeometryId);
  assert.ok(doorFront);
  const doorHandle = doorFront.getObjectByName(doorAnchor.id);
  assert.ok(doorHandle);
  assert.ok(Math.abs(doorHandle.position.x - (405.339 - 43.5)) < 1e-9);
  assert.equal(doorHandle.position.y, 657);
  assert.equal(doorHandle.position.z, 4);

  registry.dispose();
});

test("a handle mesh remains owned and selectable as module 03", () => {
  const registry = new ThreeMaterialRegistry(styleAnchorAppearance);
  const adapter = buildThreeScene(currentSceneBase, (entityId, slot) => registry.resolve(entityId, slot));
  attachCurrentHardware(adapter, currentSceneBase, registry);
  const moduleGroup = adapter.entityGroups.get(module03WithSink.id);
  assert.ok(moduleGroup);
  const anchor = currentHardwareAnchors[0];
  const front = moduleGroup.getObjectByName(anchor.hostGeometryId);
  const handle = front?.getObjectByName(anchor.id);
  assert.ok(handle);
  let handleMesh = null;
  handle.traverse(object => {
    if (handleMesh === null && object instanceof Mesh) handleMesh = object;
  });
  assert.ok(handleMesh);
  assert.equal(selectableModuleIdForObject(adapter, currentSceneBase, handleMesh), module03WithSink.id);
  registry.dispose();
});
