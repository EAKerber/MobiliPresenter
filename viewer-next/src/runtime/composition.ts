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
import { buildThreeLighting, installNeutralRoomEnvironment } from "../renderer/three/lighting.js";
import { ThreeMaterialRegistry } from "../renderer/three/materials.js";
import { applyFh06OvenReadability } from "../renderer/three/oven-readability.js";
import { auditRenderOwnership, type RenderOwnershipAudit } from "../renderer/three/ownership.js";
import { createSelectiveBloomPipeline } from "../renderer/three/post.js";
import { buildThreeScene, type ThreeSceneAdapter } from "../renderer/three/scene-adapter.js";
import { applyFh06SinkRefinement } from "../renderer/three/sink-refinement.js";
import { applyFh06UnderCabProfile } from "../renderer/three/under-cab-profile.js";
import { applyFh06VisualRefinements } from "../renderer/three/visual-refinements.js";
import { applyFh06FullWallTiles } from "../renderer/three/wall-tiles.js";

export interface ViewerCompositionDiagnostics {
  readonly cooktopGapMm: number;
  readonly frontPhysicalGapMm: readonly number[];
  readonly ovenPhysicalClearanceMm: readonly number[];
  readonly sinkFamilyId: string;
  readonly sinkStoneHole: string;
  readonly faucetPresetId: string;
  readonly faucetHostEntityId: string;
  readonly underCabHostModuleId: string;
  readonly underCabKelvin: number;
  readonly wallTileSurfaceCount: number;
}

export interface ViewerComposition {
  readonly scenePackage: ScenePackage;
  readonly appearance: AppearancePackage;
  readonly adapter: ThreeSceneAdapter;
  readonly ownership: RenderOwnershipAudit;
  readonly diagnostics: ViewerCompositionDiagnostics;
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
  scenePackage: ScenePackage,
  appearance: AppearancePackage,
  options: ViewerCompositionOptions
): ViewerComposition {
  const materials = new ThreeMaterialRegistry(appearance);
  const adapter = buildThreeScene(scenePackage, (entityId, slot) => materials.resolve(entityId, slot));
  attachParametricAppliances(adapter, scenePackage, appearance, materials);

  const cooktopContact = applyFh06CooktopContact(adapter, scenePackage);
  applyFh06VisualRefinements(adapter, materials);
  const frontReadability = applyFh06FrontReadability(adapter, materials, scenePackage);
  const ovenReadability = applyFh06OvenReadability(adapter, materials, scenePackage, appearance);
  const tileRefinement = applyFh06FullWallTiles(adapter, scenePackage);
  const sinkRefinement = applyFh06SinkRefinement(adapter, materials, scenePackage);
  const faucetRefinement = applyFh06FaucetRefinement(adapter, materials, currentFaucetAnchor);
  const underCabRefinement = applyFh06UnderCabProfile(
    adapter,
    materials,
    scenePackage,
    currentUnderCabLightContract
  );

  adapter.scene.background = options.background ?? new Color(0xf0ede7);
  const lighting = buildThreeLighting(scenePackage, appearance);
  adapter.scene.add(lighting.root);
  const ownership = auditRenderOwnership(adapter, [lighting.root.name]);
  if (!ownership.pass) throw new Error(`VIEWER_RENDER_OWNERSHIP_FAILED:${ownership.unownedTopLevelNames.join(",")}`);

  const environment = installNeutralRoomEnvironment(
    renderer,
    adapter.scene,
    appearance.lighting.environment.relativeIntensity
  );
  const post = createSelectiveBloomPipeline(
    renderer,
    adapter.scene,
    camera,
    appearance,
    options.widthPx,
    options.heightPx
  );

  let disposed = false;
  return {
    scenePackage,
    appearance,
    adapter,
    ownership,
    diagnostics: {
      cooktopGapMm: cooktopContact.afterGapMm,
      frontPhysicalGapMm: frontReadability.physicalGapMm,
      ovenPhysicalClearanceMm: ovenReadability.physicalClearanceMm,
      sinkFamilyId: sinkRefinement.sinkFamilyId,
      sinkStoneHole: sinkRefinement.stoneHoleGeometry,
      faucetPresetId: faucetRefinement.presetId,
      faucetHostEntityId: faucetRefinement.hostEntityId,
      underCabHostModuleId: underCabRefinement.hostModuleId,
      underCabKelvin: underCabRefinement.colorTemperatureK,
      wallTileSurfaceCount: tileRefinement.surfaceCount
    },
    render(): void {
      if (disposed) throw new Error("VIEWER_COMPOSITION_DISPOSED");
      post.render();
    },
    setSize(widthPx: number, heightPx: number): void {
      if (disposed) throw new Error("VIEWER_COMPOSITION_DISPOSED");
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
}
