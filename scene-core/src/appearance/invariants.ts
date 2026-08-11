import type { AppearancePackage, SemanticEmitterDefinition } from "../contracts/appearance.js";
import type { ScenePackage } from "../contracts/model.js";

export interface AppearanceValidationIssue {
  readonly code: string;
  readonly path: string;
  readonly detail: string;
}

const within01 = (value: number): boolean => value >= 0 && value <= 1;
const colorIsValid = (value: string): boolean => /^#[0-9A-Fa-f]{6}$/.test(value);

export function validateAppearancePackage(appearance: AppearancePackage): AppearanceValidationIssue[] {
  const issues: AppearanceValidationIssue[] = [];
  const definitionIds = new Set<string>();
  const materialIds = new Set<string>();

  for (let i = 0; i < appearance.materials.length; i++) {
    const material = appearance.materials[i]!;
    if (materialIds.has(material.id)) issues.push({ code: "MATERIAL_ID_DUPLICATE", path: `materials[${i}].id`, detail: material.id });
    materialIds.add(material.id);
    if (!colorIsValid(material.baseColorSrgb)) issues.push({ code: "MATERIAL_COLOR_INVALID", path: `materials[${i}].baseColorSrgb`, detail: material.baseColorSrgb });
    if (material.emissiveSrgb && !colorIsValid(material.emissiveSrgb)) issues.push({ code: "MATERIAL_EMISSIVE_COLOR_INVALID", path: `materials[${i}].emissiveSrgb`, detail: material.emissiveSrgb });
    if (material.emissiveIntensity !== undefined && material.emissiveIntensity < 0) issues.push({ code: "MATERIAL_EMISSIVE_INTENSITY_INVALID", path: `materials[${i}].emissiveIntensity`, detail: String(material.emissiveIntensity) });
    for (const [name, value] of [["roughness", material.roughness], ["metallic", material.metallic], ["opacity", material.opacity], ["transmission", material.transmission]] as const) {
      if (!within01(value)) issues.push({ code: "MATERIAL_PARAMETER_RANGE", path: `materials[${i}].${name}`, detail: String(value) });
    }
  }

  const slotResolvable = (slot: string): boolean => materialIds.has(slot) || appearance.assignments.defaultsBySlot[slot] !== undefined;

  const validateEmitters = (emitters: readonly SemanticEmitterDefinition[], path: string): void => {
    for (let e = 0; e < emitters.length; e++) {
      const emitter = emitters[e]!;
      if (!(emitter.colorTemperatureK >= 1000 && emitter.colorTemperatureK <= 12000)) issues.push({ code: "EMITTER_TEMPERATURE_INVALID", path: `${path}.emitters[${e}]`, detail: String(emitter.colorTemperatureK) });
      if (emitter.relativeIntensity < 0) issues.push({ code: "EMITTER_INTENSITY_INVALID", path: `${path}.emitters[${e}]`, detail: String(emitter.relativeIntensity) });
      if (emitter.localPositionNormalized.some(value => value < 0 || value > 1)) issues.push({ code: "EMITTER_POSITION_INVALID", path: `${path}.emitters[${e}]`, detail: emitter.localPositionNormalized.join(",") });
    }
  };

  for (let i = 0; i < appearance.applianceDefinitions.length; i++) {
    const definition = appearance.applianceDefinitions[i]!;
    if (definitionIds.has(definition.id)) issues.push({ code: "DEFINITION_ID_DUPLICATE", path: `applianceDefinitions[${i}].id`, detail: definition.id });
    definitionIds.add(definition.id);
    const size = definition.nominalAppearanceMm;
    if (!(size.width > 0 && size.height > 0 && size.depth > 0)) issues.push({ code: "APPLIANCE_DIMENSIONS_INVALID", path: `applianceDefinitions[${i}].nominalAppearanceMm`, detail: definition.id });
    for (const slot of definition.materialSlots) if (!slotResolvable(slot)) issues.push({ code: "APPLIANCE_MATERIAL_NOT_FOUND", path: `applianceDefinitions[${i}].materialSlots`, detail: slot });
    validateEmitters(definition.emitters, `applianceDefinitions[${i}]`);
  }

  for (let i = 0; i < appearance.accessoryDefinitions.length; i++) {
    const definition = appearance.accessoryDefinitions[i]!;
    if (definitionIds.has(definition.id)) issues.push({ code: "DEFINITION_ID_DUPLICATE", path: `accessoryDefinitions[${i}].id`, detail: definition.id });
    definitionIds.add(definition.id);
    for (const slot of definition.materialSlots) if (!slotResolvable(slot)) issues.push({ code: "ACCESSORY_MATERIAL_NOT_FOUND", path: `accessoryDefinitions[${i}].materialSlots`, detail: slot });
    validateEmitters(definition.emitters, `accessoryDefinitions[${i}]`);
  }

  for (const [slot, materialId] of Object.entries(appearance.assignments.defaultsBySlot)) {
    if (!materialIds.has(materialId)) issues.push({ code: "DEFAULT_MATERIAL_NOT_FOUND", path: `assignments.defaultsBySlot.${slot}`, detail: materialId });
  }
  for (const [entityId, overrides] of Object.entries(appearance.assignments.entityOverrides)) {
    for (const [slot, materialId] of Object.entries(overrides)) {
      if (!materialIds.has(materialId)) issues.push({ code: "OVERRIDE_MATERIAL_NOT_FOUND", path: `assignments.entityOverrides.${entityId}.${slot}`, detail: materialId });
    }
  }

  const lightIds = new Set<string>();
  for (let i = 0; i < appearance.lighting.baseRig.length; i++) {
    const light = appearance.lighting.baseRig[i]!;
    if (lightIds.has(light.id)) issues.push({ code: "LIGHT_ID_DUPLICATE", path: `lighting.baseRig[${i}].id`, detail: light.id });
    lightIds.add(light.id);
    if (light.relativeIntensity < 0 || !within01(light.softness)) issues.push({ code: "LIGHT_PARAMETER_INVALID", path: `lighting.baseRig[${i}]`, detail: light.id });
  }
  if (!within01(appearance.lighting.environment.relativeIntensity)) issues.push({ code: "ENVIRONMENT_INTENSITY_INVALID", path: "lighting.environment.relativeIntensity", detail: String(appearance.lighting.environment.relativeIntensity) });
  if (!appearance.lighting.post.emitterMaskOnly) issues.push({ code: "POST_EMITTER_MASK_REQUIRED", path: "lighting.post.emitterMaskOnly", detail: "bloom must be constrained to semantic emitter mask" });
  return issues;
}

