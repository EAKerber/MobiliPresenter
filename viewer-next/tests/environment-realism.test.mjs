import assert from "node:assert/strict";
import test from "node:test";
import {
  currentSceneBase,
  sceneGeometryDigest
} from "@mobilipresenter/scene-core";
import { RectAreaLight } from "three";
import { styleAnchorAppearance } from "../dist-ts/src/fixtures/style-anchor.js";
import {
  applyEnvironmentRealism,
  applyEnvironmentRealismLightingCalibration,
  ENVIRONMENT_REALISM_ID,
  ENVIRONMENT_REALISM_LIGHTING_CALIBRATION,
  ENVIRONMENT_REALISM_LIGHTING_CALIBRATION_ID,
  environmentRealismEnvironmentIntensity
} from "../dist-ts/src/renderer/three/environment-realism.js";
import { buildThreeLighting } from "../dist-ts/src/renderer/three/lighting.js";
import { ThreeMaterialRegistry } from "../dist-ts/src/renderer/three/materials.js";
import { buildThreeScene } from "../dist-ts/src/renderer/three/scene-adapter.js";
import { applyFh06FullWallTiles } from "../dist-ts/src/renderer/three/wall-tiles.js";

function setup() {
  const materials = new ThreeMaterialRegistry(styleAnchorAppearance);
  const adapter = buildThreeScene(currentSceneBase, (entityId, slot) => materials.resolve(entityId, slot));
  return { materials, adapter };
}

function close(actual, expected, epsilon = 1e-9) {
  assert.ok(Math.abs(actual - expected) <= epsilon, `${actual} != ${expected}`);
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
  assert.equal(result.daylightIntensity, 76);
  assert.equal(sceneGeometryDigest(currentSceneBase), before);

  const root = adapter.scene.getObjectByName("__environment-realism");
  assert.ok(root);
  assert.equal(root.userData.appearanceOnly, true);
  assert.equal(root.userData.presentationInferred, true);
  assert.equal(root.userData.realismId, ENVIRONMENT_REALISM_ID);
  assert.ok(root.userData.sourceRefs.some(ref => ref.includes("presentation-policy")));

  const daylight = root.getObjectByName("environment-realism/daylight");
  assert.ok(daylight instanceof RectAreaLight);
  assert.equal(daylight.intensity, 76);
  assert.equal(daylight.userData.colorTemperatureK, 6200);
  assert.ok(root.getObjectByName("environment-realism/window-glass"));
  assert.ok(root.getObjectByName("environment-realism/window-sill"));
  materials.dispose();
});

test("Environment Realism 0.2 balances the canonical studio rig around the window key", () => {
  const lighting = buildThreeLighting(currentSceneBase, styleAnchorAppearance);
  const ambient = lighting.baseLights.get("ambient");
  const key = lighting.baseLights.get("key-front-high");
  const fill = lighting.baseLights.get("fill-side");
  assert.ok(ambient && key && fill);

  const before = {
    ambient: ambient.intensity,
    key: key.intensity,
    fill: fill.intensity
  };
  const result = applyEnvironmentRealismLightingCalibration(lighting);

  assert.equal(result.calibrationId, ENVIRONMENT_REALISM_LIGHTING_CALIBRATION_ID);
  close(ambient.intensity, before.ambient * ENVIRONMENT_REALISM_LIGHTING_CALIBRATION.ambientScale);
  close(key.intensity, before.key * ENVIRONMENT_REALISM_LIGHTING_CALIBRATION.keyScale);
  close(fill.intensity, before.fill * ENVIRONMENT_REALISM_LIGHTING_CALIBRATION.fillScale);
  assert.equal(ambient.userData.appearanceOnlyCalibration, ENVIRONMENT_REALISM_LIGHTING_CALIBRATION_ID);
  assert.equal(key.userData.appearanceOnlyCalibration, ENVIRONMENT_REALISM_LIGHTING_CALIBRATION_ID);
  assert.equal(fill.userData.appearanceOnlyCalibration, ENVIRONMENT_REALISM_LIGHTING_CALIBRATION_ID);

  const baseEnvironment = styleAnchorAppearance.lighting.environment.relativeIntensity;
  close(
    environmentRealismEnvironmentIntensity(baseEnvironment),
    baseEnvironment * ENVIRONMENT_REALISM_LIGHTING_CALIBRATION.environmentScale
  );
});

test("realism lighting calibration can be reapplied after canonical lighting sync resets intensities", () => {
  const lighting = buildThreeLighting(currentSceneBase, styleAnchorAppearance);
  const ambient = lighting.baseLights.get("ambient");
  const key = lighting.baseLights.get("key-front-high");
  const fill = lighting.baseLights.get("fill-side");
  assert.ok(ambient && key && fill);

  const canonical = {
    ambient: ambient.intensity,
    key: key.intensity,
    fill: fill.intensity
  };
  applyEnvironmentRealismLightingCalibration(lighting);

  ambient.intensity = canonical.ambient;
  key.intensity = canonical.key;
  fill.intensity = canonical.fill;
  applyEnvironmentRealismLightingCalibration(lighting);

  close(ambient.intensity, canonical.ambient * ENVIRONMENT_REALISM_LIGHTING_CALIBRATION.ambientScale);
  close(key.intensity, canonical.key * ENVIRONMENT_REALISM_LIGHTING_CALIBRATION.keyScale);
  close(fill.intensity, canonical.fill * ENVIRONMENT_REALISM_LIGHTING_CALIBRATION.fillScale);
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