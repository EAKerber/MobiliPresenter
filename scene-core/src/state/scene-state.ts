import type {
  EntityKind,
  EnvironmentGeometry,
  ModuleGeometry,
  SceneItem,
  ScenePackage,
  SemanticLayer,
  VisibilityIntent
} from "../contracts/model.js";
import type { RigidTransform } from "../core/math.js";
import { composeTransforms } from "../core/math.js";

export type AnySceneEntity = EnvironmentGeometry | ModuleGeometry | SceneItem;

export type VisibilityReason = "visible" | "intent-off" | "default-hidden" | "host-hidden" | "host-missing";

export interface EffectiveVisibility {
  readonly entityId: string;
  readonly intent: VisibilityIntent;
  readonly effectiveVisible: boolean;
  readonly reason: VisibilityReason;
}

export function semanticLayerForKind(kind: EntityKind): SemanticLayer {
  if (kind === "environment") return 0;
  if (kind === "module") return 2;
  return 1;
}

export function entityIsControllable(entity: AnySceneEntity): boolean {
  if (entity.controllable !== undefined) return entity.controllable;
  return entity.kind !== "environment";
}

export function allSceneEntities(scene: ScenePackage): readonly AnySceneEntity[] {
  return [...scene.environment, ...scene.items, ...scene.modules];
}

export function listControllables(scene: ScenePackage): readonly AnySceneEntity[] {
  return allSceneEntities(scene).filter(entityIsControllable);
}

export function resolveWorldTransforms(scene: ScenePackage): ReadonlyMap<string, RigidTransform> {
  const entities = new Map(allSceneEntities(scene).map(entity => [entity.id, entity] as const));
  const resolved = new Map<string, RigidTransform>();
  const visiting = new Set<string>();

  const resolveOne = (entity: AnySceneEntity): RigidTransform => {
    const cached = resolved.get(entity.id);
    if (cached) return cached;
    if (visiting.has(entity.id)) throw new Error(`TRANSFORM_DEPENDENCY_CYCLE:${entity.id}`);
    visiting.add(entity.id);
    let world = entity.transform;
    if (entity.mountPolicy === "hosted" && entity.hostId) {
      const host = entities.get(entity.hostId);
      if (!host) throw new Error(`HOST_NOT_FOUND:${entity.hostId}`);
      world = composeTransforms(resolveOne(host), entity.transform);
    }
    visiting.delete(entity.id);
    resolved.set(entity.id, world);
    return world;
  };

  for (const entity of entities.values()) resolveOne(entity);
  return resolved;
}

export function resolveItemPlacementTransform(scene: ScenePackage, item: SceneItem): RigidTransform {
  if (item.mountPolicy === "standalone") return item.transform;
  if (!item.hostId) throw new Error(`HOST_REQUIRED:${item.id}`);
  const host = scene.modules.find(module => module.id === item.hostId)
    ?? scene.environment.find(entity => entity.id === item.hostId)
    ?? scene.items.find(entity => entity.id === item.hostId);
  if (!host) throw new Error(`HOST_NOT_FOUND:${item.hostId}`);
  const world = resolveWorldTransforms(scene);
  const hostWorld = world.get(host.id);
  if (!hostWorld) throw new Error(`WORLD_TRANSFORM_NOT_FOUND:${host.id}`);

  if (!item.slotId) return composeTransforms(hostWorld, item.transform);
  if (host.kind !== "module") throw new Error(`SLOT_HOST_MUST_BE_MODULE:${item.hostId}`);
  const slot = host.applianceSlots.find(candidate => candidate.id === item.slotId);
  if (!slot) throw new Error(`SLOT_NOT_FOUND:${item.slotId}`);
  return composeTransforms(composeTransforms(hostWorld, slot.localTransform), item.transform);
}

export function resolveEffectiveVisibility(scene: ScenePackage): ReadonlyMap<string, EffectiveVisibility> {
  const entities = new Map(allSceneEntities(scene).map(entity => [entity.id, entity] as const));
  const resolved = new Map<string, EffectiveVisibility>();
  const visiting = new Set<string>();

  const resolveOne = (entity: AnySceneEntity): EffectiveVisibility => {
    const cached = resolved.get(entity.id);
    if (cached) return cached;
    if (visiting.has(entity.id)) throw new Error(`VISIBILITY_DEPENDENCY_CYCLE:${entity.id}`);
    visiting.add(entity.id);

    let effectiveVisible = entity.visibilityIntent === "on" || (entity.visibilityIntent === "auto" && entity.defaultVisible);
    let reason: VisibilityReason = effectiveVisible ? "visible" : entity.visibilityIntent === "off" ? "intent-off" : "default-hidden";

    if (entity.mountPolicy === "hosted") {
      const host = entity.hostId ? entities.get(entity.hostId) : undefined;
      if (!host) {
        effectiveVisible = false;
        reason = "host-missing";
      } else if (!resolveOne(host).effectiveVisible) {
        effectiveVisible = false;
        reason = "host-hidden";
      }
    }

    visiting.delete(entity.id);
    const result = { entityId: entity.id, intent: entity.visibilityIntent, effectiveVisible, reason } as const;
    resolved.set(entity.id, result);
    return result;
  };

  for (const entity of entities.values()) resolveOne(entity);
  return resolved;
}

export function setVisibilityIntent(scene: ScenePackage, entityId: string, visibilityIntent: VisibilityIntent): ScenePackage {
  let found = false;
  const update = <T extends AnySceneEntity>(entity: T): T => {
    if (entity.id !== entityId) return entity;
    found = true;
    return { ...entity, visibilityIntent };
  };

  const next: ScenePackage = {
    ...scene,
    environment: scene.environment.map(update),
    items: scene.items.map(update),
    modules: scene.modules.map(update)
  };
  if (!found) throw new Error(`ENTITY_NOT_FOUND:${entityId}`);
  return next;
}
