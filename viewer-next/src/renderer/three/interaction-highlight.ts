import type { ScenePackage } from "@mobilipresenter/scene-core";
import type { Object3D } from "three";
import type { ThreeSceneAdapter } from "./scene-adapter.js";

export const INTERACTION_HIGHLIGHT_ID = "module-outline-interaction-v1" as const;

export interface ModuleInteractionTargets {
  readonly selected: readonly Object3D[];
  readonly hovered: readonly Object3D[];
  readonly selectedModuleId: string | null;
  readonly hoveredModuleId: string | null;
}

function visibleModuleRoot(
  adapter: ThreeSceneAdapter,
  scenePackage: ScenePackage,
  moduleId: string | null
): Object3D | null {
  if (moduleId === null) return null;
  if (!scenePackage.modules.some(module => module.id === moduleId)) {
    throw new Error(`VIEWER_INTERACTION_MODULE_NOT_FOUND:${moduleId}`);
  }
  const group = adapter.entityGroups.get(moduleId);
  if (!group) throw new Error(`VIEWER_INTERACTION_GROUP_NOT_FOUND:${moduleId}`);
  return group.visible ? group : null;
}

export function resolveModuleInteractionTargets(
  adapter: ThreeSceneAdapter,
  scenePackage: ScenePackage,
  selectedModuleId: string | null,
  hoveredModuleId: string | null
): ModuleInteractionTargets {
  const selectedRoot = visibleModuleRoot(adapter, scenePackage, selectedModuleId);
  const hoverSuppressed = hoveredModuleId !== null && hoveredModuleId === selectedModuleId;
  const hoveredRoot = hoverSuppressed
    ? null
    : visibleModuleRoot(adapter, scenePackage, hoveredModuleId);

  return {
    selected: selectedRoot ? [selectedRoot] : [],
    hovered: hoveredRoot ? [hoveredRoot] : [],
    selectedModuleId: selectedRoot ? selectedModuleId : null,
    hoveredModuleId: hoveredRoot ? hoveredModuleId : null
  };
}
