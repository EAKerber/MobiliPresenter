import assert from "node:assert/strict";
import test from "node:test";
import {
  currentSceneBase,
  sceneGeometryDigest
} from "@mobilipresenter/scene-core";
import { Box3 } from "three";
import { styleAnchorAppearance } from "../dist-ts/src/fixtures/style-anchor.js";
import { ThreeMaterialRegistry } from "../dist-ts/src/renderer/three/materials.js";
import { buildThreeScene } from "../dist-ts/src/renderer/three/scene-adapter.js";
import { applyFh06FullWallTiles } from "../dist-ts/src/renderer/three/wall-tiles.js";

function setup() {
  const materials = new ThreeMaterialRegistry(styleAnchorAppearance);
  const adapter = buildThreeScene(currentSceneBase, (entityId, slot) => materials.resolve(entityId, slot));
  return { materials, adapter };
}

test("S6 covers every confirmed wall/column face plus the inferred laundry wall", () => {
  const before = sceneGeometryDigest(currentSceneBase);
  const { materials, adapter } = setup();
  const result = applyFh06FullWallTiles(adapter, currentSceneBase);
  assert.equal(result.surfaceCount, 4);
  assert.equal(result.confirmedSurfaceCount, 3);
  assert.equal(result.inferredSurfaceCount, 1);
  assert.equal(result.tileGridMm, 400);
  assert.equal(result.groutMm, 2);
  assert.ok(result.surfaceIds.some(id => id.includes("wall-main")));
  assert.ok(result.surfaceIds.some(id => id.includes("column-front")));
  assert.ok(result.surfaceIds.some(id => id.includes("column-return")));
  assert.ok(result.surfaceIds.includes("scene/traditional/environment/inferred-laundry-wall/tile-surface"));
  assert.equal(sceneGeometryDigest(currentSceneBase), before);

  const root = adapter.scene.getObjectByName("fh06-full-wall-tile");
  assert.ok(root);
  assert.equal(root.userData.appearanceOnly, true);
  assert.equal(root.userData.fullWallCoverage, true);
  assert.equal(root.children.length, 4);
  materials.dispose();
});

test("S6 inferred laundry tile plane closes the exact module01 span and uses two independent back-plane evidences", () => {
  const { materials, adapter } = setup();
  applyFh06FullWallTiles(adapter, currentSceneBase);
  const surface = adapter.scene.getObjectByName("scene/traditional/environment/inferred-laundry-wall/tile-surface");
  assert.ok(surface);
  assert.equal(surface.userData.status, "inferred");
  assert.ok(surface.userData.evidenceRefs.some(ref => ref.includes("module01-back-plane-y8638.827")));
  assert.ok(surface.userData.evidenceRefs.some(ref => ref.includes("washer-back-plane-y8638.81")));
  const base = surface.getObjectByName("scene/traditional/environment/inferred-laundry-wall/tile-surface/tile-base");
  assert.ok(base);
  base.updateWorldMatrix(true, true);
  const bounds = new Box3().setFromObject(base);
  assert.ok(Math.abs(bounds.min.x - 1568.684) <= 0.001);
  assert.ok(Math.abs(bounds.max.x - 2331.934) <= 0.001);
  assert.ok(Math.abs((bounds.max.x - bounds.min.x) - 763.25) <= 0.001);
  assert.ok(Math.abs(bounds.min.y - 0) <= 0.001);
  assert.ok(Math.abs(bounds.max.y - 2601.63) <= 0.001);
  materials.dispose();
});

test("S6 wall tiling is idempotent and does not accumulate duplicate overlays", () => {
  const { materials, adapter } = setup();
  applyFh06FullWallTiles(adapter, currentSceneBase);
  applyFh06FullWallTiles(adapter, currentSceneBase);
  const roots = adapter.scene.children.filter(child => child.name === "fh06-full-wall-tile");
  assert.equal(roots.length, 1);
  materials.dispose();
});
