import {
  currentFaucetAnchor,
  currentUnderCabLightContract,
  type AppearancePackage,
  type ScenePackage
} from "@mobilipresenter/scene-core";
import {
  BufferGeometry,
  Color,
  Material,
  Mesh,
  PerspectiveCamera,
  Scene,
  WebGLRenderer
} from "three";
import { attachParametricAppliances } from "../renderer/three/appliances.js";
import { applyFh06CooktopContact } from "../renderer/three/cooktop-contact.js";
import { applyFh06FaucetRefinement } from "../renderer/three/faucet-refinement.js";
import { applyFh06FrontReadability } from "../renderer/three/front-readability.js";
import { attachCurrentHardware } from "../renderer/three/hardware.js";
import {
  INTERACTION_HIGHLIGHT_ID,
  resolveModuleInteractionTargets
} from "../renderer/three/interaction-highlight.js";
import { buildThreeLighting, installNeutralRoomEnvironment } from "../renderer/three/lighting.js";
import {
  WOOD_GRAIN_SHADER_VERSION,
  ThreeMaterialRegistry,
  bindModuleContinuousMaterialMappings
} from "../renderer/three/materials.js";
import { applyFh06OvenReadability } from "../renderer/three/oven-readability.js";
import { auditRenderOwnership, type RenderOwnershipAudit } from "../renderer/three/ownership.js";
import { createSelectiveBloomPipeline } from "../renderer/three/post.js";
import { buildThreeScene, type ThreeSceneAdapter } from "../renderer/three/scene-adapter.js";
import { applyFh06SinkRefinement } from "../renderer/three/sink-refinement.js";
import { applyFh06UnderCabProfile } from "../renderer/three/under-cab-profile.js";
import { applyFh06VisualRefinements } from "../renderer/three/visual-refinements.js";
import { applyFh06FullWallTiles } from "../renderer/three/wall-tiles.js";
import { syncRuntimeLighting, syncRuntimeMaterials, syncRuntimeVisibility } from "./sync.js";

export interface ViewerCompositionDiagnostics {
  readonly cooktopContactId: string;
  readonly cooktopGapMm: number;
  readonly frontReadabilityId: string;
  readonly frontPhysicalGapMm: readonly number[];
  readonly hardwareRefinementId: string;
  readonly hardwareHandleCount: number;
  readonly hardwareAnchorCount: number;
  readonly interactionHighlightId: string;
  readonly materialMappingId: string;
  readonly woodGrainShaderVersion: string;
  readonly initialWoodMappedMeshCount: number;
  readonly ovenReadabilityId: string;
  readonly ovenPhysicalClearanceMm: readonly number[];
  readonly sinkFamilyId: string;
  readonly sinkStoneHole: string;
  readonly sinkContinuousBowl: boolean;
  readonly faucetPresetId: string;
  readonly faucetHostEntityId: string;
  readonly underCabProfileId: string;
  readonly underCabHostModuleId: string;
  readonly underCabKelvin: number;
  readonly underCabAreaLight: boolean;
  readonly wallTileSurfaceCount: number;
}

export interface ViewerComposition {
  readonly scenePackage: ScenePackage;
  readonly appearance: AppearancePackage;
  readonly adapter: ThreeSceneAdapter;
  readonly ownership: RenderOwnershipAudit;
  readonly diagnostics: ViewerCompositionDiagnostics;
  syncVisibility(scenePackage: ScenePackage, appearance: AppearancePackage): void;
  syncMaterials(scenePackage: ScenePackage, appearance: AppearancePackage): void;
  syncLighting(scenePackage: ScenePackage, appearance: AppearancePackage): void;
  syncConfiguration(scenePackage: ScenePackage, appearance: AppearancePackage): void;
  syncInteraction(selectedModuleId: string | null, hoveredModuleId: string | null): void;
  render(): void;
  setSize(widthPx: number, heightPx: number): void;
  dispose(): void;
}

export interface ViewerCompositionOptions {
  readonly widthPx: number;
  readonly heightPx: number;
  readonly background?: Color;
}

function disposeSceneResources(scene: Scene): void {
  const geometries = new Set<BufferGeometry>();
  const materials = new Set<Material>();
  scene.traverse(object => {
    if (!(object instanceof Mesh)) return;
    geometries.add(object.geometry);
    if (Array.isArray(object.material)) {
      for (const material of object.material) materials.add(material);
    } else {
      materials.add(object.material);
    }
  });
  for (const geometry of geometries) geometry.dispose();
  for (const material of materials) material.dispose();
}

