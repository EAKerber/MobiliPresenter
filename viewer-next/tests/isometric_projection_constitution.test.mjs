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
import { buildTechnicalLineModel } from "../dist-ts/src/presentation/technical-line-model.js";
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

function projectedEdgeKey(edge) {
  const a = `${edge.startMm.horizontalMm.toFixed(6)},${edge.startMm.verticalMm.toFixed(6)}`;
  const b = `${edge.endMm.horizontalMm.toFixed(6)},${edge.endMm.verticalMm.toFixed(6)}`;
  return a < b ? `${a}|${b}` : `${b}|${a}`;
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

  assert.ok(frame.sceneToCameraDirection.x < 0, "technical camera must remain on the left hemisphere");
  assert.ok(frame.sceneToCameraDirection.y < 0, "technical camera must observe the furniture front from lower y");
  assert.ok(frame.sceneToCameraDirection.z > 0, "technical camera must remain above the product");
  assert.ok(frame.screenUp.z > 0, "positive Scene Core height must remain visually up");

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
  assert.ok(ISOMETRIC_PROJECTION_BASIS.width.verticalMm > 0);
  assert.ok(ISOMETRIC_PROJECTION_BASIS.depth.horizontalMm < 0);
  assert.ok(ISOMETRIC_PROJECTION_BASIS.depth.verticalMm > 0);
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
  assert.ok(normalizedArea > 0.8, `projected width/depth plane is too flat: ${normalizedArea}`);
});

test("technical primitive topology is complete before projection", () => {
  const box = technicalPrimitiveTopology(syntheticBox);
  assert.equal(box.vertices.length, 8);
  assert.equal(box.edges.length, 12);
  assert.equal(new Set(box.edges.map(([a, b]) => a < b ? `${a}-${b}` : `${b}-${a}`)).size, 12);

  const face = technicalPrimitiveTopology(syntheticFace);
  assert.equal(face.vertices.length, 4);
  assert.equal(face.edges.length, 4);
});

test("physical edge graph stays complete while the line model selects technical representation", () => {
  const edges = buildProjectedTechnicalEdgeGraph([syntheticBox], projectIsometricPoint);
  assert.equal(edges.length, 12);
  assert.equal(new Set(edges.map(projectedEdgeKey)).size, 12);
  assert.ok(edges.some(edge => edge.classification === "silhouette"));
  assert.ok(edges.some(edge => edge.classification === "front"));
  assert.ok(edges.some(edge => edge.classification === "depth"));

  const model = buildTechnicalLineModel(edges);
  assert.equal(model.physicalEdgeCount, 12);
  assert.equal(model.renderedEdgeCount, 8);
  assert.equal(model.candidates.length, 12);
  assert.equal(model.omittedEdgeIds.length, 4);
  assert.ok(model.renderedEdges.every(edge =>
    edge.classification !== "back" && edge.classification !== "depth"
  ));
});

