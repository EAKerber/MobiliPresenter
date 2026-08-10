import type { ScenePackage } from "@mobilipresenter/scene-core";
import {
  Box3,
  Box3Helper,
  Color,
  Group,
  PerspectiveCamera,
  Raycaster,
  Vector2
} from "three";
import { moduleIdForEntity, selectableModuleIdForObject } from "./ownership.js";
import type { ThreeSceneAdapter } from "./scene-adapter.js";

const SELECTION_GOLD = new Color(0xc5a35a);

export function pickModuleAtNdc(
  adapter: ThreeSceneAdapter,
  scenePackage: ScenePackage,
  camera: PerspectiveCamera,
  ndc: readonly [number, number]
): string | null {
  const raycaster = new Raycaster();
  raycaster.setFromCamera(new Vector2(ndc[0], ndc[1]), camera);

  const visibleRoots = [...adapter.entityGroups.entries()]
    .filter(([, group]) => group.visible)
    .map(([, group]) => group);
  const hits = raycaster.intersectObjects(visibleRoots, true);
  for (const hit of hits) {
    const moduleId = selectableModuleIdForObject(adapter, scenePackage, hit.object);
    if (moduleId) return moduleId;
  }
  return null;
}

export interface ModuleSelectionOverlay {
  readonly root: Group;
  getSelectedModuleId(): string | null;
  setSelectedModule(moduleId: string | null): void;
  dispose(): void;
}

export function createModuleSelectionOverlay(
  adapter: ThreeSceneAdapter,
  scenePackage: ScenePackage
): ModuleSelectionOverlay {
  const root = new Group();
  root.name = "__selection";
  root.renderOrder = 20_000;
  let selectedModuleId: string | null = null;
  let helper: Box3Helper | null = null;

  const clear = (): void => {
    if (!helper) return;
    root.remove(helper);
    helper.geometry.dispose();
    helper.material.dispose();
    helper = null;
  };

  return {
    root,
    getSelectedModuleId(): string | null {
      return selectedModuleId;
    },
    setSelectedModule(moduleId: string | null): void {
      clear();
      selectedModuleId = moduleId;
      if (!moduleId) return;
      const module = scenePackage.modules.find(candidate => candidate.id === moduleId);
      if (!module) throw new Error(`VIEWER_SELECTION_MODULE_NOT_FOUND:${moduleId}`);
      const group = adapter.entityGroups.get(moduleId);
      if (!group) throw new Error(`VIEWER_SELECTION_GROUP_NOT_FOUND:${moduleId}`);
      if (!group.visible) return;

      group.updateWorldMatrix(true, true);
      const bounds = new Box3().setFromObject(group);
      if (bounds.isEmpty()) return;
      helper = new Box3Helper(bounds, SELECTION_GOLD);
      helper.name = `selection:${moduleId}`;
      helper.material.transparent = true;
      helper.material.opacity = 0.34;
      helper.material.depthTest = true;
      helper.material.depthWrite = false;
      helper.userData.moduleId = moduleId;
      helper.userData.interactionOnly = true;
      root.add(helper);
    },
    dispose(): void {
      clear();
      root.clear();
      selectedModuleId = null;
    }
  };
}

export function selectableModuleIds(scenePackage: ScenePackage): readonly string[] {
  const ids = new Set<string>();
  for (const module of scenePackage.modules) ids.add(module.id);
  for (const item of scenePackage.items) {
    const moduleId = moduleIdForEntity(scenePackage, item.id);
    if (moduleId) ids.add(moduleId);
  }
  return [...ids].sort();
}
