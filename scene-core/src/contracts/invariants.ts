import { aabbSize } from "../core/math.js";
import type {
  DimensionTripleMm,
  GeometryPrimitive,
  ModuleGeometry,
  SceneEntityBase,
  SceneItem,
  ScenePackage,
  SourceBinding
} from "./model.js";
import { MOBILIPRESENTER_COORDINATE_SYSTEM, SCENE_PACKAGE_SCHEMA_VERSION } from "./model.js";

export interface ValidationIssue {
  readonly code: string;
  readonly path: string;
  readonly detail: string;
}

function positiveDimensions(value: DimensionTripleMm): boolean {
  return value.width > 0 && value.height > 0 && value.depth > 0;
}

function validateEntityBase(entity: SceneEntityBase, path: string): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  if (!entity.id.trim()) issues.push({ code: "ENTITY_ID_EMPTY", path: `${path}.id`, detail: "id must be non-empty" });
  if (entity.mountPolicy === "hosted" && !entity.hostId) issues.push({ code: "HOST_REQUIRED", path: `${path}.hostId`, detail: "hosted entity requires hostId" });
  if (entity.mountPolicy === "standalone" && entity.hostId) issues.push({ code: "HOST_FORBIDDEN", path: `${path}.hostId`, detail: "standalone entity cannot declare hostId" });
  if (entity.hostId === entity.id) issues.push({ code: "SELF_HOST_FORBIDDEN", path: `${path}.hostId`, detail: "entity cannot host itself" });
  return issues;
}

function validateGeometry(geometry: readonly GeometryPrimitive[], path: string): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  const ids = new Set<string>();
  for (let i = 0; i < geometry.length; i++) {
    const primitive = geometry[i]!;
    const primitivePath = `${path}[${i}]`;
    if (ids.has(primitive.id)) issues.push({ code: "GEOMETRY_ID_DUPLICATE", path: `${primitivePath}.id`, detail: primitive.id });
    ids.add(primitive.id);
    if (primitive.primitive === "box") {
      if (!positiveDimensions(primitive.sizeMm)) issues.push({ code: "BOX_DIMENSIONS_INVALID", path: `${primitivePath}.sizeMm`, detail: "box dimensions must be positive" });
    } else if (!(primitive.sizeMm[0] > 0 && primitive.sizeMm[1] > 0)) {
      issues.push({ code: "FACE_DIMENSIONS_INVALID", path: `${primitivePath}.sizeMm`, detail: "face dimensions must be positive" });
    }
  }
  return issues;
}

function validateModule(module: ModuleGeometry, path: string): ValidationIssue[] {
  const issues = validateEntityBase(module, path);
  if (!positiveDimensions(module.dimensions.geometryMm)) issues.push({ code: "GEOMETRY_DIMENSIONS_INVALID", path: `${path}.dimensions.geometryMm`, detail: "geometry dimensions must be positive" });
  if (module.dimensions.nominalMm && !positiveDimensions(module.dimensions.nominalMm)) issues.push({ code: "NOMINAL_DIMENSIONS_INVALID", path: `${path}.dimensions.nominalMm`, detail: "nominal dimensions must be positive" });
  const structuralSize = aabbSize(module.structuralEnvelope);
  if (structuralSize.x <= 0 || structuralSize.y <= 0 || structuralSize.z <= 0) issues.push({ code: "STRUCTURAL_ENVELOPE_INVALID", path: `${path}.structuralEnvelope`, detail: "structural envelope must have positive volume" });
  issues.push(...validateGeometry(module.geometry, `${path}.geometry`));
  const slotIds = new Set<string>();
  for (let i = 0; i < module.applianceSlots.length; i++) {
    const slot = module.applianceSlots[i]!;
    if (slotIds.has(slot.id)) issues.push({ code: "APPLIANCE_SLOT_ID_DUPLICATE", path: `${path}.applianceSlots[${i}].id`, detail: slot.id });
    slotIds.add(slot.id);
    if (!positiveDimensions(slot.clearSizeMm)) issues.push({ code: "APPLIANCE_SLOT_DIMENSIONS_INVALID", path: `${path}.applianceSlots[${i}].clearSizeMm`, detail: slot.id });
  }
  return issues;
}

