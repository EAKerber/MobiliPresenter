import assert from "node:assert/strict";
import test from "node:test";
import {
  currentSceneBase,
  sceneGeometryDigest
} from "@mobilipresenter/scene-core";
import { RectAreaLight } from "three";
import { styleAnchorAppearance } from "../dist-ts/src/fixtures/style-anchor.js";
import { applyEnvironmentRealism, ENVIRONMENT_REALISM_ID } from "../dist-ts/src/renderer/three/environment-realism.js";
import { ThreeMaterialRegistry } from "../dist-ts/src/renderer/three/materials.js";
import { buildThreeScene } from "../dist-ts/src/renderer/three/scene-adapter.js";
import { applyFh06FullWallTiles } from "../dist-ts/src/renderer/three/wall-tiles.js";

function setup() {
  const materials = new ThreeMaterialRegistry(styleAnchorAppearance);
  const adapter = buildThreeScene(currentSceneBase, (entityId, slot) => materials.resolve(entityId, slot));
  return { materials, adapter };
}

test("Environment Realism adds presentation-only window daylight without changing Scene Core geometry", () => {
  const before = sceneGeometryDigest(currentSceneBase);
  const { materials, adapter } = setup();
  const result = applyEnvironmentRealism(adapter, currentSceneBase);

  assert.equal(result.realismId, ENVIRONMENT_REALISM_ID);
  assert.equal(result.daylightWindow, true);
  assert.equal(result.inferredPresentationGeometry, true);
  assert.ok(result.windowWidthMm > 500);
  assert.ok(result.windowHeightMm > 1400);
  assert.equal(sceneGeometryDigest(currentSceneBase), before);

  const root = adapter.scene.getObjectByName("__environment-realism");
  assert.ok(root);
  assert.equal(root.userData.appearanceOnly, true);
  assert.equal(root.userData.presentationInferred, true);
  assert.equal(root.userData.realismId, ENVIRONMENT_REALISM_ID);
  assert.ok(root.userData.sourceRefs.some(ref => ref.includes("presentation-policy")));

  const daylight = root.getObjectByName("environment-realism/daylight");
  assert.ok(daylight instanceof RectAreaLight);
  assert.equal(daylight.userData.colorTemperatureK, 6200);
  assert.ok(root.getObjectByName("environment-realism/window-glass"));
  assert.ok(root.getObjectByName("environment-realism/window-sill"));
  materials.dispose();
});

test("Environment Realism is idempotent and does not accumulate presentation roots", () => {
  const { materials, adapter } = setup();
  applyEnvironmentRealism(adapter, currentSceneBase);
  applyEnvironmentRealism(adapter, currentSceneBase);
  assert.equal(adapter.scene.children.filter(child => child.name === "__environment-realism").length, 1);
  materials.dispose();
});

test("realism tile mode recesses grout while legacy wall tiling remains available", () => {
  const { materials, adapter } = setup();
  const legacy = applyFh06FullWallTiles(adapter, currentSceneBase);
  assert.equal(legacy.microRelief, false);
  assert.equal(legacy.reliefMm, 0);

  const relief = applyFh06FullWallTiles(adapter, currentSceneBase, { microRelief: true });
  assert.equal(relief.microRelief, true);
  assert.ok(relief.reliefMm > 0 && relief.reliefMm < 1);

  const root = adapter.scene.getObjectByName("fh06-full-wall-tile");
  assert.ok(root);
  assert.equal(root.userData.microRelief, true);
  assert.equal(root.userData.reliefMm, relief.reliefMm);
  const firstSurface = root.children[0];
  assert.ok(firstSurface);
  assert.ok(firstSurface.children.some(child => child.name.includes("/tile-0-0")));
  materials.dispose();
});
