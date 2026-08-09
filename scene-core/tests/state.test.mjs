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
import {
  listControllables,
  resolveEffectiveVisibility,
  semanticLayerForKind,
  setVisibilityIntent
} from "../dist/src/state/scene-state.js";

const moduleId = "scene/test/module/host";
const microwaveId = "scene/test/appliance/microwave";

function sceneFixture() {
  return {
    schemaVersion: SCENE_PACKAGE_SCHEMA_VERSION,
    sceneId: "test/state",
    coordinateSystem: MOBILIPRESENTER_COORDINATE_SYSTEM,
    camera: {
      id: "camera/main", mode: "fixed", projection: "perspective",
      positionMm: vec3(0, 0, 0), targetMm: vec3(0, 1000, 0), up: vec3(0, 0, 1),
      fovYDeg: 45, principalPointNormalized: [0.5, 0.5], nearMm: 1, farMm: 20000,
      status: "preview", evidenceRefs: []
    },
    environment: [{
      id: "scene/test/environment/base", kind: "environment",
      schemaVersion: ENVIRONMENT_GEOMETRY_SCHEMA_VERSION,
      transform: identityTransform(), visibilityIntent: "auto", defaultVisible: true,
      mountPolicy: "standalone", structuralEnvelope: { min: vec3(0,0,0), max: vec3(3000,100,2600) }, geometry: []
    }],
    items: [{
      id: microwaveId, kind: "appliance", definitionId: "AP-MICRO-01",
      transform: identityTransform(), visibilityIntent: "auto", defaultVisible: true,
      controllable: true, mountPolicy: "hosted", hostId: moduleId, slotId: `${moduleId}/slot/microwave`
    }],
    modules: [{
      id: moduleId, kind: "module", schemaVersion: MODULE_GEOMETRY_SCHEMA_VERSION,
      transform: identityTransform(), visibilityIntent: "auto", defaultVisible: true,
      controllable: true, mountPolicy: "standalone",
      dimensions: { geometryMm: { width: 1200, height: 800, depth: 400 }, conflictPolicy: "geometry-wins-for-assembly-preserve-nominal", evidence: [] },
      structuralEnvelope: { min: vec3(0,0,0), max: vec3(1200,400,800) },
      renderEnvelope: { min: vec3(0,-18,0), max: vec3(1200,400,800) }, geometry: [], applianceSlots: []
    }],
    sourceBindings: []
  };
}

test("semantic layers are ownership/state layers", () => {
  assert.equal(semanticLayerForKind("environment"), 0);
  assert.equal(semanticLayerForKind("appliance"), 1);
  assert.equal(semanticLayerForKind("fixture"), 1);
  assert.equal(semanticLayerForKind("accessory"), 1);
  assert.equal(semanticLayerForKind("module"), 2);
});

test("default hosted appliance follows visible host", () => {
  const resolved = resolveEffectiveVisibility(sceneFixture());
  assert.equal(resolved.get(moduleId)?.effectiveVisible, true);
  assert.equal(resolved.get(microwaveId)?.effectiveVisible, true);
});

test("explicit child off survives host hide/show", () => {
  let scene = setVisibilityIntent(sceneFixture(), microwaveId, "off");
  scene = setVisibilityIntent(scene, moduleId, "off");
  scene = setVisibilityIntent(scene, moduleId, "on");
  const resolved = resolveEffectiveVisibility(scene);
  assert.equal(resolved.get(microwaveId)?.intent, "off");
  assert.equal(resolved.get(microwaveId)?.effectiveVisible, false);
  assert.equal(resolved.get(microwaveId)?.reason, "intent-off");
});

test("child on while host hidden remembers intent but stays effectively hidden", () => {
  let scene = setVisibilityIntent(sceneFixture(), moduleId, "off");
  scene = setVisibilityIntent(scene, microwaveId, "on");
  let resolved = resolveEffectiveVisibility(scene);
  assert.equal(resolved.get(microwaveId)?.intent, "on");
  assert.equal(resolved.get(microwaveId)?.effectiveVisible, false);
  assert.equal(resolved.get(microwaveId)?.reason, "host-hidden");
  scene = setVisibilityIntent(scene, moduleId, "on");
  resolved = resolveEffectiveVisibility(scene);
  assert.equal(resolved.get(microwaveId)?.effectiveVisible, true);
});

test("controllability manifest excludes base environment by default", () => {
  assert.deepEqual(listControllables(sceneFixture()).map(entity => entity.id).sort(), [microwaveId, moduleId].sort());
});

test("visibility state survives JSON round-trip", () => {
  const changed = setVisibilityIntent(sceneFixture(), microwaveId, "off");
  const restored = JSON.parse(JSON.stringify(changed));
  assert.equal(resolveEffectiveVisibility(restored).get(microwaveId)?.reason, "intent-off");
});

test("host cycles are rejected", () => {
  const scene = sceneFixture();
  const cyclic = {
    ...scene,
    modules: [{ ...scene.modules[0], mountPolicy: "hosted", hostId: microwaveId }]
  };
  assert.equal(validateScenePackage(cyclic).some(issue => issue.code === "HOST_CYCLE"), true);
});