export function validateAppearanceForScene(scene: ScenePackage, appearance: AppearancePackage): AppearanceValidationIssue[] {
  const issues = validateAppearancePackage(appearance);
  const applianceDefinitions = new Map(appearance.applianceDefinitions.map(definition => [definition.id, definition] as const));
  const accessoryDefinitions = new Set(appearance.accessoryDefinitions.map(definition => definition.id));
  const allDefinitions = new Set([...applianceDefinitions.keys(), ...accessoryDefinitions]);

  for (let i = 0; i < scene.items.length; i++) {
    const item = scene.items[i]!;
    if (!allDefinitions.has(item.definitionId)) {
      issues.push({ code: "SCENE_ITEM_DEFINITION_NOT_FOUND", path: `items[${i}].definitionId`, detail: item.definitionId });
      continue;
    }
    if (item.kind === "accessory" && !accessoryDefinitions.has(item.definitionId)) {
      issues.push({ code: "SCENE_ACCESSORY_DEFINITION_KIND_MISMATCH", path: `items[${i}].definitionId`, detail: item.definitionId });
    }
    if (item.kind !== "accessory") {
      const definition = applianceDefinitions.get(item.definitionId);
      if (!definition) continue;
      if ((definition.fitPolicy === "fit-to-source-envelope-preserve-front-proportions" || definition.fitPolicy === "fit-to-environment-envelope") && !item.targetEnvelopeMm) {
        issues.push({ code: "TARGET_ENVELOPE_REQUIRED", path: `items[${i}].targetEnvelopeMm`, detail: item.definitionId });
      }
    }
  }
  return issues;
}
