import assert from "node:assert/strict";
import test from "node:test";
import {
  applyTransform,
  composeTransforms,
  invertTransform,
  quaternionFromAxisAngle,
  vec3
} from "../dist/src/core/math.js";

function almostEqual(actual, expected, epsilon = 1e-9) {
  assert.ok(Math.abs(actual - expected) <= epsilon, `${actual} != ${expected}`);
}

test("local -> world -> local round-trip is stable", () => {
  const transform = {
    translationMm: vec3(1200, 530, 760),
    rotation: quaternionFromAxisAngle(vec3(0, 0, 1), Math.PI / 3)
  };
  const local = vec3(123.4, 55.6, 789.1);
  const world = applyTransform(transform, local);
  const roundTrip = applyTransform(invertTransform(transform), world);
  almostEqual(roundTrip.x, local.x);
  almostEqual(roundTrip.y, local.y);
  almostEqual(roundTrip.z, local.z);
});

test("composed rigid transforms equal sequential application", () => {
  const a = {
    translationMm: vec3(100, 200, 300),
    rotation: quaternionFromAxisAngle(vec3(0, 0, 1), Math.PI / 2)
  };
  const b = {
    translationMm: vec3(25, 0, 10),
    rotation: quaternionFromAxisAngle(vec3(1, 0, 0), Math.PI / 6)
  };
  const p = vec3(5, 7, 11);
  const sequential = applyTransform(a, applyTransform(b, p));
  const composed = applyTransform(composeTransforms(a, b), p);
  almostEqual(composed.x, sequential.x);
  almostEqual(composed.y, sequential.y);
  almostEqual(composed.z, sequential.z);
});
