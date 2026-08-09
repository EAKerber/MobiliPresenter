import type { DxfInventory } from "../source/dxf.js";
import { compileModuleFromDxfInventory } from "../source/dxf.js";
import type { ScenePackage } from "../contracts/model.js";
import {
  ENVIRONMENT_GEOMETRY_SCHEMA_VERSION,
  MOBILIPRESENTER_COORDINATE_SYSTEM,
  SCENE_PACKAGE_SCHEMA_VERSION,
  identityTransform
} from "../contracts/model.js";

export const portableInventory: DxfInventory = {
  schemaVersion: "DxfInventory 0.1.0",
  source: {
    name: "portable-room-r12.dxf",
    bytes: 1234,
    sha256: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  },
  entityCount: 24,
  layers: {
    CABINET_BODY: {
      count: 12,
      entityTypes: ["LINE"],
      min: [100, 200, 0],
      max: [700, 760, 720],
      size: [600, 560, 720]
    },
    CABINET_FRONT: {
      count: 12,
      entityTypes: ["LINE"],
      min: [102, 182, 2],
      max: [698, 200, 718],
      size: [596, 18, 716]
    }
  }
};

export const portableCompiled = compileModuleFromDxfInventory(portableInventory, {
  id: "scene/portable-demo/module/cabinet-a",
  worldOriginMm: [100, 200, 0],
  nominalMm: { width: 600, height: 720, depth: 560 },
  expectedSourceSha256: portableInventory.source.sha256,
  bindings: [
    { id: "body", layer: "CABINET_BODY", role: "other", structural: true, materialSlot: "carcass-white" },
    { id: "front", layer: "CABINET_FRONT", role: "front", structural: false, materialSlot: "front-primary" }
  ]
});

export const portableScene: ScenePackage = {
  schemaVersion: SCENE_PACKAGE_SCHEMA_VERSION,
  sceneId: "portable-demo",
  coordinateSystem: MOBILIPRESENTER_COORDINATE_SYSTEM,
  camera: {
    id: "scene/portable-demo/camera/main",
    mode: "fixed",
    projection: "perspective",
    positionMm: { x: 400, y: -1800, z: 900 },
    targetMm: { x: 400, y: 400, z: 900 },
    up: { x: 0, y: 0, z: 1 },
    fovYDeg: 45,
    principalPointNormalized: [0.5, 0.5],
    nearMm: 1,
    farMm: 10000,
    status: "preview",
    evidenceRefs: ["synthetic-portability-fixture"]
  },
  environment: [{
    id: "scene/portable-demo/environment/wall",
    kind: "environment",
    schemaVersion: ENVIRONMENT_GEOMETRY_SCHEMA_VERSION,
    transform: identityTransform(),
    visibilityIntent: "auto",
    defaultVisible: true,
    controllable: false,
    mountPolicy: "standalone",
    structuralEnvelope: { min: { x: 0, y: 800, z: 0 }, max: { x: 1200, y: 801, z: 2400 } },
    geometry: []
  }],
  items: [],
  modules: [portableCompiled.module],
  sourceBindings: portableCompiled.sourceBindings
};
