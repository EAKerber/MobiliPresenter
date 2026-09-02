import assert from "node:assert/strict";
import test from "node:test";
import {
  buildProjectedTechnicalEdgeGraph,
  technicalPrimitiveTopology
} from "../dist-ts/src/presentation/technical-edge-graph.js";
import {
  ISOMETRIC_PROJECTION_BASIS,
  ISOMETRIC_PROJECTION_FRAME,
  isometricProjectionMetrics,
  isometricViewDepth,
  projectIsometricPoint
} from "../dist-ts/src/presentation/technical-isometric.js";
import {
  buildTechnicalLineModel,
  selectTechnicalLineEdges
} from "../dist-ts/src/presentation/technical-line-model.js";
import { getCurrentTechnicalPresentationByAlias } from "../dist-ts/src/presentation/current-service.js";
import { renderTechnicalViewSvg } from "../dist-ts/src/presentation/technical-diagram.js";
import { createDefaultViewerConfiguration } from "../dist-ts/src/runtime/viewer-state.js";

const identity = {
  translationMm: { x: 0, y: 0, z: 0 },
  rotation: { x: 0, y: 0, z: 0, w: 1 }
};

const syntheticBox = {
  id: "fixture/box",
  primitive: "box",
  role: "other",
  localTransform: identity,
  sizeMm: { width: 100, height: 80, depth: 60 },
  sourceBindingIds: ["fixture:box"]
};

const syntheticFace = {
  id: "fixture/face",
  primitive: "face",
  role: "other",
  localTransform: identity,
  uAxis: { x: 1, y: 0, z: 0 },
  vAxis: { x: 0, y: 0, z: 1 },
  normal: { x: 0, y: -1, z: 0 },
  sizeMm: [100, 80],
  sourceBindingIds: ["fixture:face"]
};

function geometry(pkg, viewId) {
  const value = pkg.technicalViewGeometry.find(candidate => candidate.viewId === viewId);
  assert.ok(value, `missing compiled geometry for ${viewId}`);
  return value;
}

function countDimensionLabel(svg, label) {
  return [...svg.matchAll(/<text data-role="dimension-label"[^>]*>([^<]+)<\/text>/g)]
    .filter(match => match[1] === label)
    .length;
}

function approx(actual, expected, epsilon = 1e-9) {
  assert.ok(Math.abs(actual - expected) <= epsilon, `${actual} != ${expected}`);
}

function length3(vector) {
  return Math.hypot(vector.x, vector.y, vector.z);
}

function dot3(a, b) {
  return a.x * b.x + a.y * b.y + a.z * b.z;
}

test("canonical isometric projection uses a front-left-above orthonormal camera frame", () => {
  const frame = ISOMETRIC_PROJECTION_FRAME;
  approx(length3(frame.sceneToCameraDirection), 1);
  approx(length3(frame.screenRight), 1);
  approx(length3(frame.screenUp), 1);
  approx(dot3(frame.sceneToCameraDirection, frame.screenRight), 0);
  approx(dot3(frame.sceneToCameraDirection, frame.screenUp), 0);
  approx(dot3(frame.screenRight, frame.screenUp), 0);

  assert.ok(frame.sceneToCameraDirection.x < 0);
  assert.ok(frame.sceneToCameraDirection.y < 0);
  assert.ok(frame.sceneToCameraDirection.z > 0);
  assert.ok(frame.screenUp.z > 0);

  const frontDepth = isometricViewDepth({ x: 0, y: -18, z: 0 });
  const carcassFrontDepth = isometricViewDepth({ x: 0, y: 0, z: 0 });
  const rearDepth = isometricViewDepth({ x: 0, y: 530, z: 0 });
  assert.ok(frontDepth > carcassFrontDepth);
  assert.ok(carcassFrontDepth > rearDepth);

  const metrics = isometricProjectionMetrics();
  approx(metrics.widthScale, 1);
  approx(metrics.depthScale, 1);
  approx(metrics.heightScale, 1);
  approx(metrics.normalizedWidthDepthArea, Math.sqrt(3) / 2);

  assert.ok(ISOMETRIC_PROJECTION_BASIS.width.horizontalMm > 0);
  assert.ok(ISOMETRIC_PROJECTION_BASIS.depth.horizontalMm < 0);
  assert.ok(ISOMETRIC_PROJECTION_BASIS.height.verticalMm > 0);
});

test("canonical projection is linear and keeps width/depth non-degenerate", () => {
  const width = projectIsometricPoint({ x: 100, y: 0, z: 0 });
  const depth = projectIsometricPoint({ x: 0, y: 100, z: 0 });
  const height = projectIsometricPoint({ x: 0, y: 0, z: 100 });
  const combined = projectIsometricPoint({ x: 100, y: 100, z: 100 });

  approx(Math.hypot(width.horizontalMm, width.verticalMm), 100);
  approx(Math.hypot(depth.horizontalMm, depth.verticalMm), 100);
  approx(Math.hypot(height.horizontalMm, height.verticalMm), 100);
  approx(combined.horizontalMm, width.horizontalMm + depth.horizontalMm + height.horizontalMm);
  approx(combined.verticalMm, width.verticalMm + depth.verticalMm + height.verticalMm);

  const normalizedArea = Math.abs(
    width.horizontalMm * depth.verticalMm - width.verticalMm * depth.horizontalMm
  ) / 10000;
  assert.ok(normalizedArea > 0.8);
});