export function createViewerComposition(
  renderer: WebGLRenderer,
  camera: PerspectiveCamera,
  initialScenePackage: ScenePackage,
  initialAppearance: AppearancePackage,
  options: ViewerCompositionOptions
): ViewerComposition {
  const materials = new ThreeMaterialRegistry(initialAppearance);
  const adapter = buildThreeScene(initialScenePackage, (entityId, slot) => materials.resolve(entityId, slot));
  attachParametricAppliances(adapter, initialScenePackage, initialAppearance, materials);

  const cooktopContact = applyFh06CooktopContact(adapter, initialScenePackage);
  applyFh06VisualRefinements(adapter, materials);
  const frontReadability = applyFh06FrontReadability(adapter, materials, initialScenePackage);
  const hardwareRefinement = attachCurrentHardware(adapter, initialScenePackage, materials);
  const ovenReadability = applyFh06OvenReadability(adapter, materials, initialScenePackage, initialAppearance);
  const tileRefinement = applyFh06FullWallTiles(adapter, initialScenePackage);
  const sinkRefinement = applyFh06SinkRefinement(adapter, materials, initialScenePackage);
  const faucetRefinement = applyFh06FaucetRefinement(adapter, materials, currentFaucetAnchor);
  const underCabRefinement = applyFh06UnderCabProfile(
    adapter,
    materials,
    initialScenePackage,
    currentUnderCabLightContract
  );
  const initialMaterialMapping = bindModuleContinuousMaterialMappings(adapter);

  adapter.scene.background = options.background ?? new Color(0xf0ede7);
  const lighting = buildThreeLighting(initialScenePackage, initialAppearance);
  adapter.scene.add(lighting.root);
  const ownership = auditRenderOwnership(adapter, [lighting.root.name, tileRefinement.groupName]);
  if (!ownership.pass) throw new Error(`VIEWER_RENDER_OWNERSHIP_FAILED:${ownership.unownedTopLevelNames.join(",")}`);

  const environment = installNeutralRoomEnvironment(
    renderer,
    adapter.scene,
    initialAppearance.lighting.environment.relativeIntensity
  );
  const post = createSelectiveBloomPipeline(
    renderer,
    adapter.scene,
    camera,
    initialAppearance,
    options.widthPx,
    options.heightPx
  );

  let currentScenePackage = initialScenePackage;
  let currentAppearance = initialAppearance;
  let currentSelectedModuleId: string | null = null;
  let currentHoveredModuleId: string | null = null;
  let disposed = false;
  const assertActive = (): void => {
    if (disposed) throw new Error("VIEWER_COMPOSITION_DISPOSED");
  };
  const applyInteractionTargets = (): void => {
    const targets = resolveModuleInteractionTargets(
      adapter,
      currentScenePackage,
      currentSelectedModuleId,
      currentHoveredModuleId
    );
    post.setInteractionTargets(targets.selected, targets.hovered);
  };
  const refreshMaterialMappings = (): void => {
    bindModuleContinuousMaterialMappings(adapter);
  };

  const result: ViewerComposition = {
    get scenePackage(): ScenePackage {
      return currentScenePackage;
    },
    get appearance(): AppearancePackage {
      return currentAppearance;
    },
    adapter,
    ownership,
    diagnostics: {
      cooktopContactId: cooktopContact.refinementId,
      cooktopGapMm: cooktopContact.afterGapMm,
      frontReadabilityId: frontReadability.refinementId,
      frontPhysicalGapMm: frontReadability.physicalGapMm,
      hardwareRefinementId: hardwareRefinement.refinementId,
      hardwareHandleCount: hardwareRefinement.handleCount,
      hardwareAnchorCount: hardwareRefinement.handleCount,
      interactionHighlightId: INTERACTION_HIGHLIGHT_ID,
      materialMappingId: initialMaterialMapping.bindingId,
      woodGrainShaderVersion: WOOD_GRAIN_SHADER_VERSION,
      initialWoodMappedMeshCount: initialMaterialMapping.boundMeshCount,
      ovenReadabilityId: ovenReadability.refinementId,
      ovenPhysicalClearanceMm: ovenReadability.physicalClearanceMm,
      sinkFamilyId: sinkRefinement.sinkFamilyId,
      sinkStoneHole: sinkRefinement.stoneHoleGeometry,
      sinkContinuousBowl: sinkRefinement.continuousBowl,
      faucetPresetId: faucetRefinement.presetId,
      faucetHostEntityId: faucetRefinement.hostEntityId,
      underCabProfileId: underCabRefinement.profileDefinitionId,
      underCabHostModuleId: underCabRefinement.hostModuleId,
      underCabKelvin: underCabRefinement.colorTemperatureK,
      underCabAreaLight: underCabRefinement.hasActualAreaLight,
      wallTileSurfaceCount: tileRefinement.surfaceCount
    },
    syncVisibility(scenePackage, appearance): void {
      assertActive();
      syncRuntimeVisibility(adapter, lighting, scenePackage, appearance);
      currentScenePackage = scenePackage;
      currentAppearance = appearance;
      applyInteractionTargets();
    },
    syncMaterials(scenePackage, appearance): void {
      assertActive();
      syncRuntimeMaterials(adapter, materials, appearance);
      refreshMaterialMappings();
      currentScenePackage = scenePackage;
      currentAppearance = appearance;
    },
    syncLighting(scenePackage, appearance): void {
      assertActive();
      syncRuntimeLighting(adapter.scene, lighting, post, scenePackage, appearance);
      currentScenePackage = scenePackage;
      currentAppearance = appearance;
    },
    syncConfiguration(scenePackage, appearance): void {
      assertActive();
      syncRuntimeVisibility(adapter, lighting, scenePackage, appearance);
      syncRuntimeMaterials(adapter, materials, appearance);
      refreshMaterialMappings();
      syncRuntimeLighting(adapter.scene, lighting, post, scenePackage, appearance);
      currentScenePackage = scenePackage;
      currentAppearance = appearance;
      applyInteractionTargets();
    },
    syncInteraction(selectedModuleId, hoveredModuleId): void {
      assertActive();
      currentSelectedModuleId = selectedModuleId;
      currentHoveredModuleId = hoveredModuleId;
      applyInteractionTargets();
    },
    render(): void {
      assertActive();
      post.render();
    },
    setSize(widthPx: number, heightPx: number): void {
      assertActive();
      post.setSize(widthPx, heightPx);
    },
    dispose(): void {
      if (disposed) return;
      disposed = true;
      post.dispose();
      environment.dispose();
      disposeSceneResources(adapter.scene);
      materials.dispose();
      adapter.scene.clear();
    }
  };
  return result;
}
