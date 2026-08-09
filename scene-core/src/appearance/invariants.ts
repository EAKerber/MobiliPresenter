import type { AppearancePackage } from "../contracts/appearance.js";
import type { ScenePackage } from "../contracts/model.js";

export interface AppearanceValidationIssue {
  readonly code: string;
  readonly path: string;
  readonly detail: string;
}

const within01 = (value: number): boolean => value >= 0 && value <= 1;

export function validateAppearancePackage(appearance: AppearancePackage): AppearanceValidationIssue[] {
  const issues: AppearanceValidationIssue[] = [];
  const applianceIds = new Set<string>();
  const materialIds = new Set<string>();

  for (let i = 0; i < appearance.materials.length; i++) {
    const material = appearance.materials[i]!;
    if (materialIds.has(material.id)) issues.push({ code: "MATERIAL_ID_DUPLICATE", path: `materials[${i}].id`, detail: material.id });
    materialIds.add(material.id);
    if (!/^#[0-9A-Fa-f]{6}$/.test(material.baseColorSrgb)) issues.push({ code: "MATERIAL_COLOR_INVALID", path: `materials[${i}].baseColorSrgb`, detail: material.baseColorSrgb });
    for (const [name, value] of [["roughness", material.roughness], ["metallic", material.metallic], ["opacity", material.opacity], ["transmission", material.transmission]] as const) {
      if (!within01(value)) issues.push({ code: "MATERIAL_PARAMETER_RANGE", path: `materials[${i}].${name}`, detail: String(value) });
    }
  }

  for (let i = 0; i < appearance.applianceDefinitions.length; i++) {
    const definition = appearance.applianceDefinitions[i]!;
    if (applianceIds.has(definition.id)) issues.push({ code: "APPLIANCE_ID_DUPLICATE", path: `applianceDefinitions[${i}].id`, detail: definition.id });
    applianceIds.add(definition.id);
    const size = definition.nominalAppearanceMm;
    if (!(size.width > 0 && size.height > 0 && size.depth > 0)) issues.push({ code: "APPLIANCE_DIMENSIONS_INVALID", path: `applianceDefinitions[${i}].nominalAppearanceMm`, detail: definition.id });
    for (const slot of definition.materialSlots) if (!materialIds.has(slot)) issues.push({ code: "APPLIANCE_MATERIAL_NOT_FOUND", path: `applianceDefinitions[${i}].materialSlots`, detail: slot });
    for (let e = 0; e < definition.emitters.length; e++) {
      const emitter = definition.emitters[e]!;
      if (!(emitter.colorTemperatureK >= 1000 && emitter.colorTemperatureK <= 12000)) issues.push({ code: "EMITTER_TEMPERATURE_INVALID", path: `applianceDefinitions[${i}].emitters[${e}]`, detail: String(emitter.colorTemperatureK) });
      if (emitter.relativeIntensity < 0) issues.push({ code: "EMITTER_INTENSITY_INVALID", path: `applianceDefinitions[${i}].emitters[${e}]`, detail: String(emitter.relativeIntensity) });
      if (emitter.localPositionNormalized.some(value => value < 0 || value > 1)) issues.push({ code: "EMITTER_POSITION_INVALID", path: `applianceDefinitions[${i}].emitters[${e}]`, detail: emitter.localPositionNormalized.join(",") });
    }
  }

  const lightIds = new Set<string>();
  for (let i = 0; i < appearance.lighting.baseRig.length; i++) {
    const light = appearance.lighting.baseRig[i]!;
    if (lightIds.has(light.id)) issues.push({ code: "LIGHT_ID_DUPLICATE", path: `lighting.baseRig[${i}].id`, detail: light.id });
    lightIds.add(light.id);
    if (light.relativeIntensity < 0 || !within01(light.softness)) issues.push({ code: "LIGHT_PARAMETER_INVALID", path: `lighting.baseRig[${i}]`, detail: light.id });
  }
  if (!appearance.lighting.post.emitterMaskOnly) issues.push({ code: "POST_EMITTER_MASK_REQUIRED", path: "lighting.post.emitterMaskOnly", detail: "bloom must be constrained to semantic emitter mask" });
  return issues;
}

export function validateAppearanceForScene(scene: ScenePackage, appearance: AppearancePackage): AppearanceValidationIssue[] {
  const issues = validateAppearancePackage(appearance);
  const definitions = new Set(appearance.applianceDefinitions.map(definition => definition.id));
  for (let i = 0; i < scene.items.length; i++) {
    const item = scene.items[i]!;
    if ((item.kind === "appliance" || item.kind === "fixture") && !definitions.has(item.definitionId)) {
      issues.push({ code: "SCENE_ITEM_DEFINITION_NOT_FOUND", path: `items[${i}].definitionId`, detail: item.definitionId });
    }
  }
  return issues;
}
