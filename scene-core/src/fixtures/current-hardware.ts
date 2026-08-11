import type { HardwareAnchor, HardwareDefinition } from "../contracts/hardware.js";
import {
  HARDWARE_ANCHOR_SCHEMA_VERSION,
  HARDWARE_DEFINITION_SCHEMA_VERSION
} from "../contracts/hardware.js";
import { module03 } from "./current-geometry.js";

export const currentHardwareDefinitions: readonly HardwareDefinition[] = [
  {
    schemaVersion: HARDWARE_DEFINITION_SCHEMA_VERSION,
    id: "tango-128",
    family: "bar-handle",
    mountSpacingMm: 128,
    barLengthMm: 160,
    barWidthMm: 11,
    barDepthMm: 7,
    standoffDepthMm: 22,
    supportWidthMm: 11
  },
  {
    schemaVersion: HARDWARE_DEFINITION_SCHEMA_VERSION,
    id: "rigato-point",
    family: "point-handle",
    radiusMm: 10,
    depthMm: 25,
    frontCap: "flat"
  }
];

const anchor = (value: Omit<HardwareAnchor, "schemaVersion" | "hostEntityId" | "surface" | "normalOffsetMm" | "hardwareDefinitionId" | "status" | "evidenceRefs">): HardwareAnchor => ({
  schemaVersion: HARDWARE_ANCHOR_SCHEMA_VERSION,
  hostEntityId: module03.id,
  surface: "front",
  normalOffsetMm: 4,
  hardwareDefinitionId: "tango-128",
  status: "inferred",
  evidenceRefs: ["v7-i4.1:balcao-1182-handle-slots", "revalidated-against-current-module03-front-face"],
  ...value
});

export const currentHardwareAnchors: readonly HardwareAnchor[] = [
  anchor({
    id: "scene/traditional/hardware-anchor/lower-sink/drawer-1",
    hostGeometryId: "scene/traditional/module/lower-sink/front/drawer-1",
    placement: { type: "centered" },
    orientation: "horizontal"
  }),
  anchor({
    id: "scene/traditional/hardware-anchor/lower-sink/drawer-2",
    hostGeometryId: "scene/traditional/module/lower-sink/front/drawer-2",
    placement: { type: "centered" },
    orientation: "horizontal"
  }),
  anchor({
    id: "scene/traditional/hardware-anchor/lower-sink/drawer-3",
    hostGeometryId: "scene/traditional/module/lower-sink/front/drawer-3",
    placement: { type: "centered" },
    orientation: "horizontal"
  }),
  anchor({
    id: "scene/traditional/hardware-anchor/lower-sink/drawer-4",
    hostGeometryId: "scene/traditional/module/lower-sink/front/drawer-4",
    placement: { type: "centered" },
    orientation: "horizontal"
  }),
  anchor({
    id: "scene/traditional/hardware-anchor/lower-sink/door-center",
    hostGeometryId: "scene/traditional/module/lower-sink/front/door-center",
    placement: {
      type: "edge-offset-mm",
      horizontal: { from: "right", mm: 43.5 },
      vertical: { from: "top", mm: 97 }
    },
    orientation: "vertical"
  }),
  anchor({
    id: "scene/traditional/hardware-anchor/lower-sink/door-right",
    hostGeometryId: "scene/traditional/module/lower-sink/front/door-right",
    placement: {
      type: "edge-offset-mm",
      horizontal: { from: "left", mm: 43.5 },
      vertical: { from: "top", mm: 97 }
    },
    orientation: "vertical"
  })
];
