import assert from "node:assert/strict";
import test from "node:test";
import { vec3 } from "../dist/src/core/math.js";
import {
  ENVIRONMENT_GEOMETRY_SCHEMA_VERSION,
  MOBILIPRESENTER_COORDINATE_SYSTEM,
  MODULE_GEOMETRY_SCHEMA_VERSION,
  SCENE_PACKAGE_SCHEMA_VERSION,
  identityTransform
} from "../dist/src/contracts/model.js";
import { validateScenePackage } from "../dist/src/contracts/invariants.js";

function minimalScene() {
  return {
    schemaVersion: SCENE_PACKAGE_SCHEMA_VERSION,
    sceneId: "test/minimal",
    coordinateSystem: MOBILIPRESENTER_COORDINATE_SYSTEM,
    camera: {
      id: "camera/main",
      mode: "fixed",
      projection: "perspective",
      transform: identityTransform(),
      targetMm: vec3(0, 1000, 0),
      up: vec3(0, 0, 1),
      fovYDeg: 43.28,
      principalPointNormalized: [0.5, 0.5],
      nearMm: 1,
      farMm: 20000,
      status: "preview",
      evidenceRefs: []
    },
    environment: [{
      id: "scene/test/environment/wall",
      kind: "environment",
      schemaVersion: ENVIRONMENT_GEOMETRY_SCHEMA_VERSION,
      transform: identityTransform(),
      visibilityIntent: "auto",
      defaultVisible: true,
      mountPolicy: "standalone",
      structuralEnvelope: { min: vec3(0, 0, 0), max: vec3(3000, 100, 2600) },
      geometry: []
    }],
    modules: [{
      id: "scene/test/module/box",
      kind: "module",
      schemaVersion: MODULE_GEOMETRY_SCHEMA_VERSION,
      transform: identityTransform(),
      visibilityIntent: "auto",
      defaultVisible: true,
      mountPolicy: "standalone",
      dimensions: {
        nominalMm: { width: 1200, height: 800, depth: 400 },
        geometryMm: { width: 1200, height: 800, depth: 400 },
        conflictPolicy: "geometry-wins-for-assembly-preserve-nominal",
        evidence: []
      },
      structuralEnvelope: { min: vec3(0, 0, 0), max: vec3(1200, 400, 800) },
      renderEnvelope: { min: vec3(0, -18, 0), max: vec3(1200, 400, 800) },
      geometry: [],
      applianceSlots: []
    }],
    sourceBindings: []
  };
}

test("minimal second-scene fixture validates without project-specific ids", () => {
  assert.deepEqual(validateScenePackage(minimalScene()), []);
});

test("hosted entity must reference a host", () => {
  const scene = minimalScene();
  const module = scene.modules[0];
  const broken = { ...scene, modules: [{ ...module, mountPolicy: "hosted", hostId: "scene/test/module/missing" }] };
  assert.equal(validateScenePackage(broken).some(issue => issue.code === "HOST_NOT_FOUND"), true);
});

test("duplicate entity ids are rejected", () => {
  const scene = minimalScene();
  const environment = scene.environment[0];
  const duplicate = { ...scene, modules: [{ ...scene.modules[0], id: environment.id }] };
  assert.equal(validateScenePackage(duplicate).some(issue => issue.code === "ENTITY_ID_DUPLICATE"), true);
});
