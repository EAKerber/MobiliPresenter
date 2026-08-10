import type { ScenePackage } from "@mobilipresenter/scene-core";
import type { Object3D } from "three";
import type { ThreeSceneAdapter } from "./scene-adapter.js";

export interface RenderOwnershipAudit {
  readonly entityGroupCount: number;
  readonly globalTopLevelNames: readonly string[];
  readonly unownedTopLevelNames: readonly string[];
  readonly pass: boolean;
}

export function auditRenderOwnership(
  adapter: ThreeSceneAdapter,
  allowedGlobalTopLevelNames: readonly string[] = []
): RenderOwnershipAudit {
  const entityGroups = new Set(adapter.entityGroups.values());
  const allowedGlobals = new Set(allowedGlobalTopLevelNames);
  const globalTopLevelNames: string[] = [];
  const unownedTopLevelNames: string[] = [];

  for (const child of adapter.scene.children) {
    if (entityGroups.has(child as never)) continue;
    if (allowedGlobals.has(child.name)) globalTopLevelNames.push(child.name);
    else unownedTopLevelNames.push(child.name || "<unnamed>");
  }

  globalTopLevelNames.sort();
  unownedTopLevelNames.sort();
  return {
    entityGroupCount: entityGroups.size,
    globalTopLevelNames,
    unownedTopLevelNames,
    pass: unownedTopLevelNames.length === 0
  };
}

export function owningEntityIdForObject(adapter: ThreeSceneAdapter, object: Object3D): string | null {
  const byObject = new Map<Object3D, string>();
  for (const [entityId, group] of adapter.entityGroups) byObject.set(group, entityId);

  let cursor: Object3D | null = object;
  while (cursor) {
    const entityId = byObject.get(cursor);
    if (entityId) return entityId;
    cursor = cursor.parent;
  }
  return null;
}

export function moduleIdForEntity(scene: ScenePackage, entityId: string): string | null {
  const module = scene.modules.find(candidate => candidate.id === entityId);
  if (module) return module.id;

  const visited = new Set<string>();
  let currentId: string | undefined = entityId;
  while (currentId) {
    if (visited.has(currentId)) throw new Error(`VIEWER_OWNERSHIP_CYCLE:${currentId}`);
    visited.add(currentId);

    const currentModule = scene.modules.find(candidate => candidate.id === currentId);
    if (currentModule) return currentModule.id;
    const item = scene.items.find(candidate => candidate.id === currentId);
    if (!item || item.mountPolicy !== "hosted" || !item.hostId) return null;
    currentId = item.hostId;
  }
  return null;
}

export function selectableModuleIdForObject(
  adapter: ThreeSceneAdapter,
  scene: ScenePackage,
  object: Object3D
): string | null {
  const entityId = owningEntityIdForObject(adapter, object);
  return entityId ? moduleIdForEntity(scene, entityId) : null;
}
