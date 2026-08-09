import type { BoxGeometry, EnvironmentGeometry, ModuleGeometry } from "../contracts/model.js";
import { ENVIRONMENT_GEOMETRY_SCHEMA_VERSION, MODULE_GEOMETRY_SCHEMA_VERSION } from "../contracts/model.js";
import type { RigidTransform } from "../core/math.js";
import { module03 } from "./current-geometry.js";

const t = (x: number, y: number, z: number): RigidTransform => ({
  translationMm: { x, y, z },
  rotation: { x: 0, y: 0, z: 0, w: 1 }
});

const box = (
  id: string,
  role: BoxGeometry["role"],
  transform: RigidTransform,
  width: number,
  height: number,
  depth: number,
  layer: string,
  materialSlot?: string
): BoxGeometry => ({
  id,
  primitive: "box",
  role,
  localTransform: transform,
  sizeMm: { width, height, depth },
  sourceBindingIds: [`placement:${layer}`],
  materialSlot: materialSlot ?? (role === "front" ? "front" : "carcass")
});

export const glassDivider: EnvironmentGeometry = {
  id: "scene/traditional/environment/glass-divider",
  kind: "environment",
  schemaVersion: ENVIRONMENT_GEOMETRY_SCHEMA_VERSION,
  transform: t(3063.739, 8032.528, 0),
  visibilityIntent: "auto",
  defaultVisible: true,
  controllable: false,
  mountPolicy: "standalone",
  structuralEnvelope: { min: { x: 0, y: 0, z: 0 }, max: { x: 8, y: 400, z: 2601.63 } },
  geometry: [
    box("scene/traditional/environment/glass-divider/panel", "glass", t(0,0,0), 8, 2601.63, 400, "LAYER59", "glass")
  ]
};

export const module04: ModuleGeometry = {
  id: "scene/traditional/module/fridge-side",
  kind: "module",
  schemaVersion: MODULE_GEOMETRY_SCHEMA_VERSION,
  transform: t(5079.427, 8040.44, 0),
  visibilityIntent: "auto",
  defaultVisible: true,
  controllable: true,
  mountPolicy: "standalone",
  dimensions: {
    nominalMm: { width: 18, height: 2400, depth: 600 },
    geometryMm: { width: 18, height: 2400, depth: 610 },
    conflictPolicy: "geometry-wins-for-assembly-preserve-nominal",
    evidence: [
      { source: "technical-sheet", status: "provided", reference: "module-04-sheet" },
      { source: "promob-dxf", status: "confirmed", reference: "placement:LAYER114" }
    ]
  },
  structuralEnvelope: { min: {x:0,y:0,z:0}, max: {x:18,y:610,z:2400} },
  renderEnvelope: { min: {x:0,y:0,z:0}, max: {x:18,y:610,z:2400} },
  geometry: [
    box("scene/traditional/module/fridge-side/panel", "side", t(0,0,0), 18, 2400, 610, "LAYER114", "front")
  ],
  applianceSlots: []
};

