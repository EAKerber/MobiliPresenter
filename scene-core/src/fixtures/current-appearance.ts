import type { AccessoryDefinition, AppearancePackage, ApplianceDefinition, MaterialDefinition } from "../contracts/appearance.js";
import {
  ACCESSORY_DEFINITION_SCHEMA_VERSION,
  APPEARANCE_PACKAGE_SCHEMA_VERSION,
  APPLIANCE_DEFINITION_SCHEMA_VERSION,
  LIGHTING_POLICY_SCHEMA_VERSION,
  MATERIAL_DEFINITION_SCHEMA_VERSION
} from "../contracts/appearance.js";

const appliance = (value: Omit<ApplianceDefinition, "schemaVersion">): ApplianceDefinition => ({
  schemaVersion: APPLIANCE_DEFINITION_SCHEMA_VERSION,
  ...value
});

const accessory = (value: Omit<AccessoryDefinition, "schemaVersion">): AccessoryDefinition => ({
  schemaVersion: ACCESSORY_DEFINITION_SCHEMA_VERSION,
  ...value
});

const material = (value: Omit<MaterialDefinition, "schemaVersion">): MaterialDefinition => ({
  schemaVersion: MATERIAL_DEFINITION_SCHEMA_VERSION,
  ...value
});

export const currentAppearance: AppearancePackage = {
  schemaVersion: APPEARANCE_PACKAGE_SCHEMA_VERSION,
  applianceDefinitions: [
    appliance({ id: "AP-WASHER-01", role: "laundry-washer", appearanceFamily: "front-load-silver", nominalAppearanceMm: { width: 600, height: 850, depth: 660 }, fitPolicy: "fit-to-source-envelope-preserve-front-proportions", assetPolicy: "normalized-external-allowed", requiredVisualFeatures: ["large-smoked-circular-door", "upper-horizontal-control-band", "silver-satin-body"], materialSlots: ["inox-brushed", "black-glass"], emitters: [], sourceHints: ["Electrolux LSW11 is a style anchor only; Promob source envelope governs scene fit"] }),
    appliance({ id: "AP-TANK-01", role: "laundry-tank", appearanceFamily: "ceramic-pedestal-utility-sink", nominalAppearanceMm: { width: 500, height: 820, depth: 500 }, fitPolicy: "fixture-adjustable-preserve-basin-language", assetPolicy: "parametric-preferred", requiredVisualFeatures: ["deep-rectangular-white-basin", "central-pedestal"], materialSlots: ["ceramic-white"], emitters: [], sourceHints: ["project style anchor; stable fantasy fixture"] }),
    appliance({ id: "AP-RANGE-01", role: "freestanding-range", appearanceFamily: "inox-5-burner-freestanding-range", nominalAppearanceMm: { width: 760, height: 970, depth: 650 }, fitPolicy: "fit-to-source-envelope-preserve-front-proportions", assetPolicy: "normalized-external-allowed", requiredVisualFeatures: ["freestanding-oven-body", "top-burner-table", "dark-glass-oven-door", "horizontal-control-band", "inox-or-silver-finish"], materialSlots: ["inox-brushed", "black-glass", "dark-metal"], emitters: [], sourceHints: ["Electrolux FE5IC/FE5IB official dimensions used only as stable fantasy-family anchor; project scene placement remains inferred"] }),
    appliance({ id: "AP-OVEN-01", role: "built-in-oven", appearanceFamily: "inox-60cm-dark-glass", nominalAppearanceMm: { width: 596, height: 596, depth: 575 }, fitPolicy: "fit-to-slot-front-authoritative", assetPolicy: "normalized-external-allowed", requiredVisualFeatures: ["thin-inox-frame", "dark-glass-door", "horizontal-handle", "discreet-upper-controls"], materialSlots: ["inox-brushed", "black-glass"], emitters: [], sourceHints: ["Electrolux OE8 family official style anchor"] }),
    appliance({ id: "AP-COOKTOP-01", role: "cooktop", appearanceFamily: "4-burner-black-glass", nominalAppearanceMm: { width: 600, height: 60, depth: 520 }, fitPolicy: "top-surface-fit", assetPolicy: "parametric-preferred", requiredVisualFeatures: ["black-tempered-glass-top", "four-burners", "black-lightweight-grates"], materialSlots: ["black-glass", "dark-metal"], emitters: [], sourceHints: ["Electrolux KE4TP official style anchor"] }),
    appliance({ id: "AP-HOOD-01", role: "hood", appearanceFamily: "built-in-slim-inox-60cm", nominalAppearanceMm: { width: 600, height: 215, depth: 298 }, fitPolicy: "under-cab-fit", assetPolicy: "normalized-external-allowed", requiredVisualFeatures: ["slim-under-cab-body", "metal-filter", "brushed-inox", "task-led"], materialSlots: ["inox-brushed", "dark-metal"], emitters: [{ id: "hood-task-led", type: "line", colorTemperatureK: 3200, relativeIntensity: 0.55, localPositionNormalized: [0.5, 0.55, 0.04], localDirection: { x: 0, y: 0, z: -1 } }], sourceHints: ["Electrolux DE6RX official dimensional/style anchor"] }),
    appliance({ id: "AP-MICRO-01", role: "built-in-microwave", appearanceFamily: "black-glass-inox-60cm", nominalAppearanceMm: { width: 595, height: 389, depth: 393 }, fitPolicy: "letterbox-allowed-within-slot", assetPolicy: "normalized-external-allowed", requiredVisualFeatures: ["large-dark-glass-door-left", "narrow-right-control-column", "subtle-inox-trim"], materialSlots: ["black-glass", "inox-brushed"], emitters: [], sourceHints: ["Electrolux ME3BP official dimensional/style anchor"] }),
    appliance({ id: "AP-FRIDGE-01", role: "refrigerator", appearanceFamily: "inox-bottom-freezer-dispenser", nominalAppearanceMm: { width: 750, height: 1900, depth: 800 }, fitPolicy: "fit-to-environment-envelope", assetPolicy: "normalized-external-allowed", requiredVisualFeatures: ["tall-silver-body", "two-horizontal-zones", "front-water-dispenser", "discreet-vertical-handles"], materialSlots: ["inox-brushed", "dark-plastic"], emitters: [], sourceHints: ["Electrolux TF39 official style cues; project envelope controls dimensions"] }),
    appliance({ id: "FX-SINK-01", role: "kitchen-sink", appearanceFamily: "single-bowl-inox-undermount", nominalAppearanceMm: { width: 400, height: 180, depth: 340 }, fitPolicy: "stone-cutout-dependent", assetPolicy: "parametric-preferred", requiredVisualFeatures: ["single-rectangular-bowl", "rounded-corners", "brushed-inox", "simple-arched-chrome-faucet"], materialSlots: ["inox-brushed", "chrome"], emitters: [], sourceHints: ["project style anchor; kitchen sink confirmed as present fixture"] })
  ],
  accessoryDefinitions: [
    accessory({ id: "ACC-STONE-COUNTERTOP", role: "countertop", materialSlots: ["stone"], emitters: [], sourceHints: ["Promob DXF countertop geometry; material is variable by policy"] }),
    accessory({ id: "ACC-PLINTH-LOWER", role: "plinth", materialSlots: ["stone"], emitters: [], sourceHints: ["Promob DXF LAYER145 split by host module for state ownership"] }),
    accessory({ id: "ACC-UNDERCAB-LED-01", role: "under-cab-light", materialSlots: ["emissive"], emitters: [{ id: "under-cab-line", type: "line", colorTemperatureK: 3000, relativeIntensity: 0.65, localPositionNormalized: [0.5, 0.5, 0.5], localDirection: { x: 0, y: -0.7071067811865476, z: -0.7071067811865476 } }], sourceHints: ["Promob DXF LAYER115 preserves legacy 1200x40.91x32.02 placement envelope; FH-06.2 rear-corner 18mm profile contract controls runtime geometry and light direction"] })
  ],
  materials: [
    material({ id: "wall-white", mappingPolicy: "world-continuous", baseColorSrgb: "#F4F3EE", roughness: 0.86, metallic: 0, opacity: 1, transmission: 0 }),
    material({ id: "front-primary", mappingPolicy: "module-continuous", baseColorSrgb: "#A6A19A", roughness: 0.55, metallic: 0, opacity: 1, transmission: 0 }),
    material({ id: "front-wood", mappingPolicy: "module-continuous", baseColorSrgb: "#B77A43", roughness: 0.58, metallic: 0, opacity: 1, transmission: 0, physicalTextureScaleMm: [600, 1200], grainDirection: "world-z" }),
    material({ id: "carcass-white", mappingPolicy: "panel-local", baseColorSrgb: "#F8F8F6", roughness: 0.75, metallic: 0, opacity: 1, transmission: 0 }),
    material({ id: "inox-brushed", mappingPolicy: "panel-local", baseColorSrgb: "#B8BAB8", roughness: 0.36, metallic: 0.9, opacity: 1, transmission: 0, grainDirection: "u" }),
    material({ id: "black-glass", mappingPolicy: "panel-local", baseColorSrgb: "#111417", roughness: 0.12, metallic: 0.05, opacity: 0.92, transmission: 0.08 }),
    material({ id: "ceramic-white", mappingPolicy: "panel-local", baseColorSrgb: "#F6F5F0", roughness: 0.2, metallic: 0, opacity: 1, transmission: 0 }),
    material({ id: "stone-granite", mappingPolicy: "module-continuous", baseColorSrgb: "#BDB8AA", roughness: 0.5, metallic: 0, opacity: 1, transmission: 0, physicalTextureScaleMm: [600, 600] }),
    material({ id: "glass-clear", mappingPolicy: "world-continuous", baseColorSrgb: "#DCE7EA", roughness: 0.06, metallic: 0, opacity: 0.16, transmission: 0.92 }),
    material({ id: "dark-metal", mappingPolicy: "panel-local", baseColorSrgb: "#27292A", roughness: 0.42, metallic: 0.7, opacity: 1, transmission: 0 }),
    material({ id: "dark-plastic", mappingPolicy: "panel-local", baseColorSrgb: "#333638", roughness: 0.5, metallic: 0, opacity: 1, transmission: 0 }),
    material({ id: "chrome", mappingPolicy: "panel-local", baseColorSrgb: "#D6D8D8", roughness: 0.16, metallic: 1, opacity: 1, transmission: 0 }),
    material({ id: "emissive-warm", mappingPolicy: "panel-local", baseColorSrgb: "#F4D6A0", roughness: 0.3, metallic: 0.15, opacity: 1, transmission: 0, emissiveSrgb: "#FFD08A", emissiveIntensity: 1 }),
    material({ id: "under-cab-opal-3000k", mappingPolicy: "panel-local", baseColorSrgb: "#FFF1D6", roughness: 0.42, metallic: 0.05, opacity: 1, transmission: 0, emissiveSrgb: "#FFD7A3", emissiveIntensity: 1.1 })
  ],
  assignments: {
    defaultsBySlot: {
      wall: "wall-white",
      front: "front-primary",
      carcass: "carcass-white",
      stone: "stone-granite",
      glass: "glass-clear",
      emissive: "emissive-warm"
    },
    entityOverrides: {}
  },
  lighting: {
    schemaVersion: LIGHTING_POLICY_SCHEMA_VERSION,
    id: "LIGHT-CANONICAL-01",
    units: "relative-renderer-neutral",
    environment: { type: "neutral-room-pmrem", relativeIntensity: 0.28 },
    baseRig: [
      { id: "ambient", type: "ambient", relativeIntensity: 0.32, colorTemperatureK: 5200, softness: 1 },
      { id: "key-front-high", type: "directional", relativeIntensity: 0.72, colorTemperatureK: 5000, direction: { x: -0.12, y: 0.78, z: -0.61 }, softness: 0.8 },
      { id: "fill-side", type: "directional", relativeIntensity: 0.24, colorTemperatureK: 5600, direction: { x: 0.55, y: 0.82, z: -0.16 }, softness: 0.92 }
    ],
    semanticEmitters: "from-effective-visible-entities",
    post: { bloomEnabled: true, bloomStrength: 0.08, bloomRadius: 0.45, emitterMaskOnly: true, vignetteStrength: 0.02 }
  }
};
