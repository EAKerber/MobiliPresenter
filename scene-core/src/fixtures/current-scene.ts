import type { SceneItem, ScenePackage } from "../contracts/model.js";
import {
  MOBILIPRESENTER_COORDINATE_SYSTEM,
  SCENE_PACKAGE_SCHEMA_VERSION,
  identityTransform
} from "../contracts/model.js";
import { currentFixedCamera, currentPresentationFrame } from "./current-camera.js";
import { currentEnvironment, currentModules, module02, module06 } from "./current-geometry.js";

export const currentItems: readonly SceneItem[] = [
  {
    id: "scene/traditional/appliance/oven",
    kind: "appliance",
    definitionId: "AP-OVEN-01",
    transform: identityTransform(),
    visibilityIntent: "auto",
    defaultVisible: true,
    controllable: true,
    mountPolicy: "hosted",
    hostId: module02.id,
    slotId: module02.applianceSlots[0]!.id
  },
  {
    id: "scene/traditional/appliance/microwave",
    kind: "appliance",
    definitionId: "AP-MICRO-01",
    transform: identityTransform(),
    visibilityIntent: "auto",
    defaultVisible: true,
    controllable: true,
    mountPolicy: "hosted",
    hostId: module06.id,
    slotId: module06.applianceSlots[0]!.id
  }
];

export const currentSceneBase: ScenePackage = {
  schemaVersion: SCENE_PACKAGE_SCHEMA_VERSION,
  sceneId: "traditional-complete",
  coordinateSystem: MOBILIPRESENTER_COORDINATE_SYSTEM,
  camera: currentFixedCamera,
  presentationFrame: currentPresentationFrame,
  environment: [currentEnvironment],
  items: currentItems,
  modules: currentModules,
  sourceBindings: []
};
