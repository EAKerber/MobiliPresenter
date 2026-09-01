import assert from "node:assert/strict";
import test from "node:test";
import { getCurrentTechnicalPresentationByAlias } from "../dist-ts/src/presentation/current-service.js";
import { renderTechnicalViewSvg } from "../dist-ts/src/presentation/technical-diagram.js";
import { createDefaultViewerConfiguration } from "../dist-ts/src/runtime/viewer-state.js";

function geometry(pkg, viewId) {
  const value = pkg.technicalViewGeometry.find(candidate => candidate.viewId === viewId);
  assert.ok(value, `missing compiled geometry for ${viewId}`);
  return value;
}

test("module03 front side and isometric views are deterministic projections of real Scene Core primitives", () => {
  const pkg = getCurrentTechnicalPresentationByAlias(createDefaultViewerConfiguration(), "03");
  const front = geometry(pkg, "module03/view/front");
  const side = geometry(pkg, "module03/view/side");
  const isometric = geometry(pkg, "module03/view/isometric");

  assert.equal(front.projection, "width-height");
  assert.equal(side.projection, "depth-height");
  assert.equal(isometric.projection, "isometric");

  const frontIds = front.primitives.map(primitive => primitive.id);
  for (const suffix of ["drawer-1", "drawer-2", "drawer-3", "drawer-4", "door-center", "door-right"]) {
    assert.ok(frontIds.some(id => id.endsWith(suffix)), `front projection missing ${suffix}`);
  }

  const isometricIds = isometric.primitives.map(primitive => primitive.id);
  assert.ok(isometricIds.some(id => id.endsWith("drawer-1")));
  assert.ok(isometricIds.some(id => id.endsWith("door-right")));
  assert.ok(isometricIds.some(id => id.endsWith("drawer-left-side")));
  assert.ok(isometric.boundsMm.horizontal > 0);
  assert.ok(isometric.boundsMm.vertical > 0);
  assert.deepEqual(isometric.coverage, ["module-geometry-primitives"]);
  assert.deepEqual(isometric.omitted, ["hardware", "hidden-line-removal"]);
});

test("module03 geometry-derived SVG exposes stable semantic hooks and authority-backed side dimensions", () => {
  const pkg = getCurrentTechnicalPresentationByAlias(createDefaultViewerConfiguration(), "03");
  const sideA = renderTechnicalViewSvg(pkg, "module03/view/side");
  const sideB = renderTechnicalViewSvg(pkg, "module03/view/side");
  const isoA = renderTechnicalViewSvg(pkg, "module03/view/isometric");
  const isoB = renderTechnicalViewSvg(pkg, "module03/view/isometric");

  assert.equal(sideA.fidelity, "geometry-derived");
  assert.equal(sideA.source, "scene-geometry");
  assert.equal(sideA.svg, sideB.svg);
  assert.match(sideA.svg ?? "", /data-role="primary-geometry"/);
  assert.match(sideA.svg ?? "", /data-role="extension-line"/);
  assert.match(sideA.svg ?? "", /data-role="dimension-line"/);
  assert.match(sideA.svg ?? "", /data-role="tick"/);
  assert.match(sideA.svg ?? "", /data-role="dimension-label"/);
  assert.match(sideA.svg ?? "", />530 mm</);
  assert.match(sideA.svg ?? "", />760 mm</);
  assert.doesNotMatch(sideA.svg ?? "", /data-role="geometry-envelope"/);

  assert.equal(isoA.fidelity, "geometry-derived");
  assert.equal(isoA.source, "scene-geometry");
  assert.equal(isoA.svg, isoB.svg);
  assert.match(isoA.svg ?? "", /drawer-1/);
  assert.match(isoA.svg ?? "", /door-right/);
  assert.match(isoA.svg ?? "", /data-role="primary-geometry"/);
  assert.doesNotMatch(isoA.svg ?? "", /data-role="envelope-edge"/);
});

test("module03 authored internal layout remains authored rather than being relabeled as geometry-derived", () => {
  const pkg = getCurrentTechnicalPresentationByAlias(createDefaultViewerConfiguration(), "03");
  assert.equal(
    pkg.technicalViewGeometry.some(candidate => candidate.viewId === "module03/view/internal-front"),
    false
  );

  const internal = renderTechnicalViewSvg(pkg, "module03/view/internal-front");
  assert.equal(internal.fidelity, "schematic");
  assert.equal(internal.source, "authored-internal-layout");
  assert.deepEqual(internal.coverage, ["envelope", "authored-layout"]);
  assert.match(internal.svg ?? "", /data-role="authored-dimension-label"/);
  assert.match(internal.svg ?? "", />390</);
  assert.match(internal.svg ?? "", />400</);
});

test("module04 panel views use available panel geometry without pretending to be cabinet fronts", () => {
  const pkg = getCurrentTechnicalPresentationByAlias(createDefaultViewerConfiguration(), "04");
  const front = geometry(pkg, "module04/view/front");
  const thickness = geometry(pkg, "module04/view/thickness");
  const isometric = geometry(pkg, "module04/view/isometric");

  assert.equal(front.projection, "depth-height");
  assert.equal(thickness.projection, "width-height");
  assert.equal(isometric.projection, "isometric");
  assert.deepEqual(front.coverage, ["module-geometry-primitives"]);
  assert.deepEqual(thickness.coverage, ["module-geometry-primitives"]);
  assert.deepEqual(isometric.coverage, ["module-geometry-primitives"]);
  assert.deepEqual(thickness.omitted, ["hardware", "hidden-line-removal"]);

  const thicknessAsset = renderTechnicalViewSvg(pkg, "module04/view/thickness");
  assert.equal(thicknessAsset.fidelity, "geometry-derived");
  assert.equal(thicknessAsset.source, "scene-geometry");
  assert.deepEqual(thicknessAsset.coverage, ["module-geometry-primitives"]);
  assert.match(thicknessAsset.svg ?? "", /18 mm/);
  assert.match(thicknessAsset.svg ?? "", /2400 mm/);
});
