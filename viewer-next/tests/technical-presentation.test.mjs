import assert from "node:assert/strict";
import test from "node:test";
import {
  UNDER_CAB_LIGHT_ITEM_ID,
  currentSceneBase,
  module03WithSink,
  module04
} from "@mobilipresenter/scene-core";
import {
  compileTechnicalPresentation,
  technicalPresentationFingerprint,
  validateTechnicalCatalog
} from "../dist-ts/src/presentation/compile.js";
import {
  createCurrentTechnicalPresentationInput,
  getCurrentTechnicalPresentationByAlias,
  getSelectedTechnicalPresentation
} from "../dist-ts/src/presentation/current-service.js";
import { renderTechnicalViewSvg } from "../dist-ts/src/presentation/technical-diagram.js";
import {
  CURRENT_TECHNICAL_CATALOG,
  module03TechnicalCatalog
} from "../dist-ts/src/presentation/technical-catalog.js";
import {
  createDefaultViewerConfiguration,
  reduceViewerConfiguration
} from "../dist-ts/src/runtime/viewer-state.js";

test("module03 presentation uses Core dimensions and authored internal layout without conflating them", () => {
  const configuration = createDefaultViewerConfiguration();
  const pkg = getCurrentTechnicalPresentationByAlias(configuration, "03");

  assert.equal(pkg.target.entityId, module03WithSink.id);
  assert.equal(pkg.dimensions?.primaryKind, "nominal");
  assert.deepEqual(pkg.dimensions?.primaryMm, { width: 1200, height: 760, depth: 530 });
  assert.deepEqual(pkg.dimensions?.geometryMm, { width: 1216.678, height: 760, depth: 530 });
  assert.ok(pkg.dimensions?.evidence.some(item => item.reference === "module-03-sheet"));

  const internal = pkg.technicalViews.find(view => view.id === "module03/view/internal-front");
  assert.deepEqual(internal?.internalLayout?.segments.map(segment => segment.spanMm), [390, 400, 400]);
  assert.equal(pkg.components.find(component => component.id === "module03/component/runner-h45")?.quantity, 4);

  const asset = renderTechnicalViewSvg(pkg, "module03/view/internal-front");
  assert.equal(asset.status, "ready");
  assert.match(asset.svg ?? "", /1200 mm/);
  assert.match(asset.svg ?? "", />390</);
});

test("module04 technical orientation presents 2400 x 600 x 18 from nominal Core axes", () => {
  const pkg = getCurrentTechnicalPresentationByAlias(createDefaultViewerConfiguration(), "04");
  assert.deepEqual(pkg.dimensions?.primaryMm, { width: 18, height: 2400, depth: 600 });
  assert.deepEqual(pkg.dimensions?.order, ["height", "depth", "width"]);

  const front = renderTechnicalViewSvg(pkg, "module04/view/front");
  const thickness = renderTechnicalViewSvg(pkg, "module04/view/thickness");
  assert.equal(front.status, "ready");
  assert.match(front.svg ?? "", /600 mm/);
  assert.match(front.svg ?? "", /2400 mm/);
  assert.match(thickness.svg ?? "", /18 mm/);
});

test("finish policies expose controlled option ids while Appearance remains material authority", () => {
  let configuration = createDefaultViewerConfiguration();
  configuration = reduceViewerConfiguration(configuration, {
    type: "set-front-preset",
    moduleId: module03WithSink.id,
    presetId: "neutral-greige"
  });
  configuration = reduceViewerConfiguration(configuration, { type: "set-stone-preset", presetId: "graphite-speckled" });

  const pkg = getCurrentTechnicalPresentationByAlias(configuration, "03");
  const front = pkg.finishes.find(finish => finish.id === "module03/finish/front");
  const stone = pkg.finishes.find(finish => finish.id === "module03/finish/stone");
  assert.equal(front?.currentOptionId, "neutral-greige");
  assert.equal(front?.resolvedMaterialId, "front-primary");
  assert.equal(stone?.currentOptionId, "graphite-speckled");
  assert.equal(stone?.resolvedMaterialId, "stone-speckled-graphite");
  assert.ok(front?.options.every(option => option.materialId.length > 0));
});

test("lighting 08 declares own visibility and activation separately and resolves module04/module06 dependencies", () => {
  const initial = createDefaultViewerConfiguration();
  const available = getCurrentTechnicalPresentationByAlias(initial, "08");
  assert.equal(available.target.entityId, UNDER_CAB_LIGHT_ITEM_ID);
  assert.equal(available.availability.available, true);
  assert.deepEqual(available.controls.map(control => control.kind), ["visibility", "activation"]);
  assert.equal(available.controls.find(control => control.kind === "visibility")?.implementationStatus, "declared-not-bound");
  assert.equal(available.controls.find(control => control.kind === "activation")?.implementationStatus, "declared-not-bound");

  const hidden04 = reduceViewerConfiguration(initial, {
    type: "set-module-visibility",
    moduleId: module04.id,
    value: "off"
  });
  const blocked = getCurrentTechnicalPresentationByAlias(hidden04, "08");
  assert.equal(blocked.availability.available, false);
  assert.deepEqual(blocked.availability.blockingDependencyIds, [module04.id]);
});

test("technical catalog is forbidden from becoming a second physical dimension authority", () => {
  const rogue = {
    ...module03TechnicalCatalog,
    dimensions: {
      ...module03TechnicalCatalog.dimensions,
      nominalMm: { width: 999, height: 999, depth: 999 }
    }
  };
  assert.throws(
    () => validateTechnicalCatalog(currentSceneBase, [rogue]),
    /TECHNICAL_CATALOG_PHYSICAL_DIMENSION_FORBIDDEN/
  );
});

test("presentation compilation is deterministic, serializable and does not mutate its inputs", () => {
  const configuration = createDefaultViewerConfiguration();
  const input = createCurrentTechnicalPresentationInput(configuration);
  const beforeScene = JSON.stringify(input.scene);
  const beforeAppearance = JSON.stringify(input.appearance);
  const beforeConfiguration = JSON.stringify(configuration);

  const first = compileTechnicalPresentation(input, module03WithSink.id);
  const second = compileTechnicalPresentation(input, module03WithSink.id);
  assert.equal(technicalPresentationFingerprint(first), technicalPresentationFingerprint(second));
  assert.doesNotThrow(() => JSON.stringify(first));
  assert.equal(JSON.stringify(input.scene), beforeScene);
  assert.equal(JSON.stringify(input.appearance), beforeAppearance);
  assert.equal(JSON.stringify(configuration), beforeConfiguration);
});

test("selected-module service yields a package directly and null for no selection", () => {
  const configuration = createDefaultViewerConfiguration();
  assert.equal(getSelectedTechnicalPresentation(configuration, null), null);
  assert.equal(getSelectedTechnicalPresentation(configuration, module04.id)?.identity.alias, "04");
});

test("all catalog references resolve in the current scene", () => {
  const input = createCurrentTechnicalPresentationInput(createDefaultViewerConfiguration());
  assert.doesNotThrow(() => validateTechnicalCatalog(input.scene, CURRENT_TECHNICAL_CATALOG));
  for (const entry of CURRENT_TECHNICAL_CATALOG) {
    assert.doesNotThrow(() => compileTechnicalPresentation(input, entry.target.entityId));
  }
});
