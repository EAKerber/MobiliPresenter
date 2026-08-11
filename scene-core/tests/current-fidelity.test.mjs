import assert from "node:assert/strict";
import test from "node:test";
import {
  CURRENT_FIDELITY_SUPERSAMPLE,
  CURRENT_FIDELITY_VIEWPORT,
  createCurrentFidelityOverlayLines
} from "../dist/src/fixtures/current-fidelity.js";

test("current fidelity profile freezes canonical viewport and 4x supersampling", () => {
  assert.deepEqual(CURRENT_FIDELITY_VIEWPORT, { widthPx: 1865, heightPx: 967 });
  assert.equal(CURRENT_FIDELITY_SUPERSAMPLE, 4);
});

test("current fidelity overlay contains metric grids and 02+03 dimension", () => {
  const lines = createCurrentFidelityOverlayLines();
  const ids = new Set(lines.map(line => line.id));
  assert.ok([...ids].some(id => id.startsWith("scene/traditional/fidelity/grid/wall-main/")));
  assert.ok([...ids].some(id => id.startsWith("scene/traditional/fidelity/grid/lower-front/")));
  assert.ok([...ids].some(id => id.startsWith("scene/traditional/fidelity/grid/upper-front/")));
  assert.ok([...ids].some(id => id.startsWith("scene/traditional/fidelity/grid/fridge-front/")));
  const dimension = lines.find(line => line.id === "scene/traditional/fidelity/dimension/module02-plus-module03");
  assert.ok(dimension);
  assert.equal(dimension.metricMm, 2007.688);
});

test("fidelity overlay is deterministic", () => {
  assert.deepEqual(createCurrentFidelityOverlayLines(), createCurrentFidelityOverlayLines());
});