test("module03 isometric keeps the physical front toward the technical camera", () => {
  const pkg = getCurrentTechnicalPresentationByAlias(createDefaultViewerConfiguration(), "03");
  const iso = geometry(pkg, "module03/view/isometric");
  const widthGuide = iso.dimensionGuides.find(guide => guide.axis === "width");
  const depthGuide = iso.dimensionGuides.find(guide => guide.axis === "depth");
  assert.ok(widthGuide);
  assert.ok(depthGuide);
  assert.ok(widthGuide.endMm.horizontalMm > widthGuide.startMm.horizontalMm);
  assert.ok(widthGuide.endMm.verticalMm > widthGuide.startMm.verticalMm);
  assert.ok(depthGuide.endMm.horizontalMm < depthGuide.startMm.horizontalMm);
  assert.ok(depthGuide.endMm.verticalMm > depthGuide.startMm.verticalMm);

  const widthVector = {
    x: widthGuide.endMm.horizontalMm - widthGuide.startMm.horizontalMm,
    y: widthGuide.endMm.verticalMm - widthGuide.startMm.verticalMm
  };
  const depthVector = {
    x: depthGuide.endMm.horizontalMm - depthGuide.startMm.horizontalMm,
    y: depthGuide.endMm.verticalMm - depthGuide.startMm.verticalMm
  };
  const normalizedArea = Math.abs(widthVector.x * depthVector.y - widthVector.y * depthVector.x) /
    (Math.hypot(widthVector.x, widthVector.y) * Math.hypot(depthVector.x, depthVector.y));
  assert.ok(normalizedArea > 0.8, `module03 projected width/depth plane is too flat: ${normalizedArea}`);

  assert.ok(iso.edges.length > 12);
  assert.equal(new Set(iso.edges.map(projectedEdgeKey)).size, iso.edges.length);
  assert.ok(iso.edges.some(edge => edge.classification === "silhouette"));
  assert.ok(iso.edges.some(edge => edge.classification === "front"));
  assert.ok(iso.edges.some(edge => edge.classification === "depth"));
  assert.ok(iso.edges.some(edge => edge.sourcePrimitiveIds.some(id => id.endsWith("front/drawer-1"))));
  assert.ok(iso.edges.some(edge => edge.sourcePrimitiveIds.some(id => id.endsWith("front/door-right"))));
  assert.deepEqual(iso.omitted, ["hardware", "hidden-line-removal"]);

  const lineModel = buildTechnicalLineModel(iso.edges);
  assert.equal(lineModel.physicalEdgeCount, iso.edges.length);
  assert.ok(
    lineModel.renderedEdgeCount < lineModel.physicalEdgeCount / 2,
    `${lineModel.renderedEdgeCount} rendered from ${lineModel.physicalEdgeCount} physical edges`
  );
  assert.ok(lineModel.renderedEdges.every(edge =>
    edge.classification !== "back" && edge.classification !== "depth"
  ));
  assert.equal(
    lineModel.renderedEdges.some(edge =>
      edge.classification === "internal" && edge.sourcePrimitiveRoles.includes("front")
    ),
    false
  );
  assert.ok(lineModel.renderedEdges.some(edge =>
    edge.sourcePrimitiveIds.some(id => id.endsWith("front/drawer-1"))
  ));
  assert.ok(lineModel.renderedEdges.some(edge =>
    edge.sourcePrimitiveIds.some(id => id.endsWith("front/door-right"))
  ));
  const omittedReasons = new Set(
    lineModel.candidates
      .filter(candidate => candidate.disposition === "omit")
      .map(candidate => candidate.reason)
  );
  assert.ok(omittedReasons.has("non-silhouette-depth"));
  assert.ok(omittedReasons.has("rear-plane"));
  assert.ok(omittedReasons.has("front-thickness-rear"));

  const asset = renderTechnicalViewSvg(pkg, "module03/view/isometric");
  const svg = asset.svg ?? "";
  assert.match(svg, /data-isometric-constitution="isometric-projection\/v0\.5\.1"/);
  assert.match(svg, /data-technical-line-constitution="technical-line-model\/v0\.6"/);
  assert.match(svg, /data-role="technical-line"/);
  assert.match(svg, /data-line-class="front"/);
  assert.match(svg, /data-line-class="silhouette"/);
  assert.doesNotMatch(svg, /data-role="technical-edge"/);
  assert.doesNotMatch(svg, /data-line-class="back"/);
  assert.doesNotMatch(svg, /data-line-class="depth"/);
  assert.match(svg, new RegExp(`data-technical-edge-count="${lineModel.physicalEdgeCount}"`));
  assert.match(svg, new RegExp(`data-technical-line-count="${lineModel.renderedEdgeCount}"`));
  assert.doesNotMatch(svg, /data-role="primary-geometry"/);
  assert.equal(countDimensionLabel(svg, "1200 mm"), 1);
  assert.equal(countDimensionLabel(svg, "760 mm"), 1);
  assert.equal(countDimensionLabel(svg, "530 mm"), 1);
});

test("module04 remains a generic thin-panel stress fixture on the same line policy", () => {
  const pkg = getCurrentTechnicalPresentationByAlias(createDefaultViewerConfiguration(), "04");
  const iso = geometry(pkg, "module04/view/isometric");
  const depthGuide = iso.dimensionGuides.find(guide => guide.axis === "depth");
  assert.ok(depthGuide);
  assert.ok(depthGuide.endMm.horizontalMm < depthGuide.startMm.horizontalMm);
  assert.ok(depthGuide.endMm.verticalMm > depthGuide.startMm.verticalMm);

  assert.equal(iso.edges.length, 12);
  assert.equal(new Set(iso.edges.map(projectedEdgeKey)).size, 12);
  assert.ok(iso.edges.every(edge =>
    edge.sourcePrimitiveIds.every(id => id === "scene/traditional/module/fridge-side/panel")
  ));
  assert.deepEqual(iso.omitted, ["hardware", "hidden-line-removal"]);

  const lineModel = buildTechnicalLineModel(iso.edges);
  assert.equal(lineModel.physicalEdgeCount, 12);
  assert.equal(lineModel.renderedEdgeCount, 8);

  const asset = renderTechnicalViewSvg(pkg, "module04/view/isometric");
  const svg = asset.svg ?? "";
  assert.match(svg, /data-isometric-constitution="isometric-projection\/v0\.5\.1"/);
  assert.match(svg, /data-technical-line-constitution="technical-line-model\/v0\.6"/);
  assert.match(svg, /data-role="technical-line"/);
  assert.match(svg, /data-technical-edge-count="12"/);
  assert.match(svg, /data-technical-line-count="8"/);
  assert.equal(countDimensionLabel(svg, "18 mm"), 1);
  assert.equal(countDimensionLabel(svg, "600 mm"), 1);
  assert.equal(countDimensionLabel(svg, "2400 mm"), 1);
});
