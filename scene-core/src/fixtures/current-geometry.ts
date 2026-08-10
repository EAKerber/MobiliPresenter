import type {
  ApplianceFrontOpening,
  ApplianceSlot,
  BoxGeometry,
  EnvironmentGeometry,
  FaceGeometry,
  ModuleGeometry
} from "../contracts/model.js";
import {
  ENVIRONMENT_GEOMETRY_SCHEMA_VERSION,
  MODULE_GEOMETRY_SCHEMA_VERSION,
  identityTransform
} from "../contracts/model.js";
import type { RigidTransform, Vec3 } from "../core/math.js";

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
  sourceBindingId: string,
  materialSlot?: string
): BoxGeometry => ({
  id,
  primitive: "box",
  role,
  localTransform: transform,
  sizeMm: { width, height, depth },
  sourceBindingIds: [sourceBindingId],
  materialSlot: materialSlot ?? (role === "front" ? "front" : "carcass")
});

const face = (
  id: string,
  role: FaceGeometry["role"],
  transform: RigidTransform,
  uAxis: Vec3,
  vAxis: Vec3,
  normal: Vec3,
  uMm: number,
  vMm: number,
  sourceBindingId: string,
  materialSlot: string
): FaceGeometry => ({
  id,
  primitive: "face",
  role,
  localTransform: transform,
  uAxis,
  vAxis,
  normal,
  sizeMm: [uMm, vMm],
  sourceBindingIds: [sourceBindingId],
  materialSlot
});

const slot = (
  id: string,
  role: string,
  transform: RigidTransform,
  width: number,
  height: number,
  depth: number,
  defaultApplianceId: string,
  status: "confirmed" | "inferred",
  evidenceRefs: readonly string[],
  frontOpening?: ApplianceFrontOpening
): ApplianceSlot => ({
  id,
  role,
  localTransform: transform,
  clearSizeMm: { width, height, depth },
  defaultApplianceId,
  status,
  evidenceRefs,
  ...(frontOpening ? { frontOpening } : {})
});

export const currentEnvironment: EnvironmentGeometry = {
  id: "scene/traditional/environment/base",
  kind: "environment",
  schemaVersion: ENVIRONMENT_GEOMETRY_SCHEMA_VERSION,
  transform: identityTransform(),
  visibilityIntent: "auto",
  defaultVisible: true,
  mountPolicy: "standalone",
  structuralEnvelope: {
    min: { x: 2331.934, y: 8444.14, z: 0 },
    max: { x: 5906.427, y: 8650.44, z: 2601.63 }
  },
  geometry: [
    face("scene/traditional/environment/base/wall-main", "wall", t(3071.739, 8650.44, 0), { x: 1, y: 0, z: 0 }, { x: 0, y: 0, z: 1 }, { x: 0, y: -1, z: 0 }, 2834.688, 2601.63, "placement:LAYER-wall-main", "wall"),
    face("scene/traditional/environment/base/column-front", "column", t(2331.934, 8444.14, 0), { x: 1, y: 0, z: 0 }, { x: 0, y: 0, z: 1 }, { x: 0, y: -1, z: 0 }, 739.805, 2601.63, "placement:LAYER-column-front", "wall"),
    face("scene/traditional/environment/base/column-return", "column", t(3071.739, 8444.14, 0), { x: 0, y: 1, z: 0 }, { x: 0, y: 0, z: 1 }, { x: 1, y: 0, z: 0 }, 206.3, 2601.63, "placement:LAYER-column-return", "wall")
  ]
};

const MODULE02_NOMINAL_FRONT_OFFSET_X = (791.01 - 790) / 2;
const MODULE02_OVEN_OPENING_X = MODULE02_NOMINAL_FRONT_OFFSET_X + 95;
const MODULE02_OVEN_OPENING_Z = 80;
const MODULE02_FRONT_SOURCE = "design-default:fh06-1:module02-front-opening";

