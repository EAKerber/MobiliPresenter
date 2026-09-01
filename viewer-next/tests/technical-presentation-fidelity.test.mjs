import assert from "node:assert/strict";
import test from "node:test";
import {
  getCurrentTechnicalPresentationByAlias,
  getSelectedTechnicalPresentation,
  getSelectedTechnicalPresentationResult
} from "../dist-ts/src/presentation/current-service.js";
import { renderTechnicalViewSvg } from "../dist-ts/src/presentation/technical-diagram.js";
import { createViewerUiSnapshot } from "../dist-ts/src/api/ui-adapter.js";
import { moduleIdFromAlias } from "../dist-ts/src/runtime/query.js";
import {
  createDefaultViewerConfiguration,
  createDefaultViewerInteraction,
  reduceViewerInteraction
} from "../dist-ts/src/runtime/viewer-state.js";

function span(points, key) {
  const values = points.map(point => point[key]);
  return Math.max(...values) - Math.min(...values);
}

test("module02 front view is geometry-derived from front primitives and the physical oven opening", () => {
  const pkg = getCurrentTechnicalPresentationByAlias(createDefaultViewerConfiguration(), "02");
  const geometry = pkg.technicalViewGeometry.find(candidate => candidate.viewId === "module02/view/front");
  assert.ok(geometry);
  assert.equal(geometry.coordinateUnit, "mm");
  assert.equal(geometry.projection, "width-height");
  assert.deepEqual(geometry.boundsMm, { horizontal: 791.01, vertical: 760 });
  assert.deepEqual(geometry.coverage, ["module-front-primitives", "appliance-front-openings"]);
  assert.deepEqual(geometry.omitted, ["hardware", "hidden-geometry"]);

  const primitiveIds = geometry.primitives.map(primitive => primitive.id);
  assert.equal(geometry.primitives.length, 4);
  assert.ok(primitiveIds.some(id => id.endsWith("oven-left-stile")));
  assert.ok(primitiveIds.some(id => id.endsWith("oven-right-stile")));
  assert.ok(primitiveIds.some(id => id.endsWith("oven-bottom-rail")));
  assert.ok(primitiveIds.some(id => id.endsWith("oven-top-rail")));

  assert.equal(geometry.openings.length, 1);
  const opening = geometry.openings[0];
  assert.equal(opening.role, "built-in-oven");
  assert.ok(Math.abs(span(opening.pointsMm, "horizontalMm") - 600) < 1e-6);
  assert.ok(Math.abs(span(opening.pointsMm, "verticalMm") - 600) < 1e-6);

  const asset = renderTechnicalViewSvg(pkg, "module02/view/front");
  assert.equal(asset.status, "ready");
  assert.equal(asset.fidelity, "geometry-derived");
  assert.equal(asset.source, "scene-geometry");
  assert.match(asset.svg ?? "", /data-technical-fidelity="geometry-derived"/);
  assert.match(asset.svg ?? "", /data-role="primary-geometry"/);
  assert.match(asset.svg ?? "", /oven-left-stile/);
  assert.match(asset.svg ?? "", /data-opening-id=/);
  assert.match(asset.svg ?? "", /790 mm/);
});

