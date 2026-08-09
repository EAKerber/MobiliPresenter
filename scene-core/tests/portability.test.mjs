import assert from "node:assert/strict";
import test from "node:test";
import { validateScenePackage } from "../dist/src/contracts/invariants.js";
import { compileModuleFromDxfInventory } from "../dist/src/source/dxf.js";
import { portableCompiled, portableInventory, portableScene } from "../dist/src/fixtures/portable-scene.js";

test("second scene compiles from DXF inventory and data bindings without core changes", () => {
  assert.deepEqual(validateScenePackage(portableScene), []);
  assert.deepEqual(portableCompiled.module.dimensions.geometryMm, {
    width: 600,
    height: 720,
    depth: 560
  });
  assert.equal(portableCompiled.module.geometry.length, 2);
  assert.equal(portableCompiled.module.geometry[0]?.localTransform.translationMm.x, 0);
  assert.equal(portableCompiled.module.geometry[1]?.localTransform.translationMm.y, -18);
  assert.equal(portableCompiled.sourceBindings[0]?.sourceSelector.layer, "CABINET_BODY");
});

test("portable fixture contains no current-scene ids or Promob generic LAYER numbers", () => {
  const serialized = JSON.stringify(portableScene);
  assert.equal(serialized.includes("traditional"), false);
  assert.equal(serialized.includes("module-02"), false);
  assert.equal(serialized.includes("module-06"), false);
  assert.equal(serialized.includes("LAYER"), false);
});

test("source fingerprint mismatch blocks compilation before geometry is trusted", () => {
  assert.throws(() => compileModuleFromDxfInventory(portableInventory, {
    id: "scene/portable-demo/module/invalid",
    worldOriginMm: [100, 200, 0],
    expectedSourceSha256: "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    bindings: [{ id: "body", layer: "CABINET_BODY", role: "other", structural: true }]
  }), /DXF_SOURCE_FINGERPRINT_MISMATCH/);
});
