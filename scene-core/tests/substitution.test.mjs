import assert from "node:assert/strict";
import test from "node:test";
import {
  resolveEffectiveVisibility,
  setVisibilityIntent
} from "../dist/src/state/scene-state.js";
import {
  MOBILIPRESENTER_COORDINATE_SYSTEM,
  SCENE_PACKAGE_SCHEMA_VERSION,
  identityTransform
} from "../dist/src/contracts/model.js";
import { currentFixedCamera } from "../dist/src/fixtures/current-camera.js";

function scene() {
  const primary = {
    id: "module-primary",
    kind: "module",
    schemaVersion: "ModuleGeometry 0.1.0",
    transform: identityTransform(),
    visibilityIntent: "auto",
    defaultVisible: true,
    mountPolicy: "standalone",
    dimensions: {
      geometryMm: { width: 100, height: 100, depth: 100 },
      conflictPolicy: "geometry-wins-for-assembly-preserve-nominal",
      evidence: []
    },
    structuralEnvelope: { min: { x: 0, y: 0, z: 0 }, max: { x: 100, y: 100, z: 100 } },
    renderEnvelope: { min: { x: 0, y: 0, z: 0 }, max: { x: 100, y: 100, z: 100 } },
    geometry: [],
    applianceSlots: []
  };
  const replacement = {
    id: "replacement",
    kind: "appliance",
    definitionId: "AP-RANGE-01",
    transform: identityTransform(),
    targetEnvelopeMm: { width: 100, height: 100, depth: 100 },
    visibilityIntent: "auto",
    defaultVisible: true,
    controllable: true,
    mountPolicy: "standalone"
  };
  return {
    schemaVersion: SCENE_PACKAGE_SCHEMA_VERSION,
    sceneId: "substitution-test",
    coordinateSystem: MOBILIPRESENTER_COORDINATE_SYSTEM,
    camera: currentFixedCamera,
    environment: [],
    items: [replacement],
    modules: [primary],
    sourceBindings: [],
    substitutionGroups: [{
      id: "primary-or-replacement",
      primaryEntityId: primary.id,
      replacementEntityId: replacement.id,
      policy: "replacement-when-primary-hidden"
    }]
  };
}

test("replacement is suppressed while primary is visible", () => {
  const visibility = resolveEffectiveVisibility(scene());
  assert.equal(visibility.get("module-primary")?.effectiveVisible, true);
  assert.deepEqual(visibility.get("replacement"), {
    entityId: "replacement",
    intent: "auto",
    effectiveVisible: false,
    reason: "substitution-primary-visible"
  });
});

test("replacement appears automatically when primary is hidden", () => {
  const hidden = setVisibilityIntent(scene(), "module-primary", "off");
  const visibility = resolveEffectiveVisibility(hidden);
  assert.equal(visibility.get("module-primary")?.effectiveVisible, false);
  assert.equal(visibility.get("replacement")?.effectiveVisible, true);
});

test("explicit replacement off survives primary hide/show", () => {
  let current = setVisibilityIntent(scene(), "replacement", "off");
  current = setVisibilityIntent(current, "module-primary", "off");
  assert.equal(resolveEffectiveVisibility(current).get("replacement")?.effectiveVisible, false);
  current = setVisibilityIntent(current, "module-primary", "on");
  current = setVisibilityIntent(current, "module-primary", "off");
  const replacement = resolveEffectiveVisibility(current).get("replacement");
  assert.equal(replacement?.intent, "off");
  assert.equal(replacement?.effectiveVisible, false);
});
