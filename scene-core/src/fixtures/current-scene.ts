import type { RigidTransform } from "../core/math.js";
import type { SceneItem, ScenePackage } from "../contracts/model.js";
import {
  MOBILIPRESENTER_COORDINATE_SYSTEM,
  SCENE_PACKAGE_SCHEMA_VERSION,
  identityTransform
} from "../contracts/model.js";
import { currentFixedCamera, currentPresentationFrame } from "./current-camera.js";
import { currentEnvironment, module02, module06 } from "./current-geometry.js";
import {
  glassDivider,
  module03WithSink,
  module04,
  module05,
  module07
} from "./current-context.js";

const t = (x: number, y: number, z: number): RigidTransform => ({
  translationMm: { x, y, z },
  rotation: { x: 0, y: 0, z: 0, w: 1 }
});

export const currentItems: readonly SceneItem[] = [
  {
    id: "scene/traditional/appliance/washer",
    kind: "appliance",
    definitionId: "AP-WASHER-01",
    transform: t(1641.934, 7908.81, 0),
    visibilityIntent: "auto",
    defaultVisible: true,
    controllable: true,
    mountPolicy: "standalone"
  },
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
    id: "scene/traditional/fixture/kitchen-sink",
    kind: "fixture",
    definitionId: "FX-SINK-01",
    transform: identityTransform(),
    visibilityIntent: "auto",
    defaultVisible: true,
    controllable: true,
    mountPolicy: "hosted",
    hostId: module03WithSink.id,
    slotId: module03WithSink.applianceSlots[0]!.id
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
  },
  {
    id: "scene/traditional/appliance/fridge",
    kind: "appliance",
    definitionId: "AP-FRIDGE-01",
    transform: t(5097.427, 7900.44, 0),
    visibilityIntent: "auto",
    defaultVisible: true,
    controllable: true,
    mountPolicy: "standalone"
  }
];

export const currentSceneBase: ScenePackage = {
  schemaVersion: SCENE_PACKAGE_SCHEMA_VERSION,
  sceneId: "traditional-complete",
  coordinateSystem: MOBILIPRESENTER_COORDINATE_SYSTEM,
  camera: currentFixedCamera,
  presentationFrame: currentPresentationFrame,
  environment: [currentEnvironment, glassDivider],
  items: currentItems,
  modules: [module02, module03WithSink, module04, module05, module06, module07],
  sourceBindings: []
};
