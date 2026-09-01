import assert from "node:assert/strict";
import test from "node:test";
import {
  buildProjectedTechnicalEdgeGraph,
  technicalPrimitiveTopology
} from "../dist-ts/src/presentation/technical-edge-graph.js";
import {
  ISOMETRIC_PROJECTION_BASIS,
  isometricDepthRecedes,
  projectIsometricPoint
} from "../dist-ts/src/presentation/technical-isometric.js";
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

test("canonical isometric basis makes positive scene depth recede from the frontal datum", () => {
  assert.equal(isometricDepthRecedes(), true);
  assert.ok(ISOMETRIC_PROJECTION_BASIS.width.horizontalMm > 0);
  assert.ok(ISOMETRIC_PROJECTION_BASIS.width.verticalMm < 0);
  assert.ok(ISOMETRIC_PROJECTION_BASIS.depth.horizontalMm < 0);
  assert.ok(ISOMETRIC_PROJECTION_BASIS.depth.verticalMm > 0);
  assert.ok(ISOMETRIC_PROJECTION_BASIS.height.verticalMm > 0);

  const front = projectIsometricPoint({ x: 100, y: 0, z: 0 });
  const back = projectIsometricPoint({ x: 100, y: 60, z: 0 });
  assert.ok(back.horizontalMm < front.horizontalMm);
  assert.ok(back.verticalMm > front.verticalMm);
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

test("projected edge graph deduplicates physical edges and classifies a closed box", () => {
  const edges = buildProjectedTechnicalEdgeGraph([syntheticBox], projectIsometricPoint);
  assert.equal(edges.length, 12);
  assert.equal(new Set(edges.map(projectedEdgeKey)).size, 12);
  assert.ok(edges.some(edge => edge.classification === "silhouette"));
  assert.ok(edges.some(edge => edge.classification === "front"));
  assert.ok(edges.some(edge => edge.classification === "depth"));
});

test("module03 isometric uses the canonical receding-depth edge constitution", () => {
  const pkg = getCurrentTechnicalPresentationByAlias(createDefaultViewerConfiguration(), "03");
  const iso = geometry(pkg, "module03/view/isometric");
  const depthGuide = iso.dimensionGuides.find(guide => guide.axis === "depth");
  assert.ok(depthGuide);
  assert.ok(depthGuide.endMm.horizontalMm < depthGuide.startMm.horizontalMm);
  assert.ok(depthGuide.endMm.verticalMm > depthGuide.startMm.verticalMm);

  assert.ok(iso.edges.length > 12);
  assert.equal(new Set(iso.edges.map(projectedEdgeKey)).size, iso.edges.length);
  assert.ok(iso.edges.some(edge => edge.classification === "silhouette"));
  assert.ok(iso.edges.some(edge => edge.classification === "front"));
  assert.ok(iso.edges.some(edge => edge.classification === "depth"));
  assert.ok(iso.edges.some(edge => edge.sourcePrimitiveIds.some(id => id.endsWith("front/drawer-1"))));
  assert.ok(iso.edges.some(edge => edge.sourcePrimitiveIds.some(id => id.endsWith("front/door-right"))));
  assert.deepEqual(iso.omitted, ["hardware", "hidden-line-removal"]);

  const asset = renderTechnicalViewSvg(pkg, "module03/view/isometric");
  const svg = asset.svg ?? "";
  assert.match(svg, /data-isometric-constitution="isometric-projection\/v0\.4"/);
  assert.match(svg, /data-role="technical-edge"/);
  assert.match(svg, /data-edge-class="front"/);
  assert.match(svg, /data-edge-class="silhouette"/);
  assert.doesNotMatch(svg, /data-role="primary-geometry"/);
  assert.equal(countDimensionLabel(svg, "1200 mm"), 1);
  assert.equal(countDimensionLabel(svg, "760 mm"), 1);
  assert.equal(countDimensionLabel(svg, "530 mm"), 1);
});

test("module04 remains a generic thin-panel stress fixture on the same edge pipeline", () => {
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

  const asset = renderTechnicalViewSvg(pkg, "module04/view/isometric");
  const svg = asset.svg ?? "";
  assert.match(svg, /data-isometric-constitution="isometric-projection\/v0\.4"/);
  assert.match(svg, /data-role="technical-edge"/);
  assert.equal(countDimensionLabel(svg, "18 mm"), 1);
  assert.equal(countDimensionLabel(svg, "600 mm"), 1);
  assert.equal(countDimensionLabel(svg, "2400 mm"), 1);
});
