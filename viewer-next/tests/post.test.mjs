import assert from "node:assert/strict";
import test from "node:test";
import { currentFixedCamera } from "@mobilipresenter/scene-core";
import { Layers, Object3D } from "three";
import { createThreeCamera } from "../dist-ts/src/renderer/three/camera.js";
import { BLOOM_LAYER } from "../dist-ts/src/renderer/three/lighting.js";
import { createBloomCamera, objectParticipatesInBloom } from "../dist-ts/src/renderer/three/post.js";

test("bloom camera sees only semantic emitter layer", () => {
  const camera = createThreeCamera(currentFixedCamera, { widthPx: 1865, heightPx: 967 });
  const bloomCamera = createBloomCamera(camera);
  const defaultObject = new Object3D();
  const emitter = new Object3D();
  emitter.layers.enable(BLOOM_LAYER);
  assert.equal(objectParticipatesInBloom(bloomCamera, defaultObject.layers.mask), false);
  assert.equal(objectParticipatesInBloom(bloomCamera, emitter.layers.mask), true);
});

test("bloom camera preserves fixed physical/projection state but overrides layer mask", () => {
  const camera = createThreeCamera(currentFixedCamera, { widthPx: 1865, heightPx: 967 });
  const bloomCamera = createBloomCamera(camera);
  assert.deepEqual(bloomCamera.position.toArray(), camera.position.toArray());
  assert.deepEqual(bloomCamera.quaternion.toArray(), camera.quaternion.toArray());
  assert.deepEqual(bloomCamera.projectionMatrix.toArray(), camera.projectionMatrix.toArray());
  const bloomLayers = new Layers();
  bloomLayers.set(BLOOM_LAYER);
  assert.equal(bloomCamera.layers.mask, bloomLayers.mask);
  assert.notEqual(bloomCamera.layers.mask, camera.layers.mask);
});
