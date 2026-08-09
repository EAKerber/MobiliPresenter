import assert from "node:assert/strict";
import test from "node:test";
import {
  currentAppearance,
  currentSceneBase,
  module06,
  setVisibilityIntent
} from "@mobilipresenter/scene-core";
import { DirectionalLight, Layers, RectAreaLight } from "three";
import {
  BLOOM_LAYER,
  buildThreeLighting,
  kelvinToColor
} from "../dist-ts/src/renderer/three/lighting.js";

test("canonical base rig contains ambient, key and fill with key-only shadows", () => {
  const adapter = buildThreeLighting(currentSceneBase, currentAppearance);
  assert.deepEqual([...adapter.baseLights.keys()].sort(), ["ambient", "fill-side", "key-front-high"]);
  const key = adapter.baseLights.get("key-front-high");
  const fill = adapter.baseLights.get("fill-side");
  assert.ok(key instanceof DirectionalLight);
  assert.ok(fill instanceof DirectionalLight);
  assert.equal(key.castShadow, true);
  assert.equal(fill.castShadow, false);
});

test("hood and under-cab LED resolve as independent semantic emitters", () => {
  const adapter = buildThreeLighting(currentSceneBase, currentAppearance);
  assert.equal(adapter.semanticGroups.size, 2);
  const names = [...adapter.semanticGroups.keys()].sort();
  assert.ok(names.some(name => name.includes("appliance/hood")));
  assert.ok(names.some(name => name.includes("under-cab-led-06")));
  for (const group of adapter.semanticGroups.values()) {
    const light = group.getObjectByName("semantic-light");
    assert.ok(light instanceof RectAreaLight);
    assert.equal(light.castShadow, false);
  }
});

test("semantic emitter visual is isolated on bloom layer while remaining visible to base camera layer", () => {
  const adapter = buildThreeLighting(currentSceneBase, currentAppearance);
  const bloomLayers = new Layers();
  bloomLayers.set(BLOOM_LAYER);
  const defaultLayers = new Layers();
  defaultLayers.set(0);
  for (const group of adapter.semanticGroups.values()) {
    const visual = group.getObjectByName("emitter-surface");
    assert.ok(visual);
    assert.equal(visual.layers.test(bloomLayers), true);
    assert.equal(visual.layers.test(defaultLayers), true);
    assert.equal(visual.userData.semanticEmitter, true);
  }
});

test("hiding module 06 removes only its under-cab emitter from resolved Three lighting", () => {
  const hiddenScene = setVisibilityIntent(currentSceneBase, module06.id, "off");
  const adapter = buildThreeLighting(hiddenScene, currentAppearance);
  assert.equal(adapter.semanticGroups.size, 1);
  const only = [...adapter.semanticGroups.keys()][0];
  assert.ok(only.includes("appliance/hood"));
});

test("kelvin conversion is deterministic and warmer light has stronger red than blue", () => {
  const warmA = kelvinToColor(3200);
  const warmB = kelvinToColor(3200);
  assert.deepEqual(warmA.toArray(), warmB.toArray());
  assert.ok(warmA.r > warmA.b);
  const daylight = kelvinToColor(5600);
  assert.ok(Math.abs(daylight.r - daylight.b) < Math.abs(warmA.r - warmA.b));
});