function validateItem(item: SceneItem, path: string): ValidationIssue[] {
  const issues = validateEntityBase(item, path);
  if (!item.definitionId.trim()) issues.push({ code: "ITEM_DEFINITION_ID_EMPTY", path: `${path}.definitionId`, detail: "definitionId must be non-empty" });
  if (item.targetEnvelopeMm && !positiveDimensions(item.targetEnvelopeMm)) issues.push({ code: "TARGET_ENVELOPE_INVALID", path: `${path}.targetEnvelopeMm`, detail: "target envelope must be positive" });
  if (item.geometry) issues.push(...validateGeometry(item.geometry, `${path}.geometry`));
  if (item.placementStatus && (!item.evidenceRefs || item.evidenceRefs.length === 0)) {
    issues.push({ code: "PLACEMENT_EVIDENCE_REQUIRED", path: `${path}.evidenceRefs`, detail: "placementStatus requires evidenceRefs" });
  }
  return issues;
}

function validateBindings(bindings: readonly SourceBinding[]): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  const ids = new Set<string>();
  for (let i = 0; i < bindings.length; i++) {
    const binding = bindings[i]!;
    if (ids.has(binding.id)) issues.push({ code: "SOURCE_BINDING_ID_DUPLICATE", path: `sourceBindings[${i}].id`, detail: binding.id });
    ids.add(binding.id);
    if (!binding.sourceFingerprint.startsWith("sha256:")) issues.push({ code: "SOURCE_FINGERPRINT_INVALID", path: `sourceBindings[${i}].sourceFingerprint`, detail: "expected sha256:<digest>" });
    if (!binding.sourceSelector.layer && !binding.sourceSelector.entityType) issues.push({ code: "SOURCE_SELECTOR_EMPTY", path: `sourceBindings[${i}].sourceSelector`, detail: "at least one selector field is required" });
  }
  return issues;
}

function validateHostGraph(scene: ScenePackage): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  const entities = [...scene.environment, ...scene.items, ...scene.modules];
  const byId = new Map(entities.map(entity => [entity.id, entity] as const));
  const modules = new Map(scene.modules.map(module => [module.id, module] as const));

  for (let i = 0; i < scene.items.length; i++) {
    const item = scene.items[i]!;
    if (item.hostId && !byId.has(item.hostId)) {
      issues.push({ code: "HOST_NOT_FOUND", path: `items[${i}].hostId`, detail: item.hostId });
    }
    if (item.slotId) {
      if (!item.hostId) {
        issues.push({ code: "SLOT_REQUIRES_HOST", path: `items[${i}].slotId`, detail: item.slotId });
      } else {
        const hostModule = modules.get(item.hostId);
        if (!hostModule) {
          issues.push({ code: "SLOT_HOST_MUST_BE_MODULE", path: `items[${i}].hostId`, detail: item.hostId });
        } else if (!hostModule.applianceSlots.some(slot => slot.id === item.slotId)) {
          issues.push({ code: "SLOT_NOT_FOUND", path: `items[${i}].slotId`, detail: item.slotId });
        }
      }
    }
  }
  for (const entity of [...scene.environment, ...scene.modules]) {
    if (entity.hostId && !byId.has(entity.hostId)) issues.push({ code: "HOST_NOT_FOUND", path: `${entity.id}.hostId`, detail: entity.hostId });
  }

  const state = new Map<string, "visiting" | "done">();
  const visit = (id: string): void => {
    if (state.get(id) === "done") return;
    if (state.get(id) === "visiting") {
      issues.push({ code: "HOST_CYCLE", path: id, detail: "host dependency graph must be acyclic" });
      return;
    }
    state.set(id, "visiting");
    const hostId = byId.get(id)?.hostId;
    if (hostId && byId.has(hostId)) visit(hostId);
    state.set(id, "done");
  };
  for (const id of byId.keys()) visit(id);
  return issues;
}