export const module02: ModuleGeometry = {
  id: "scene/traditional/module/lower-stove",
  kind: "module",
  schemaVersion: MODULE_GEOMETRY_SCHEMA_VERSION,
  transform: t(3071.739, 8120.44, 99),
  visibilityIntent: "auto",
  defaultVisible: true,
  mountPolicy: "standalone",
  dimensions: {
    nominalMm: { width: 790, height: 760, depth: 530 },
    geometryMm: { width: 791.01, height: 760, depth: 530 },
    conflictPolicy: "geometry-wins-for-assembly-preserve-nominal",
    evidence: [
      { source: "technical-sheet", status: "provided", reference: "module-02-sheet" },
      { source: "promob-dxf", status: "confirmed", reference: "placement:LAYER134-140" }
    ]
  },
  structuralEnvelope: { min: { x: 0, y: 0, z: 0 }, max: { x: 791.01, y: 530, z: 760 } },
  renderEnvelope: { min: { x: 0, y: -18, z: 0 }, max: { x: 791.01, y: 550, z: 796 } },
  geometry: [
    box("scene/traditional/module/lower-stove/left-side", "side", t(0, 0, 18), 18, 742, 530, "placement:LAYER134"),
    box("scene/traditional/module/lower-stove/right-side", "side", t(773.01, 0, 18), 18, 742, 530, "placement:LAYER135"),
    box("scene/traditional/module/lower-stove/bottom", "bottom", t(0, 0, 0), 791.01, 18, 530, "placement:LAYER136"),
    box("scene/traditional/module/lower-stove/rear-brace", "back", t(8, 525, 8), 775.01, 751, 5, "placement:LAYER137"),
    box("scene/traditional/module/lower-stove/top-front-rail", "top", t(18, 0, 742), 755.01, 18, 70, "placement:LAYER138"),
    box("scene/traditional/module/lower-stove/top-rear-rail", "top", t(18, 455, 742), 755.01, 18, 70, "placement:LAYER139"),
    box("scene/traditional/module/lower-stove/front/oven-left-stile", "front", t(MODULE02_NOMINAL_FRONT_OFFSET_X, -18, 0), 95, 760, 18, MODULE02_FRONT_SOURCE),
    box("scene/traditional/module/lower-stove/front/oven-right-stile", "front", t(MODULE02_OVEN_OPENING_X + 600, -18, 0), 95, 760, 18, MODULE02_FRONT_SOURCE),
    box("scene/traditional/module/lower-stove/front/oven-bottom-rail", "front", t(MODULE02_OVEN_OPENING_X, -18, 0), 600, 80, 18, MODULE02_FRONT_SOURCE),
    box("scene/traditional/module/lower-stove/front/oven-top-rail", "front", t(MODULE02_OVEN_OPENING_X, -18, 680), 600, 80, 18, MODULE02_FRONT_SOURCE)
  ],
  applianceSlots: [
    slot(
      "scene/traditional/module/lower-stove/slot/oven",
      "built-in-oven",
      t(18, 5, 18),
      755.01,
      724,
      525,
      "AP-OVEN-01",
      "confirmed",
      ["technical-sheet:module-02", "promob-dxf:LAYER134-139"],
      {
        localTransform: t(MODULE02_OVEN_OPENING_X, -18, MODULE02_OVEN_OPENING_Z),
        sizeMm: { width: 600, height: 600 },
        status: "inferred",
        evidenceRefs: ["user-reference:module02-oven-surround", "design-default:fh06-1:60cm-built-in-oven-opening"]
      }
    ),
    slot("scene/traditional/module/lower-stove/slot/cooktop", "cooktop", t(95.505, -5, 796), 600, 60, 520, "AP-COOKTOP-01", "inferred", ["style-anchor:target-render", "promob-dxf:LAYER148-countertop"])
  ]
};

