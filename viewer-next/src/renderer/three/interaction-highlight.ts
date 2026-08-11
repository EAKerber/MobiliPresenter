import type { ScenePackage } from "@mobilipresenter/scene-core";
import type { Object3D } from "three";
import { moduleIdForEntity } from "./ownership.js";
import type { ThreeSceneAdapter } from "./scene-adapter.js";

export const INTERACTION_HIGHLIGHT_ID = "module-outline-interaction-v1" as const;

export interface ModuleInteractionTargets {
  readonly selected: readonly Object3D[];
  readonly hovered: readonly Object3D[];
  readonly selectedModuleId: string | null;
  readonly hoveredModuleId: string | null;
}

function visibleModuleOwnershipRoots(
  adapter: ThreeSceneAdapter,
  scenePackage: ScenePackage,
  moduleId: string | null
): readonly Object3D[] {
  if (moduleId === null) return [];
  if (!scenePackage.modules.some(module => module.id === moduleId)) {
    throw new Error(`VIEWER_INTERACTION_MODULE_NOT_FOUND:${moduleId}`);
  }

  const roots: Object3D[] = [];
  for (const [entityId, group] of [...adapter.entityGroups.entries()].sort(([a], [b]) => a.localeCompare(b))) {
    if (!group.visible) continue;
    if (moduleIdForEntity(scenePackage, entityId) === moduleId) roots.push(group);
  }
  return roots;
}

export function resolveModuleInteractionTargets(
  adapter: ThreeSceneAdapter,
  scenePackage: ScenePackage,
  selectedModuleId: string | null,
  hoveredModuleId: string | null
): ModuleInteractionTargets {
  const selectedRoots = visibleModuleOwnershipRoots(adapter, scenePackage, selectedModuleId);
  const hoverSuppressed = hoveredModuleId !== null && hoveredModuleId === selectedModuleId;
  const hoveredRoots = hoverSuppressed
    ? []
    : visibleModuleOwnershipRoots(adapter, scenePackage, hoveredModuleId);

  return {
    selected: selectedRoots,
    hovered: hoveredRoots,
    selectedModuleId: selectedRoots.length > 0 ? selectedModuleId : null,
    hoveredModuleId: hoveredRoots.length > 0 ? hoveredModuleId : null
  };
}