test("primitive topology exposes edges, faces and outward face normals", () => {
  const box = technicalPrimitiveTopology(syntheticBox);
  assert.equal(box.vertices.length, 8);
  assert.equal(box.edges.length, 12);
  assert.equal(box.faces.length, 6);
  assert.equal(box.faceNormals.length, 6);
  assert.equal(new Set(box.edges.map(([a, b]) => a < b ? `${a}-${b}` : `${b}-${a}`)).size, 12);

  const face = technicalPrimitiveTopology(syntheticFace);
  assert.equal(face.vertices.length, 4);
  assert.equal(face.edges.length, 4);
  assert.equal(face.faces.length, 1);
  assert.equal(face.faceNormals.length, 1);
  assert.ok(dot3(face.faceNormals[0], ISOMETRIC_PROJECTION_FRAME.sceneToCameraDirection) > 0);
});

test("box line selection is camera-topological rather than world-axis filtering", () => {
  const edges = buildProjectedTechnicalEdgeGraph(
    [syntheticBox],
    projectIsometricPoint,
    isometricViewDepth
  );
  assert.equal(edges.length, 12);

  const classes = new Set(edges.map(edge => edge.classification));
  assert.ok(classes.has("silhouette"));
  assert.ok(classes.has("crease"));
  assert.ok(classes.has("back-facing"));
  assert.equal(classes.has("depth"), false);
  assert.equal(classes.has("front"), false);

  const selection = selectTechnicalLineEdges(edges);
  assert.equal(selection.physicalEdgeCount, 12);
  assert.equal(selection.selectedEdgeCount, 9);
  assert.equal(selection.omittedEdgeIds.length, 3);
  assert.ok(selection.candidates
    .filter(candidate => candidate.disposition === "omit")
    .every(candidate => candidate.reason === "back-facing"));

  const model = buildTechnicalLineModel(edges);
  assert.equal(model.renderedEdgeCount, 9);
  assert.ok(model.renderedEdges.some(edge => edge.classification === "internal"));
  assert.ok(model.renderedEdges.some(edge => edge.classification === "silhouette"));
});

test("module03 keeps physical topology and evaluates visibility only after line selection", () => {
  const pkg = getCurrentTechnicalPresentationByAlias(createDefaultViewerConfiguration(), "03");
  const iso = geometry(pkg, "module03/view/isometric");
  const selection = selectTechnicalLineEdges(iso.edges);
  const lineModel = buildTechnicalLineModel(iso.edges);

  assert.ok(iso.edges.length > 12);
  assert.ok(selection.selectedEdgeCount > 0);
  assert.ok(selection.selectedEdgeCount < selection.physicalEdgeCount);
  assert.ok(selection.omittedEdgeIds.length > 0);

  const evaluated = iso.edges.filter(edge => edge.visibleIntervals !== undefined);
  const notEvaluated = iso.edges.filter(edge => edge.visibleIntervals === undefined);
  assert.ok(evaluated.length > 0);
  assert.ok(notEvaluated.length > 0);
  assert.ok(notEvaluated.every(edge => edge.classification === "back-facing"));

  assert.ok(lineModel.renderedEdges.some(edge =>
    edge.sourcePrimitiveIds.some(id => id.endsWith("front/drawer-1"))
  ));
  assert.ok(lineModel.renderedEdges.some(edge =>
    edge.sourcePrimitiveIds.some(id => id.endsWith("front/door-right"))
  ));

  const asset = renderTechnicalViewSvg(pkg, "module03/view/isometric");
  const svg = asset.svg ?? "";
  assert.match(svg, /data-isometric-constitution="isometric-projection\/v0\.5\.1"/);
  assert.match(svg, /data-technical-line-constitution="technical-line-model\/v0\.6"/);
  assert.match(svg, /data-role="technical-line"/);
  assert.doesNotMatch(svg, /data-role="technical-edge"/);
  assert.equal(countDimensionLabel(svg, "1200 mm"), 1);
  assert.equal(countDimensionLabel(svg, "760 mm"), 1);
  assert.equal(countDimensionLabel(svg, "530 mm"), 1);
});

test("module04 remains a generic thin-panel stress fixture on the same topology policy", () => {
  const pkg = getCurrentTechnicalPresentationByAlias(createDefaultViewerConfiguration(), "04");
  const iso = geometry(pkg, "module04/view/isometric");
  assert.equal(iso.edges.length, 12);

  const selection = selectTechnicalLineEdges(iso.edges);
  const lineModel = buildTechnicalLineModel(iso.edges);
  assert.equal(selection.selectedEdgeCount, 9);
  assert.equal(lineModel.renderedEdgeCount, 9);

  const asset = renderTechnicalViewSvg(pkg, "module04/view/isometric");
  const svg = asset.svg ?? "";
  assert.match(svg, /data-role="technical-line"/);
  assert.match(svg, /data-technical-edge-count="12"/);
  assert.match(svg, /data-technical-line-count="9"/);
  assert.equal(countDimensionLabel(svg, "18 mm"), 1);
  assert.equal(countDimensionLabel(svg, "600 mm"), 1);
  assert.equal(countDimensionLabel(svg, "2400 mm"), 1);
});