export const module03: ModuleGeometry = {
  id: "scene/traditional/module/lower-sink",
  kind: "module",
  schemaVersion: MODULE_GEOMETRY_SCHEMA_VERSION,
  transform: t(3862.749, 8120.44, 100),
  visibilityIntent: "auto",
  defaultVisible: true,
  mountPolicy: "standalone",
  dimensions: {
    nominalMm: { width: 1200, height: 760, depth: 530 },
    geometryMm: { width: 1216.678, height: 760, depth: 530 },
    conflictPolicy: "geometry-wins-for-assembly-preserve-nominal",
    evidence: [
      { source: "technical-sheet", status: "provided", reference: "module-03-sheet" },
      { source: "promob-dxf", status: "confirmed", reference: "placement:LAYER5-11,LAYER120,LAYER124,LAYER129" }
    ]
  },
  structuralEnvelope: { min: { x: 0, y: 0, z: 0 }, max: { x: 1216.678, y: 530, z: 760 } },
  renderEnvelope: { min: { x: 0, y: -18, z: 0 }, max: { x: 1216.678, y: 550, z: 760 } },
  geometry: [
    box("scene/traditional/module/lower-sink/drawer-base", "bottom", t(0, 0, 0), 400, 18, 530, "placement:LAYER7"),
    box("scene/traditional/module/lower-sink/drawer-left-side", "side", t(0, 0, 18), 18, 742, 530, "placement:LAYER5"),
    box("scene/traditional/module/lower-sink/drawer-right-side", "side", t(382, 0, 18), 18, 742, 530, "placement:LAYER6"),
    box("scene/traditional/module/lower-sink/right-base", "bottom", t(400, 0, 0), 816.678, 18, 530, "placement:LAYER120"),
    box("scene/traditional/module/lower-sink/front/drawer-1", "front", t(2, -18, 570), 396, 187, 18, "placement:LAYER8"),
    box("scene/traditional/module/lower-sink/front/drawer-2", "front", t(2, -18, 381), 396, 187, 18, "placement:LAYER9"),
    box("scene/traditional/module/lower-sink/front/drawer-3", "front", t(2, -18, 192), 396, 187, 18, "placement:LAYER10"),
    box("scene/traditional/module/lower-sink/front/drawer-4", "front", t(2, -18, 3), 396, 187, 18, "placement:LAYER11"),
    box("scene/traditional/module/lower-sink/front/door-center", "front", t(402, -18, 3), 405.339, 754, 18, "placement:LAYER129"),
    box("scene/traditional/module/lower-sink/front/door-right", "front", t(809.339, -18, 3), 405.339, 754, 18, "placement:LAYER124")
  ],
  applianceSlots: []
};

export const module06: ModuleGeometry = {
  id: "scene/traditional/module/upper-sink-microwave",
  kind: "module",
  schemaVersion: MODULE_GEOMETRY_SCHEMA_VERSION,
  transform: t(3879.427, 8250.44, 1600),
  visibilityIntent: "auto",
  defaultVisible: true,
  mountPolicy: "standalone",
  dimensions: {
    nominalMm: { width: 1200, height: 800, depth: 400 },
    geometryMm: { width: 1200, height: 800, depth: 400 },
    conflictPolicy: "geometry-wins-for-assembly-preserve-nominal",
    evidence: [
      { source: "technical-sheet", status: "confirmed", reference: "module-06-sheet" },
      { source: "promob-property", status: "confirmed", reference: "module-06-properties" },
      { source: "promob-dxf", status: "confirmed", reference: "placement:LAYER76-93" }
    ]
  },
  structuralEnvelope: { min: { x: 0, y: 0, z: 0 }, max: { x: 1200, y: 400, z: 800 } },
  renderEnvelope: { min: { x: 0, y: -18, z: 0 }, max: { x: 1200, y: 400, z: 800 } },
  geometry: [
    box("scene/traditional/module/upper-sink-microwave/left-side", "side", t(0, 0, 0), 18, 800, 400, "placement:LAYER79"),
    box("scene/traditional/module/upper-sink-microwave/right-side", "side", t(1182, 0, 0), 18, 800, 400, "placement:LAYER80"),
    box("scene/traditional/module/upper-sink-microwave/bottom", "bottom", t(18, 0, 0), 1164, 18, 400, "placement:LAYER81"),
    box("scene/traditional/module/upper-sink-microwave/top", "top", t(18, 0, 782), 1164, 18, 400, "placement:LAYER82"),
    box("scene/traditional/module/upper-sink-microwave/right-divider", "divider", t(614, 6, 18), 18, 764, 394, "placement:LAYER76"),
    box("scene/traditional/module/upper-sink-microwave/left-shelf", "shelf", t(18, 6, 391), 596, 18, 394, "placement:LAYER78"),
    box("scene/traditional/module/upper-sink-microwave/right-shelf", "shelf", t(632, 6, 424), 550, 18, 394, "placement:LAYER77"),
    box("scene/traditional/module/upper-sink-microwave/front/door-left", "front", t(3, -18, 4), 307.5, 793, 18, "placement:LAYER88"),
    box("scene/traditional/module/upper-sink-microwave/front/door-center", "front", t(313.5, -18, 4), 307.5, 793, 18, "placement:LAYER83"),
    box("scene/traditional/module/upper-sink-microwave/front/lift", "front", t(625, -18, 428), 572, 369, 18, "placement:LAYER93")
  ],
  applianceSlots: [
    slot("scene/traditional/module/upper-sink-microwave/slot/microwave", "built-in-microwave", t(632, 6, 18), 550, 406, 394, "AP-MICRO-01", "confirmed", ["technical-sheet:module-06", "promob-dxf:LAYER76-82"])
  ]
};

export const currentModules: readonly ModuleGeometry[] = [module02, module03, module06];