test("module03 front and side views are geometry-derived while internal layout stays explicitly authored", () => {
  const pkg = getCurrentTechnicalPresentationByAlias(createDefaultViewerConfiguration(), "03");
  const geometry = pkg.technicalViewGeometry.find(candidate => candidate.viewId === "module03/view/front");
  assert.ok(geometry);
  assert.equal(geometry.primitives.length, 6);
  const ids = geometry.primitives.map(primitive => primitive.id);
  for (const suffix of ["drawer-1", "drawer-2", "drawer-3", "drawer-4", "door-center", "door-right"]) {
    assert.ok(ids.some(id => id.endsWith(suffix)), `missing projected front ${suffix}`);
  }

  const front = renderTechnicalViewSvg(pkg, "module03/view/front");
  assert.equal(front.fidelity, "geometry-derived");
  assert.match(front.svg ?? "", /drawer-1/);
  assert.match(front.svg ?? "", /door-right/);

  const authoredInternal = renderTechnicalViewSvg(pkg, "module03/view/internal-front");
  assert.equal(authoredInternal.fidelity, "schematic");
  assert.equal(authoredInternal.source, "authored-internal-layout");
  assert.deepEqual(authoredInternal.coverage, ["envelope", "authored-layout"]);
  assert.match(authoredInternal.svg ?? "", /data-technical-fidelity="schematic"/);
  assert.match(authoredInternal.svg ?? "", /390/);
  assert.match(authoredInternal.svg ?? "", /400/);

  const sideGeometry = pkg.technicalViewGeometry.find(candidate => candidate.viewId === "module03/view/side");
  assert.ok(sideGeometry);
  assert.equal(sideGeometry.projection, "depth-height");
  assert.deepEqual(sideGeometry.coverage, ["module-geometry-primitives"]);
  assert.deepEqual(sideGeometry.omitted, ["hardware", "hidden-line-removal"]);

  const side = renderTechnicalViewSvg(pkg, "module03/view/side");
  assert.equal(side.fidelity, "geometry-derived");
  assert.equal(side.source, "scene-geometry");
  assert.deepEqual(side.coverage, ["module-geometry-primitives"]);
  assert.match(side.svg ?? "", /530 mm/);
  assert.match(side.svg ?? "", /760 mm/);
  assert.match(side.svg ?? "", /data-role="dimension-line"/);
});

test("scene-geometry views cannot silently fall back to an envelope diagram", () => {
  const pkg = getCurrentTechnicalPresentationByAlias(createDefaultViewerConfiguration(), "03");
  const withoutGeometry = { ...pkg, technicalViewGeometry: [] };
  assert.throws(
    () => renderTechnicalViewSvg(withoutGeometry, "module03/view/front"),
    /TECHNICAL_VIEW_GEOMETRY_REQUIRED:module03\/view\/front/
  );
});

test("cataloged module01 resolves ready while null and invalid selections retain fail-closed semantics", () => {
  const configuration = createDefaultViewerConfiguration();
  const module01 = moduleIdFromAlias("01");

  assert.deepEqual(getSelectedTechnicalPresentationResult(configuration, null), {
    status: "none",
    reason: null,
    presentation: null
  });

  const module01Result = getSelectedTechnicalPresentationResult(configuration, module01);
  assert.equal(module01Result.status, "ready");
  assert.equal(module01Result.reason, null);
  assert.equal(module01Result.presentation?.identity.alias, "01");
  assert.equal(getSelectedTechnicalPresentation(configuration, module01)?.identity.alias, "01");

  assert.throws(
    () => getSelectedTechnicalPresentationResult(configuration, "scene/traditional/module/does-not-exist"),
    /TECHNICAL_PRESENTATION_TARGET_NOT_FOUND/
  );
});

test("UI snapshot exposes ready technical presentation for cataloged modules and none without selection", () => {
  const configuration = createDefaultViewerConfiguration();
  const module01Interaction = reduceViewerInteraction(createDefaultViewerInteraction(), {
    type: "select-module",
    moduleId: moduleIdFromAlias("01")
  });
  const module01 = createViewerUiSnapshot(configuration, module01Interaction);
  assert.equal(module01.selectedModuleAlias, "01");
  assert.deepEqual(module01.selectedTechnicalPresentationAvailability, {
    status: "ready",
    reason: null
  });
  assert.equal(module01.selectedTechnicalPresentation?.identity.alias, "01");
  assert.ok(module01.selectedTechnicalViewAssets.some(asset => asset.fidelity === "geometry-derived"));

  const module03Interaction = reduceViewerInteraction(createDefaultViewerInteraction(), {
    type: "select-module",
    moduleId: moduleIdFromAlias("03")
  });
  const module03 = createViewerUiSnapshot(configuration, module03Interaction);
  assert.deepEqual(module03.selectedTechnicalPresentationAvailability, { status: "ready", reason: null });
  assert.equal(module03.selectedTechnicalPresentation?.identity.alias, "03");
  assert.ok(module03.selectedTechnicalViewAssets.some(asset => asset.fidelity === "geometry-derived"));

  const none = createViewerUiSnapshot(configuration, createDefaultViewerInteraction());
  assert.deepEqual(none.selectedTechnicalPresentationAvailability, { status: "none", reason: null });
});