function validateSubstitutionGroups(scene: ScenePackage): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  const groups = scene.substitutionGroups ?? [];
  const entities = new Set([...scene.environment, ...scene.items, ...scene.modules].map(entity => entity.id));
  const ids = new Set<string>();
  const replacements = new Set<string>();
  for (let i = 0; i < groups.length; i++) {
    const group = groups[i]!;
    const path = `substitutionGroups[${i}]`;
    if (ids.has(group.id)) issues.push({ code: "SUBSTITUTION_GROUP_ID_DUPLICATE", path: `${path}.id`, detail: group.id });
    ids.add(group.id);
    if (group.primaryEntityId === group.replacementEntityId) issues.push({ code: "SUBSTITUTION_SELF_REFERENCE", path, detail: group.primaryEntityId });
    if (!entities.has(group.primaryEntityId)) issues.push({ code: "SUBSTITUTION_PRIMARY_NOT_FOUND", path: `${path}.primaryEntityId`, detail: group.primaryEntityId });
    if (!entities.has(group.replacementEntityId)) issues.push({ code: "SUBSTITUTION_REPLACEMENT_NOT_FOUND", path: `${path}.replacementEntityId`, detail: group.replacementEntityId });
    if (replacements.has(group.replacementEntityId)) issues.push({ code: "SUBSTITUTION_REPLACEMENT_DUPLICATE", path: `${path}.replacementEntityId`, detail: group.replacementEntityId });
    replacements.add(group.replacementEntityId);
  }
  return issues;
}

export function validateScenePackage(scene: ScenePackage): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  if (scene.schemaVersion !== SCENE_PACKAGE_SCHEMA_VERSION) issues.push({ code: "SCENE_SCHEMA_UNSUPPORTED", path: "schemaVersion", detail: scene.schemaVersion });
  if (JSON.stringify(scene.coordinateSystem) !== JSON.stringify(MOBILIPRESENTER_COORDINATE_SYSTEM)) issues.push({ code: "COORDINATE_SYSTEM_UNSUPPORTED", path: "coordinateSystem", detail: "expected canonical x-right/y-depth/z-up millimeter system" });
  if (scene.camera.mode !== "fixed") issues.push({ code: "CAMERA_MODE_INVALID", path: "camera.mode", detail: "camera must be fixed" });
  if (scene.camera.projection !== "perspective") issues.push({ code: "CAMERA_PROJECTION_INVALID", path: "camera.projection", detail: "Scene Core requires fixed perspective camera" });
  if (!(scene.camera.fovYDeg > 0 && scene.camera.fovYDeg < 180)) issues.push({ code: "CAMERA_FOV_INVALID", path: "camera.fovYDeg", detail: "FOV must be between 0 and 180 degrees" });
  if (!(scene.camera.nearMm > 0 && scene.camera.farMm > scene.camera.nearMm)) issues.push({ code: "CAMERA_CLIP_INVALID", path: "camera", detail: "near/far clip range invalid" });

  const entityIds = new Set<string>();
  const groups = [
    ["environment", scene.environment],
    ["items", scene.items],
    ["modules", scene.modules]
  ] as const;
  for (const [groupName, group] of groups) {
    for (let index = 0; index < group.length; index++) {
      const entity = group[index]!;
      const path = `${groupName}[${index}]`;
      if (entityIds.has(entity.id)) issues.push({ code: "ENTITY_ID_DUPLICATE", path: `${path}.id`, detail: entity.id });
      entityIds.add(entity.id);
      if (entity.kind === "module") issues.push(...validateModule(entity, path));
      else if (entity.kind === "environment") {
        issues.push(...validateEntityBase(entity, path));
        const size = aabbSize(entity.structuralEnvelope);
        if (size.x <= 0 || size.y <= 0 || size.z <= 0) issues.push({ code: "STRUCTURAL_ENVELOPE_INVALID", path: `${path}.structuralEnvelope`, detail: "environment envelope must have positive volume" });
        issues.push(...validateGeometry(entity.geometry, `${path}.geometry`));
      } else issues.push(...validateItem(entity, path));
    }
  }

  issues.push(...validateHostGraph(scene));
  issues.push(...validateSubstitutionGroups(scene));
  issues.push(...validateBindings(scene.sourceBindings));
  return issues;
}
