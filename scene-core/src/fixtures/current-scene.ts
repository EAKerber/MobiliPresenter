import type { RigidTransform } from "../core/math.js";
import type { BoxGeometry, SceneItem, ScenePackage } from "../contracts/model.js";
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
import { module01 } from "./current-laundry.js";

const t = (x: number, y: number, z: number): RigidTransform => ({
  translationMm: { x, y, z },
  rotation: { x: 0, y: 0, z: 0, w: 1 }
});

const accessoryBox = (
  id: string,
  role: BoxGeometry["role"],
  width: number,
  height: number,
  depth: number,
  materialSlot: string,
  source: string
): BoxGeometry => ({
  id,
  primitive: "box",
  role,
  localTransform: identityTransform(),
  sizeMm: { width, height, depth },
  materialSlot,
  sourceBindingIds: [source]
});

export const currentItems: readonly SceneItem[] = [
  {
    id: "scene/traditional/appliance/washer",
    kind: "appliance",
    definitionId: "AP-WASHER-01",
    transform: t(1641.934, 7908.81, 0),
    targetEnvelopeMm: { width: 690, height: 990, depth: 730 },
    visibilityIntent: "auto",
    defaultVisible: true,
    controllable: true,
    mountPolicy: "standalone",
    placementStatus: "confirmed",
    evidenceRefs: ["promob-dxf:LAYER58", "promob-property:washer-envelope"]
  },
  {
    id: "scene/traditional/fixture/laundry-tank",
    kind: "fixture",
    definitionId: "AP-TANK-01",
    transform: t(2451.8365, 7944.14, 0),
    targetEnvelopeMm: { width: 500, height: 820, depth: 500 },
    visibilityIntent: "auto",
    defaultVisible: true,
    controllable: true,
    mountPolicy: "standalone",
    placementStatus: "inferred",
    evidenceRefs: ["style-anchor:laundry-tank", "inference:centered-on-column-envelope-and-backed-to-column-front"]
  },
  {
    id: "scene/traditional/appliance/freestanding-range",
    kind: "appliance",
    definitionId: "AP-RANGE-01",
    transform: t(3087.244, 8000.44, 0),
    targetEnvelopeMm: { width: 760, height: 970, depth: 650 },
    visibilityIntent: "auto",
    defaultVisible: true,
    controllable: true,
    mountPolicy: "standalone",
    placementStatus: "inferred",
    evidenceRefs: ["user-rule:module02-absent-means-freestanding-stove", "inference:centered-in-module02-zone-and-backed-to-main-wall", "appearance:AP-RANGE-01"]
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
    id: "scene/traditional/appliance/cooktop",
    kind: "appliance",
    definitionId: "AP-COOKTOP-01",
    transform: identityTransform(),
    visibilityIntent: "auto",
    defaultVisible: true,
    controllable: true,
    mountPolicy: "hosted",
    hostId: module02.id,
    slotId: module02.applianceSlots[1]!.id
  },
  {
    id: "scene/traditional/accessory/stove-countertop",
    kind: "accessory",
    definitionId: "ACC-STONE-COUNTERTOP",
    transform: t(0, -20, 759.9999),
    visibilityIntent: "auto",
    defaultVisible: true,
    controllable: true,
    mountPolicy: "hosted",
    hostId: module02.id,
    geometry: [
      accessoryBox("scene/traditional/accessory/stove-countertop/slab", "stone", 791.01, 36, 550, "stone", "placement:LAYER148")
    ]
  },
  {
    id: "scene/traditional/accessory/stove-plinth",
    kind: "accessory",
    definitionId: "ACC-PLINTH-LOWER",
    transform: t(0, -18.83, -99),
    visibilityIntent: "auto",
    defaultVisible: true,
    controllable: true,
    mountPolicy: "hosted",
    hostId: module02.id,
    geometry: [
      accessoryBox("scene/traditional/accessory/stove-plinth/body", "plinth", 791.01, 100, 348.83, "stone", "placement:LAYER145:slice-module02")
    ]
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
    id: "scene/traditional/accessory/sink-countertop",
    kind: "accessory",
    definitionId: "ACC-STONE-COUNTERTOP",
    transform: t(0, -20.002, 759),
    visibilityIntent: "auto",
    defaultVisible: true,
    controllable: true,
    mountPolicy: "hosted",
    hostId: module03WithSink.id,
    geometry: [
      accessoryBox("scene/traditional/accessory/sink-countertop/slab", "stone", 1216.68, 18, 550, "stone", "placement:LAYER40")
    ]
  },
  {
    id: "scene/traditional/accessory/sink-plinth",
    kind: "accessory",
    definitionId: "ACC-PLINTH-LOWER",
    transform: t(0, -18.83, -100),
    visibilityIntent: "auto",
    defaultVisible: true,
    controllable: true,
    mountPolicy: "hosted",
    hostId: module03WithSink.id,
    geometry: [
      accessoryBox("scene/traditional/accessory/sink-plinth/body", "plinth", 1216.68, 100, 348.83, "stone", "placement:LAYER145:slice-module03")
    ]
  },
  {
    id: "scene/traditional/appliance/hood",
    kind: "appliance",
    definitionId: "AP-HOOD-01",
    transform: identityTransform(),
    visibilityIntent: "auto",
    defaultVisible: true,
    controllable: true,
    mountPolicy: "hosted",
    hostId: module05.id,
    slotId: module05.applianceSlots[0]!.id
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
    id: "scene/traditional/accessory/under-cab-led-06",
    kind: "accessory",
    definitionId: "ACC-UNDERCAB-LED-01",
    transform: t(0, 0, -40.91),
    visibilityIntent: "auto",
    defaultVisible: true,
    controllable: true,
    mountPolicy: "hosted",
    hostId: module06.id,
    geometry: [
      accessoryBox("scene/traditional/accessory/under-cab-led-06/profile", "light-profile", 1200, 40.91, 32.02, "emissive", "placement:LAYER115")
    ]
  },
  {
    id: "scene/traditional/appliance/fridge",
    kind: "appliance",
    definitionId: "AP-FRIDGE-01",
    transform: t(5097.427, 7900.44, 0),
    targetEnvelopeMm: { width: 809, height: 1900, depth: 750 },
    visibilityIntent: "auto",
    defaultVisible: true,
    controllable: true,
    mountPolicy: "standalone",
    placementStatus: "confirmed",
    evidenceRefs: ["promob-dxf:LAYER116", "promob-property:fridge-envelope"]
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
  modules: [module01, module02, module03WithSink, module04, module05, module06, module07],
  sourceBindings: [],
  substitutionGroups: [
    {
      id: "scene/traditional/substitution/stove-zone",
      primaryEntityId: module02.id,
      replacementEntityId: "scene/traditional/appliance/freestanding-range",
      policy: "replacement-when-primary-hidden"
    }
  ]
};
