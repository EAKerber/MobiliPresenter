import assert from "node:assert/strict";
import test from "node:test";
import {
  allSceneEntities,
  applyTransform,
  currentFixedCamera,
  currentSceneBase,
  projectPoint,
  quaternionFromAxisAngle,
  resolveItemPlacementTransform,
  setVisibilityIntent,
  vec3
} from "@mobilipresenter/scene-core";
import { MeshBasicMaterial, Vector3 } from "three";
import {
  sceneTransformToThreeMatrix,
  sceneVectorToThree,
  threeVectorToScene
} from "../dist-ts/src/renderer/three/coordinates.js";
import {
  createThreeCamera,
  projectScenePointWithThree,
  updateThreeCameraViewport
} from "../dist-ts/src/renderer/three/camera.js";
import {
  buildThreeScene,
  syncThreeVisibility
} from "../dist-ts/src/renderer/three/scene-adapter.js";

function almost(actual, expected, epsilon = 1e-7) {
  assert.ok(Math.abs(actual - expected) <= epsilon, `${actual} != ${expected}`);
}

function vectorAlmost(actual, expected, epsilon = 1e-7) {
  almost(actual.x, expected.x, epsilon);
  almost(actual.y, expected.y, epsilon);
  almost(actual.z, expected.z, epsilon);
}

test("Scene->Three coordinate conversion preserves rigid transforms", () => {
  const transform = {
    translationMm: vec3(1200, 530, 760),
    rotation: quaternionFromAxisAngle(vec3(0.2, 0.8, 0.5), Math.PI / 3)
  };
  const point = vec3(120, 45, 600);
  const expected = sceneVectorToThree(applyTransform(transform, point));
  const actual = sceneVectorToThree(point).applyMatrix4(sceneTransformToThreeMatrix(transform));
  vectorAlmost(actual, expected);
  const back = threeVectorToScene(actual);
  const expectedScene = applyTransform(transform, point);
  vectorAlmost(back, expectedScene);
});

test("Three off-axis camera reproduces Scene Core projection", () => {
  const viewport = { widthPx: 1865, heightPx: 967 };
  const camera = createThreeCamera(currentFixedCamera, viewport);
  const points = [
    vec3(3073.7, 8102.4, 102),
    vec3(4264.7, 8102.4, 103),
    vec3(3882.4, 8232.4, 1604),
    vec3(5498.9, 8040.4, 2397),
    vec3(4280.044, 8184.396, 680.8759)
  ];
  for (const point of points) {
    const core = projectPoint(currentFixedCamera, viewport, point);
    const three = projectScenePointWithThree(camera, viewport, point);
    almost(three[0], core.xPx, 1e-6);
    almost(three[1], core.yPx, 1e-6);
  }
});

test("viewport resize changes only projection sampling, not physical camera transform", () => {
  const camera = createThreeCamera(currentFixedCamera, { widthPx: 1865, heightPx: 967 });
  const positionBefore = camera.position.clone();
  const quaternionBefore = camera.quaternion.clone();
  updateThreeCameraViewport(camera, currentFixedCamera, { widthPx: 1000, heightPx: 700 });
  vectorAlmost(camera.position, positionBefore);
  almost(camera.quaternion.angleTo(quaternionBefore), 0, 1e-12);
});

test("scene adapter creates one stable group per semantic entity", () => {
  const adapter = buildThreeScene(currentSceneBase, () => new MeshBasicMaterial());
  assert.equal(adapter.entityGroups.size, allSceneEntities(currentSceneBase).length);
  for (const entity of allSceneEntities(currentSceneBase)) {
    assert.ok(adapter.entityGroups.has(entity.id), entity.id);
  }
});

test("hosted fixture group is placed at Scene Core slot transform", () => {
  const adapter = buildThreeScene(currentSceneBase, () => new MeshBasicMaterial());
  const sink = currentSceneBase.items.find(item => item.definitionId === "FX-SINK-01");
  assert.ok(sink);
  const expected = sceneVectorToThree(resolveItemPlacementTransform(currentSceneBase, sink).translationMm);
  const group = adapter.entityGroups.get(sink.id);
  assert.ok(group);
  const actual = new Vector3().setFromMatrixPosition(group.matrix);
  vectorAlmost(actual, expected);
});

test("hide/show updates Object3D.visible without rebuilding groups", () => {
  const adapter = buildThreeScene(currentSceneBase, () => new MeshBasicMaterial());
  const moduleId = "scene/traditional/module/upper-sink-microwave";
  const microwaveId = "scene/traditional/appliance/microwave";
  const moduleGroup = adapter.entityGroups.get(moduleId);
  const microwaveGroup = adapter.entityGroups.get(microwaveId);
  assert.ok(moduleGroup && microwaveGroup);
  const hidden = setVisibilityIntent(currentSceneBase, moduleId, "off");
  syncThreeVisibility(adapter, hidden);
  assert.equal(moduleGroup.visible, false);
  assert.equal(microwaveGroup.visible, false);
  assert.equal(adapter.entityGroups.get(moduleId), moduleGroup);
  assert.equal(adapter.entityGroups.get(microwaveId), microwaveGroup);
});
