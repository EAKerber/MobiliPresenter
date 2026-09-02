import assert from "node:assert/strict";
import test from "node:test";
import {
  resolveTechnicalEdgeVisibility,
  TECHNICAL_VISIBILITY_VERSION
} from "../dist-ts/src/presentation/technical-visibility.js";
import {
  isometricViewDepth,
  projectIsometricPoint
} from "../dist-ts/src/presentation/technical-isometric.js";
import {
  buildTechnicalLineModel,
  selectTechnicalLineEdges
} from "../dist-ts/src/presentation/technical-line-model.js";
import { getCurrentTechnicalPresentationByAlias } from "../dist-ts/src/presentation/current-service.js";
import { createDefaultViewerConfiguration } from "../dist-ts/src/runtime/viewer-state.js";

const identity = {
  translationMm: { x: 0, y: 0, z: 0 },
  rotation: { x: 0, y: 0, z: 0, w: 1 }
};

function projectedEdge(id, start3d, end3d) {
  return {
    id,
    classification: "crease",
    startMm: projectIsometricPoint(start3d),
    endMm: projectIsometricPoint(end3d),
    startViewDepth: isometricViewDepth(start3d),
    endViewDepth: isometricViewDepth(end3d),
    sourcePrimitiveIds: ["fixture/rear-line"],
    sourcePrimitiveRoles: ["other"]
  };
}

function occluderAt(x = 0, width = 400) {
  return {
    id: "fixture/occluder",
    primitive: "face",
    role: "other",
    localTransform: {
      translationMm: { x, y: 0, z: 0 },
      rotation: identity.rotation
    },
    uAxis: { x: 1, y: 0, z: 0 },
    vAxis: { x: 0, y: 0, z: 1 },
    normal: { x: 0, y: -1, z: 0 },
    sizeMm: [width, 400],
    sourceBindingIds: ["fixture:occluder"]
  };
}

test("visibility resolver fully hides a selected line behind a nearer projected face", () => {
  const edge = projectedEdge(
    "edge-behind-face",
    { x: 150, y: 40, z: 150 },
    { x: 250, y: 40, z: 150 }
  );

  const [resolved] = resolveTechnicalEdgeVisibility(
    [occluderAt()],
    [edge],
    projectIsometricPoint,
    isometricViewDepth
  );
  assert.ok(resolved);
  assert.deepEqual(resolved.visibleIntervals, []);
});

test("visibility resolver preserves a selected line in front of the same face", () => {
  const edge = projectedEdge(
    "edge-in-front",
    { x: 150, y: -40, z: 150 },
    { x: 250, y: -40, z: 150 }
  );

  const [resolved] = resolveTechnicalEdgeVisibility(
    [occluderAt()],
    [edge],
    projectIsometricPoint,
    isometricViewDepth
  );
  assert.ok(resolved);
  assert.deepEqual(resolved.visibleIntervals, [{ startT: 0, endT: 1 }]);
});

test("visibility resolver splits a partly occluded selected line without a fragment-cleanup heuristic", () => {
  const partialOccluder = {
    ...occluderAt(140, 40),
    id: "fixture/partial-occluder",
    localTransform: {
      translationMm: { x: 140, y: 0, z: 150 },
      rotation: identity.rotation
    },
    sizeMm: [40, 100]
  };
  const edge = projectedEdge(
    "edge-partly-behind-face",
    { x: 100, y: 40, z: 150 },
    { x: 300, y: 40, z: 150 }
  );

  const [resolved] = resolveTechnicalEdgeVisibility(
    [partialOccluder],
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

test("module03 evaluates visibility only for topology-selected technical lines", () => {
  assert.equal(TECHNICAL_VISIBILITY_VERSION, "technical-visibility/v0.1");
  const pkg = getCurrentTechnicalPresentationByAlias(createDefaultViewerConfiguration(), "03");
  const iso = pkg.technicalViewGeometry.find(candidate => candidate.viewId === "module03/view/isometric");
  assert.ok(iso);

  const selection = selectTechnicalLineEdges(iso.edges);
  const selectedIds = new Set(selection.selectedEdges.map(edge => edge.id));
  const evaluated = iso.edges.filter(edge => edge.visibleIntervals !== undefined);
  const unevaluated = iso.edges.filter(edge => edge.visibleIntervals === undefined);

  assert.equal(evaluated.length, selection.selectedEdgeCount);
  assert.ok(evaluated.every(edge => selectedIds.has(edge.id)));
  assert.ok(unevaluated.every(edge => edge.classification === "back-facing"));

  const affected = evaluated.filter(edge =>
    edge.visibleIntervals.length === 0 ||
    edge.visibleIntervals.length > 1 ||
    edge.visibleIntervals.some(interval => interval.startT > 1e-9 || interval.endT < 1 - 1e-9)
  );
  assert.ok(affected.length > 0);

  const lineModel = buildTechnicalLineModel(iso.edges);
  assert.ok(lineModel.occludedEdgeIds.length + lineModel.clippedEdgeIds.length > 0);
  assert.ok(lineModel.renderedEdges.some(edge =>
    edge.sourcePrimitiveIds.some(id => id.endsWith("front/drawer-1"))
  ));
  assert.ok(lineModel.renderedEdges.some(edge =>
    edge.sourcePrimitiveIds.some(id => id.endsWith("front/door-right"))
  ));
});
