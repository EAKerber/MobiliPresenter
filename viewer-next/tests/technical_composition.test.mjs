import assert from "node:assert/strict";
import test from "node:test";
import { getCurrentTechnicalPresentationByAlias } from "../dist-ts/src/presentation/current-service.js";
import {
  planIsometricDimensions,
  technicalCompositionBoxesIntersect
} from "../dist-ts/src/presentation/technical-composition.js";
import { renderTechnicalViewSvg } from "../dist-ts/src/presentation/technical-diagram.js";
import { createDefaultViewerConfiguration } from "../dist-ts/src/runtime/viewer-state.js";

function count(source, pattern) {
  return [...source.matchAll(pattern)].length;
}

function labelBoxes(svg) {
  return [...svg.matchAll(/data-role="dimension-label"[^>]*data-label-left="([0-9.-]+)" data-label-top="([0-9.-]+)" data-label-right="([0-9.-]+)" data-label-bottom="([0-9.-]+)"/g)]
    .map(match => ({
      left: Number(match[1]),
      top: Number(match[2]),
      right: Number(match[3]),
      bottom: Number(match[4])
    }));
}

function assertNoLabelCollisions(svg) {
  const boxes = labelBoxes(svg);
  assert.equal(boxes.length, 3, "expected three overall isometric labels");
  for (let left = 0; left < boxes.length; left += 1) {
    for (let right = left + 1; right < boxes.length; right += 1) {
      assert.equal(
        technicalCompositionBoxesIntersect(boxes[left], boxes[right], 4),
        false,
        `dimension labels ${left}/${right} overlap`
      );
    }
  }
}

test("module03 geometry-derived isometric owns one semantic overall dimension per axis", () => {
  const pkg = getCurrentTechnicalPresentationByAlias(createDefaultViewerConfiguration(), "03");
  const asset = renderTechnicalViewSvg(pkg, "module03/view/isometric");
  const svg = asset.svg ?? "";

  assert.equal(asset.fidelity, "geometry-derived");
  assert.match(svg, /data-product-dimensions="true"/);
  assert.match(svg, /data-technical-composition="technical-composition\/v0\.3"/);
  assert.equal(count(svg, /data-role="isometric-dimension"/g), 3);

  for (const axis of ["height", "width", "depth"]) {
    assert.equal(count(svg, new RegExp(`data-semantic-key="overall/${axis}"`, "g")), 6);
  }
  assert.equal(count(svg, />1200 mm</g), 1);
  assert.equal(count(svg, />760 mm</g), 1);
  assert.equal(count(svg, />530 mm</g), 1);
  assert.match(svg, /data-semantic-key="overall\/height"[^>]*data-region="left"/);
  assert.match(svg, /data-semantic-key="overall\/width"[^>]*data-region="bottom"/);
  assert.match(svg, /data-semantic-key="overall\/depth"[^>]*data-region="right"/);
  assertNoLabelCollisions(svg);
});

test("module04 thin panel keeps 2400/600/18 overall dimensions once each without cabinet assumptions", () => {
  const pkg = getCurrentTechnicalPresentationByAlias(createDefaultViewerConfiguration(), "04");
  const asset = renderTechnicalViewSvg(pkg, "module04/view/isometric");
  const svg = asset.svg ?? "";

  assert.equal(asset.fidelity, "geometry-derived");
  assert.match(svg, /data-product-dimensions="true"/);
  assert.equal(count(svg, />2400 mm</g), 1);
  assert.equal(count(svg, />600 mm</g), 1);
  assert.equal(count(svg, />18 mm</g), 1);
  assert.equal(count(svg, /data-semantic-key="overall\/height"/g), 6);
  assert.equal(count(svg, /data-semantic-key="overall\/width"/g), 6);
  assert.equal(count(svg, /data-semantic-key="overall\/depth"/g), 6);
  assertNoLabelCollisions(svg);
});

test("composition planner reserves quadrants and can place a very short physical depth guide", () => {
  const plan = planIsometricDimensions({
    guides: [
      { axis: "width", start: { x: 110, y: 200 }, end: { x: 270, y: 200 } },
      { axis: "depth", start: { x: 270, y: 200 }, end: { x: 276, y: 204 } },
      { axis: "height", start: { x: 110, y: 200 }, end: { x: 110, y: 70 } }
    ],
    valuesMm: { width: 600, height: 2400, depth: 18 },
    geometryBox: { left: 100, top: 60, right: 280, bottom: 210 },
    viewBox: { width: 420, height: 300 }
  });

  assert.deepEqual(plan.dimensions.map(item => item.semanticKey), [
    "overall/height",
    "overall/width",
    "overall/depth"
  ]);
  assert.equal(plan.dimensions.find(item => item.axis === "depth")?.valueMm, 18);
  assert.ok(plan.occupiedRegions.includes("left"));
  assert.ok(plan.occupiedRegions.includes("bottom"));
  assert.ok(plan.occupiedRegions.includes("right"));
  for (const placement of plan.dimensions) {
    assert.ok(placement.labelBox.left >= 0);
    assert.ok(placement.labelBox.top >= 0);
    assert.ok(placement.labelBox.right <= 420);
    assert.ok(placement.labelBox.bottom <= 300);
  }
});

test("composition planner fails closed on duplicate or unplaceable dimensions", () => {
  assert.throws(
    () => planIsometricDimensions({
      guides: [
        { axis: "width", start: { x: 0, y: 0 }, end: { x: 10, y: 0 } },
        { axis: "width", start: { x: 0, y: 5 }, end: { x: 10, y: 5 } },
        { axis: "depth", start: { x: 10, y: 0 }, end: { x: 12, y: 2 } },
        { axis: "height", start: { x: 0, y: 10 }, end: { x: 0, y: 0 } }
      ],
      valuesMm: { width: 1200, height: 760, depth: 530 },
      geometryBox: { left: 0, top: 0, right: 10, bottom: 10 },
      viewBox: { width: 420, height: 300 }
    }),
    /TECHNICAL_COMPOSITION_DUPLICATE_DIMENSION:overall\/width/
  );

  assert.throws(
    () => planIsometricDimensions({
      guides: [
        { axis: "width", start: { x: 5, y: 10 }, end: { x: 15, y: 10 } },
        { axis: "depth", start: { x: 15, y: 10 }, end: { x: 18, y: 12 } },
        { axis: "height", start: { x: 5, y: 10 }, end: { x: 5, y: 2 } }
      ],
      valuesMm: { width: 1200, height: 760, depth: 530 },
      geometryBox: { left: 0, top: 0, right: 20, bottom: 15 },
      viewBox: { width: 30, height: 20 },
      maxLanesPerRegion: 1
    }),
    /TECHNICAL_COMPOSITION_UNPLACEABLE_DIMENSION/
  );
});