export const module05: ModuleGeometry = {
  id: "scene/traditional/module/upper-stove",
  kind: "module",
  schemaVersion: MODULE_GEOMETRY_SCHEMA_VERSION,
  transform: t(3079.427, 8250.44, 1700),
  visibilityIntent: "auto",
  defaultVisible: true,
  controllable: true,
  mountPolicy: "standalone",
  dimensions: {
    nominalMm: { width: 800, height: 700, depth: 400 },
    geometryMm: { width: 800, height: 700, depth: 400 },
    conflictPolicy: "geometry-wins-for-assembly-preserve-nominal",
    evidence: [
      { source: "promob-property", status: "confirmed", reference: "module-05-properties" },
      { source: "promob-dxf", status: "confirmed", reference: "placement:LAYER60-75" }
    ]
  },
  structuralEnvelope: { min:{x:0,y:0,z:0}, max:{x:800,y:400,z:700} },
  renderEnvelope: { min:{x:0,y:-18,z:-215}, max:{x:800,y:400,z:700} },
  geometry: [
    box("scene/traditional/module/upper-stove/back", "back", t(8,394,8), 784,684,6,"LAYER60"),
    box("scene/traditional/module/upper-stove/bottom", "bottom", t(18,0,0),764,18,400,"LAYER61"),
    box("scene/traditional/module/upper-stove/top", "top", t(18,0,682),764,18,400,"LAYER62"),
    box("scene/traditional/module/upper-stove/left-side", "side", t(0,0,0),18,700,400,"LAYER63"),
    box("scene/traditional/module/upper-stove/right-side", "side", t(782,0,0),18,700,400,"LAYER64"),
    box("scene/traditional/module/upper-stove/shelf", "shelf", t(18,20,341),764,18,374,"LAYER65"),
    box("scene/traditional/module/upper-stove/front/door-left", "front", t(3,-18,4),395.5,693,18,"LAYER71"),
    box("scene/traditional/module/upper-stove/front/door-right", "front", t(401.5,-18,4),395.5,693,18,"LAYER66")
  ],
  applianceSlots: [
    {
      id: "scene/traditional/module/upper-stove/slot/hood",
      role: "hood",
      localTransform: t(100, 0, -215),
      clearSizeMm: { width: 600, height: 215, depth: 298 },
      defaultApplianceId: "AP-HOOD-01",
      status: "inferred",
      evidenceRefs: ["style-anchor:target-render", "appearance:AP-HOOD-01"]
    }
  ]
};

export const module07: ModuleGeometry = {
  id: "scene/traditional/module/upper-fridge",
  kind: "module",
  schemaVersion: MODULE_GEOMETRY_SCHEMA_VERSION,
  transform: t(5097.427, 8058.44, 1916),
  visibilityIntent: "auto",
  defaultVisible: true,
  controllable: true,
  mountPolicy: "standalone",
  dimensions: {
    nominalMm: { width: 800, height: 484, depth: 350 },
    geometryMm: { width: 800, height: 484, depth: 350 },
    conflictPolicy: "geometry-wins-for-assembly-preserve-nominal",
    evidence: [
      { source: "technical-sheet", status: "confirmed", reference: "module-07-sheet" },
      { source: "promob-property", status: "confirmed", reference: "module-07-properties" },
      { source: "promob-dxf", status: "confirmed", reference: "placement:LAYER99-113" }
    ]
  },
  structuralEnvelope: { min:{x:0,y:0,z:0}, max:{x:800,y:350,z:484} },
  renderEnvelope: { min:{x:0,y:-18,z:0}, max:{x:800,y:350,z:484} },
  geometry: [
    box("scene/traditional/module/upper-fridge/back", "back", t(8,344,8),784,468,6,"LAYER99"),
    box("scene/traditional/module/upper-fridge/bottom", "bottom", t(18,0,0),764,18,350,"LAYER100"),
    box("scene/traditional/module/upper-fridge/top", "top", t(18,0,466),764,18,350,"LAYER101"),
    box("scene/traditional/module/upper-fridge/left-side", "side", t(0,0,0),18,484,350,"LAYER102"),
    box("scene/traditional/module/upper-fridge/right-side", "side", t(782,0,0),18,484,350,"LAYER103"),
    box("scene/traditional/module/upper-fridge/front/door-left", "front", t(3,-18,4),395.5,477,18,"LAYER109"),
    box("scene/traditional/module/upper-fridge/front/door-right", "front", t(401.5,-18,4),395.5,477,18,"LAYER104")
  ],
  applianceSlots: []
};

export const module03WithSink: ModuleGeometry = {
  ...module03,
  applianceSlots: [
    ...module03.applianceSlots,
    {
      id: "scene/traditional/module/lower-sink/slot/sink",
      role: "kitchen-sink",
      localTransform: t(417.295, 63.956, 580.8759),
      clearSizeMm: { width: 382.087, height: 178.1241, depth: 382.085 },
      defaultApplianceId: "FX-SINK-01",
      status: "confirmed",
      evidenceRefs: ["promob-dxf:LAYER41", "style-anchor:kitchen-sink"]
    }
  ]
};
