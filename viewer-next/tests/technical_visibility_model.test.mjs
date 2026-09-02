import assert from "node:assert/strict";
import test from "node:test";
import { resolveTechnicalEdgeVisibility, TECHNICAL_VISIBILITY_VERSION } from "../dist-ts/src/presentation/technical-visibility.js";
import { isometricViewDepth, projectIsometricPoint } from "../dist-ts/src/presentation/technical-isometric.js";
import { buildTechnicalLineModel } from "../dist-ts/src/presentation/technical-line-model.js";
import { getCurrentTechnicalPresentationByAlias } from "../dist-ts/src/presentation/current-service.js";
import { createDefaultViewerConfiguration } from "../dist-ts/src/runtime/viewer-state.js";

const identity = {
  translationMm: { x: 0, y: 0, z: 0 },
  rotation: { x: 0, y: 0, z: 0, w: 1 }
};

function projectedEdge(id, start3d, end3d) {
  return {
    id,
    classification: "internal",
    startMm: projectIsometricPoint(start3d),
    endMm: projectIsometricPoint(end3d),
    startViewDepth: isometricViewDepth(start3d),
    endViewDepth: isometricViewDepth(end3d),
    visibleIntervals: [{ startT: 0, endT: 1 }],
    sourcePrimitiveIds: ["fixture/rear-line"],
    sourcePrimitiveRoles: ["other"]
  };
}

test("visibility resolver fully hides a line behind a nearer projected face", () => {
  const occluder = {
    id: "fixture/occluder",
    primitive: "face",
    role: "other",
    localTransform: identity,
    uAxis: { x: 1, y: 0, z: 0 },
    vAxis: { x: 0, y: 0, z: 1 },
    normal: { x: 0, y: -1, z: 0 },
    sizeMm: [400, 400],
    sourceBindingIds: ["fixture:occluder"]
  };
  const edge = projectedEdge(
    "edge-behind-face",
    { x: 150, y: 40, z: 150 },
    { x: 250, y: 40, z: 150 }
  );

  const [resolved] = resolveTechnicalEdgeVisibility(
    [occluder],
    [edge],
    projectIsometricPoint,
    isometricViewDepth
  );
  assert.ok(resolved);
  assert.deepEqual(resolved.visibleIntervals, []);
});

test("visibility resolver preserves a line in front of the same face", () => {
  const occluder = {
    id: "fixture/occluder",
    primitive: "face",
    role: "other",
    localTransform: identity,
    uAxis: { x: 1, y: 0, z: 0 },
    vAxis: { x: 0, y: 0, z: 1 },
    normal: { x: 0, y: -1, z: 0 },
    sizeMm: [400, 400],
    sourceBindingIds: ["fixture:occluder"]
  };
  const edge = projectedEdge(
    "edge-in-front",
    { x: 150, y: -40, z: 150 },
    { x: 250, y: -40, z: 150 }
  );

  const [resolved] = resolveTechnicalEdgeVisibility(
    [occluder],
    [edge],
    projectIsometricPoint,
    isometricViewDepth
  );
  assert.ok(resolved);
  assert.deepEqual(resolved.visibleIntervals, [{ startT: 0, endT: 1 }]);
});


test("visibility resolver splits a partly occluded line into stable visible intervals", () => {
  const occluder = {
    id: "fixture/partial-occluder",
    primitive: "face",
    role: "other",
    localTransform: {
      translationMm: { x: 140, y: 0, z: 150 },
      rotation: identity.rotation
    },
    uAxis: { x: 1, y: 0, z: 0 },
    vAxis: { x: 0, y: 0, z: 1 },
    normal: { x: 0, y: -1, z: 0 },
    sizeMm: [40, 100],
    sourceBindingIds: ["fixture:partial-occluder"]
  };
  const edge = projectedEdge(
    "edge-partly-behind-face",
    { x: 100, y: 40, z: 150 },
    { x: 300, y: 40, z: 150 }
  );

  const [resolved] = resolveTechnicalEdgeVisibility(
    [occluder],
    [edge],
    projectIsometricPoint,
    isometricViewDepth
  );
  assert.ok(resolved);
  assert.equal(resolved.visibleIntervals.length, 2);
  assert.ok(Math.abs(resolved.visibleIntervals[0].startT - 0) < 1e-9);
  assert.ok(Math.abs(resolved.visibleIntervals[0].endT - 0.4) < 1e-9);
  assert.ok(Math.abs(resolved.visibleIntervals[1].startT - 0.6) < 1e-9);
  assert.ok(Math.abs(resolved.visibleIntervals[1].endT - 1) < 1e-9);

  const lineModel = buildTechnicalLineModel([resolved]);
  assert.equal(lineModel.renderedEdgeCount, 2);
  assert.deepEqual(lineModel.clippedEdgeIds, [resolved.id]);
  assert.deepEqual(lineModel.occludedEdgeIds, []);
});

test("module03 carries visibility evidence into the technical-line model", () => {
  assert.equal(TECHNICAL_VISIBILITY_VERSION, "technical-visibility/v0.1");
  const pkg = getCurrentTechnicalPresentationByAlias(createDefaultViewerConfiguration(), "03");
  const iso = pkg.technicalViewGeometry.find(candidate => candidate.viewId === "module03/view/isometric");
  assert.ok(iso);

  const affectedPhysicalEdges = iso.edges.filter(edge =>
    edge.visibleIntervals.length === 0 ||
    edge.visibleIntervals.length > 1 ||
    edge.visibleIntervals.some(interval => interval.startT > 1e-9 || interval.endT < 1 - 1e-9)
  );
  assert.ok(affectedPhysicalEdges.length > 0, "module03 should contain physically occluded or clipped edges");

  const lineModel = buildTechnicalLineModel(iso.edges);
  assert.equal(lineModel.visibilityContractVersion, TECHNICAL_VISIBILITY_VERSION);
  assert.ok(
    lineModel.occludedEdgeIds.length + lineModel.clippedEdgeIds.length > 0,
    "technical line output should consume visibility evidence"
  );
  assert.ok(lineModel.renderedEdges.some(edge =>
    edge.sourcePrimitiveIds.some(id => id.endsWith("front/drawer-1"))
  ));
  assert.ok(lineModel.renderedEdges.some(edge =>
    edge.sourcePrimitiveIds.some(id => id.endsWith("front/door-right"))
  ));
});
