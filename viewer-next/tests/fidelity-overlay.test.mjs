import assert from "node:assert/strict";
import test from "node:test";
import { buildFidelityOverlay } from "../dist/src/renderer/three/fidelity-overlay.js";

test("debug overlay batches lines by semantic fidelity role", () => {
  const overlay = buildFidelityOverlay([
    { id: "a", role: "grid-minor", aMm: { x: 0, y: 0, z: 0 }, bMm: { x: 100, y: 0, z: 0 } },
    { id: "b", role: "grid-minor", aMm: { x: 0, y: 100, z: 0 }, bMm: { x: 100, y: 100, z: 0 } },
    { id: "c", role: "wireframe", aMm: { x: 0, y: 0, z: 0 }, bMm: { x: 0, y: 0, z: 100 } }
  ]);
  assert.equal(overlay.name, "fidelity-overlay");
  assert.equal(overlay.userData.debugOnly, true);
  assert.equal(overlay.userData.lineCount, 3);
  assert.equal(overlay.children.length, 2);
  const minor = overlay.children.find(child => child.userData.fidelityRole === "grid-minor");
  const wire = overlay.children.find(child => child.userData.fidelityRole === "wireframe");
  assert.equal(minor.userData.lineCount, 2);
  assert.equal(wire.userData.lineCount, 1);
});

test("xray style disables depth testing without changing line geometry", () => {
  const lines = [{ id: "a", role: "aabb", aMm: { x: 1, y: 2, z: 3 }, bMm: { x: 4, y: 5, z: 6 } }];
  const normal = buildFidelityOverlay(lines);
  const xray = buildFidelityOverlay(lines, { xray: true });
  assert.equal(normal.children[0].material.depthTest, true);
  assert.equal(xray.children[0].material.depthTest, false);
  assert.deepEqual(
    Array.from(normal.children[0].geometry.attributes.position.array),
    Array.from(xray.children[0].geometry.attributes.position.array)
  );
});
