import type { AppearancePackage, MaterialDefinition } from "../contracts/appearance.js";

export function resolveMaterialId(
  appearance: AppearancePackage,
  entityId: string,
  materialSlot: string
): string {
  const entityOverride = appearance.assignments.entityOverrides[entityId]?.[materialSlot];
  if (entityOverride) return entityOverride;
  const slotDefault = appearance.assignments.defaultsBySlot[materialSlot];
  if (slotDefault) return slotDefault;
  if (appearance.materials.some(material => material.id === materialSlot)) return materialSlot;
  throw new Error(`MATERIAL_SLOT_UNRESOLVED:${entityId}:${materialSlot}`);
}

export function resolveMaterial(
  appearance: AppearancePackage,
  entityId: string,
  materialSlot: string
): MaterialDefinition {
  const materialId = resolveMaterialId(appearance, entityId, materialSlot);
  const material = appearance.materials.find(candidate => candidate.id === materialId);
  if (!material) throw new Error(`MATERIAL_NOT_FOUND:${materialId}`);
  return material;
}

export function setEntityMaterialOverride(
  appearance: AppearancePackage,
  entityId: string,
  materialSlot: string,
  materialId: string
): AppearancePackage {
  if (!appearance.materials.some(material => material.id === materialId)) {
    throw new Error(`MATERIAL_NOT_FOUND:${materialId}`);
  }
  return {
    ...appearance,
    assignments: {
      ...appearance.assignments,
      entityOverrides: {
        ...appearance.assignments.entityOverrides,
        [entityId]: {
          ...appearance.assignments.entityOverrides[entityId],
          [materialSlot]: materialId
        }
      }
    }
  };
}

export function clearEntityMaterialOverride(
  appearance: AppearancePackage,
  entityId: string,
  materialSlot: string
): AppearancePackage {
  const current = appearance.assignments.entityOverrides[entityId];
  if (!current || current[materialSlot] === undefined) return appearance;
  const nextEntity = { ...current };
  delete nextEntity[materialSlot];
  const nextOverrides = { ...appearance.assignments.entityOverrides };
  if (Object.keys(nextEntity).length === 0) delete nextOverrides[entityId];
  else nextOverrides[entityId] = nextEntity;
  return {
    ...appearance,
    assignments: { ...appearance.assignments, entityOverrides: nextOverrides }
  };
}
