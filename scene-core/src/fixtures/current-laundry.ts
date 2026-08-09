import type { BoxGeometry, ModuleGeometry } from "../contracts/model.js";
import { MODULE_GEOMETRY_SCHEMA_VERSION } from "../contracts/model.js";
import type { RigidTransform } from "../core/math.js";

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

export const module01: ModuleGeometry = {
  id: "scene/traditional/module/upper-laundry",
  kind: "module",
  schemaVersion: MODULE_GEOMETRY_SCHEMA_VERSION,
  transform: t(1568.684, 8288.827, 1697.064),
  visibilityIntent: "auto",
  defaultVisible: true,
  controllable: true,
  mountPolicy: "standalone",
  dimensions: {
    nominalMm: { width: 763.3, height: 700, depth: 350 },
    geometryMm: { width: 763.25, height: 700, depth: 350 },
    conflictPolicy: "geometry-wins-for-assembly-preserve-nominal",
    evidence: [
      { source: "promob-property", status: "confirmed", reference: "module-01-properties:763.3x700x350@1568.7,8638.8,1697.1" },
      { source: "promob-dxf", status: "confirmed", reference: "placement:LAYER42-57" }
    ]
  },
  structuralEnvelope: { min: { x: 0, y: 0, z: 0 }, max: { x: 763.25, y: 350, z: 700 } },
  renderEnvelope: { min: { x: 0, y: -18, z: 0 }, max: { x: 763.25, y: 350, z: 700 } },
  geometry: [
    box("scene/traditional/module/upper-laundry/back", "back", t(8, 344, 8), 747.25, 684, 6, "LAYER42"),
    box("scene/traditional/module/upper-laundry/bottom", "bottom", t(18, 0, 0), 727.25, 18, 350, "LAYER43"),
    box("scene/traditional/module/upper-laundry/top", "top", t(18, 0, 682), 727.25, 18, 350, "LAYER44"),
    box("scene/traditional/module/upper-laundry/left-side", "side", t(0, 0, 0), 18, 700, 350, "LAYER45"),
    box("scene/traditional/module/upper-laundry/right-side", "side", t(745.25, 0, 0), 18, 700, 350, "LAYER46"),
    box("scene/traditional/module/upper-laundry/shelf", "shelf", t(18, 20, 341), 727.25, 18, 324, "LAYER47"),
    box("scene/traditional/module/upper-laundry/front/door-left", "front", t(3, -18, 4), 377.125, 693, 18, "LAYER53"),
    box("scene/traditional/module/upper-laundry/front/door-right", "front", t(383.125, -18, 4), 377.125, 693, 18, "LAYER48")
  ],
  applianceSlots: []
};
