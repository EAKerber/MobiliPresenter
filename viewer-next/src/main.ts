import {
  createCurrentFidelityOverlayLines,
  CURRENT_FIDELITY_SUPERSAMPLE,
  CURRENT_FIDELITY_VIEWPORT,
  currentFixedCamera,
  currentSceneBase,
  resolveMaterialId
} from "@mobilipresenter/scene-core";
import {
  ACESFilmicToneMapping,
  SRGBColorSpace,
  WebGLRenderer
} from "three";
import { styleAnchorAppearance } from "./fixtures/style-anchor.js";
import {
  createThreeCamera,
  updateThreeCameraCrop,
  updateThreeCameraViewport,
  type PixelCrop
} from "./renderer/three/camera.js";
import { buildFidelityOverlay } from "./renderer/three/fidelity-overlay.js";
import { FH06_GTAO_PROFILE } from "./renderer/three/post.js";
import {
  createModuleSelectionOverlay,
  pickModuleAtNdc,
  type ModuleSelectionOverlay
} from "./renderer/three/selection.js";
import { createViewerComposition, type ViewerComposition } from "./runtime/composition.js";
import {
  moduleIdFromAlias,
  parseViewerConfiguration,
  parseViewerInteraction
} from "./runtime/query.js";
import {
  configurationFingerprint,
  deriveViewerAppearance,
  deriveViewerScene,
  reduceViewerConfiguration,
  reduceViewerInteraction,
  type ViewerConfigurationAction,
  type ViewerConfigurationState,
  type ViewerInteractionState,
  type ViewerVisibilityOverride
} from "./runtime/viewer-state.js";
import type { FrontPresetId, LightingPresetId } from "./runtime/presets.js";
import type { StonePresetId } from "./fixtures/stone-presets.js";

const appElement = document.querySelector<HTMLElement>("#app");
if (appElement === null) throw new Error("APP_ROOT_NOT_FOUND");
const app: HTMLElement = appElement;

const MODULE02_ID = moduleIdFromAlias("02");
const MODULE03_ID = moduleIdFromAlias("03");
const MODULE06_ID = moduleIdFromAlias("06");
const OVEN_ID = "scene/traditional/appliance/oven";
const COOKTOP_ID = "scene/traditional/appliance/cooktop";
const RANGE_ID = "scene/traditional/appliance/freestanding-range";
const MICRO_ID = "scene/traditional/appliance/microwave";
const UNDERCAB_ID = "scene/traditional/accessory/under-cab-led-06";
const STONE03_ID = "scene/traditional/accessory/stone-03";

const query = new URLSearchParams(window.location.search);
const fidelityMode = query.get("fidelity") === "1";
const fidelityOverlayMode = fidelityMode && query.get("overlay") === "1";

function parseCrop(raw: string | null): PixelCrop | null {
  if (!raw) return null;
  const values = raw.split(",").map(value => Number.parseInt(value, 10));
  if (values.length !== 4 || values.some(value => !Number.isFinite(value))) throw new Error("FIDELITY_CROP_INVALID");
  const [xPx, yPx, widthPx, heightPx] = values as [number, number, number, number];
  if (widthPx <= 0 || heightPx <= 0 || xPx < 0 || yPx < 0) throw new Error("FIDELITY_CROP_INVALID");
  return { xPx, yPx, widthPx, heightPx };
}

let configuration: ViewerConfigurationState = parseViewerConfiguration(query);
let interaction: ViewerInteractionState = parseViewerInteraction(query);
const fidelityCrop = fidelityMode ? parseCrop(query.get("crop")) : null;
const fidelityFullViewport = {
  widthPx: CURRENT_FIDELITY_VIEWPORT.widthPx * CURRENT_FIDELITY_SUPERSAMPLE,
  heightPx: CURRENT_FIDELITY_VIEWPORT.heightPx * CURRENT_FIDELITY_SUPERSAMPLE
};

app.dataset.rendererBackend = "three-webgl2";
app.dataset.rendererReady = "false";
app.dataset.frameRendered = "false";
app.dataset.fidelityMode = fidelityMode ? "true" : "false";
app.dataset.fidelityOverlay = fidelityOverlayMode ? "true" : "false";
app.dataset.fidelityCrop = fidelityCrop ? `${fidelityCrop.xPx},${fidelityCrop.yPx},${fidelityCrop.widthPx},${fidelityCrop.heightPx}` : "none";
app.dataset.colorTreatment = "fh06-s10-neutral-warm-v1";
app.dataset.occlusion = "gtao-mm-v1";
app.dataset.occlusionRadiusMm = String(FH06_GTAO_PROFILE.radiusMm);
app.dataset.occlusionBlend = String(FH06_GTAO_PROFILE.blendIntensity);
app.dataset.viewerTransitionMode = "incremental-domain-sync-v1";

const renderer = new WebGLRenderer({ antialias: true, alpha: false, powerPreference: "high-performance" });
renderer.outputColorSpace = SRGBColorSpace;
renderer.toneMapping = ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.0;
renderer.shadowMap.enabled = true;
renderer.setPixelRatio(fidelityCrop ? 1 : Math.min(window.devicePixelRatio || 1, fidelityMode ? CURRENT_FIDELITY_SUPERSAMPLE : 2));
app.appendChild(renderer.domElement);

let viewport = { widthPx: 1, heightPx: 1 };
const camera = createThreeCamera(currentFixedCamera, fidelityCrop ? fidelityFullViewport : viewport);

function buildComposition(state: ViewerConfigurationState): ViewerComposition {
  const scene = deriveViewerScene(currentSceneBase, state);
  const appearance = deriveViewerAppearance(styleAnchorAppearance, scene, state);
  return createViewerComposition(renderer, camera, scene, appearance, {
    widthPx: viewport.widthPx,
    heightPx: viewport.heightPx
  });
}

const composition = buildComposition(configuration);
let selectionOverlay: ModuleSelectionOverlay | null = null;

function installFidelityOverlay(target: ViewerComposition): void {
  if (!fidelityOverlayMode || fidelityCrop) return;
  const fidelityLines = createCurrentFidelityOverlayLines();
  const fidelityOverlay = buildFidelityOverlay(fidelityLines, { xray: true, opacity: 0.72 });
  fidelityOverlay.renderOrder = 10_000;
  target.adapter.scene.add(fidelityOverlay);
  app.dataset.fidelityLineCount = String(fidelityLines.length);
}

function installSelectionOverlay(target: ViewerComposition): void {
  selectionOverlay?.dispose();
  selectionOverlay = createModuleSelectionOverlay(target.adapter, target.scenePackage);
  target.adapter.scene.add(selectionOverlay.root);
  selectionOverlay.setSelectedModule(interaction.selectedModuleId);
}

function groupVisible(entityId: string): string {
  return composition.adapter.entityGroups.get(entityId)?.visible ? "true" : "false";
}

function syncDatasets(): void {
  const diagnostics = composition.diagnostics;
  app.dataset.sceneId = composition.scenePackage.sceneId;
  app.dataset.viewerConfiguration = configurationFingerprint(configuration);
  app.dataset.viewerSelectedModule = interaction.selectedModuleId ?? "none";
  app.dataset.viewerHoveredModule = interaction.hoveredModuleId ?? "none";
  app.dataset.viewerStonePreset = configuration.stonePresetId;
  app.dataset.viewerLightingPreset = configuration.lightingPresetId;
  app.dataset.viewerLightingPolicy = composition.appearance.lighting.id;
  app.dataset.viewerModule02Visible = groupVisible(MODULE02_ID);
  app.dataset.viewerOvenVisible = groupVisible(OVEN_ID);
  app.dataset.viewerCooktopVisible = groupVisible(COOKTOP_ID);
  app.dataset.viewerRangeVisible = groupVisible(RANGE_ID);
  app.dataset.viewerModule06Visible = groupVisible(MODULE06_ID);
  app.dataset.viewerMicrowaveVisible = groupVisible(MICRO_ID);
  app.dataset.viewerUnderCabVisible = groupVisible(UNDERCAB_ID);
  app.dataset.viewerModule03FrontMaterial = resolveMaterialId(composition.appearance, MODULE03_ID, "front");
  app.dataset.viewerStone03Material = resolveMaterialId(composition.appearance, STONE03_ID, "stone");
  app.dataset.viewerSelectionOverlayCount = String(selectionOverlay?.root.children.length ?? 0);
  app.dataset.cooktopContact = diagnostics.cooktopContactId;
  app.dataset.cooktopGapMm = diagnostics.cooktopGapMm.toFixed(3);
  app.dataset.frontReadability = diagnostics.frontReadabilityId;
  app.dataset.frontPhysicalGapMm = diagnostics.frontPhysicalGapMm.join(",");
  app.dataset.ovenReadability = diagnostics.ovenReadabilityId;
  app.dataset.ovenPhysicalClearanceMm = diagnostics.ovenPhysicalClearanceMm.join(",");
  app.dataset.wallTileCoverage = "full-wall";
  app.dataset.wallTileSurfaceCount = String(diagnostics.wallTileSurfaceCount);
  app.dataset.sinkRefinement = diagnostics.sinkFamilyId;
  app.dataset.sinkStoneHole = diagnostics.sinkStoneHole;
  app.dataset.sinkContinuousBowl = diagnostics.sinkContinuousBowl ? "true" : "false";
  app.dataset.faucetRefinement = diagnostics.faucetPresetId;
  app.dataset.faucetHost = diagnostics.faucetHostEntityId;
  app.dataset.underCabProfile = "rear-corner-18mm-45deg";
  app.dataset.underCabKelvin = String(diagnostics.underCabKelvin);
  app.dataset.underCabHost = diagnostics.underCabHostModuleId;
  app.dataset.underCabAreaLight = diagnostics.underCabAreaLight ? "true" : "false";
  app.dataset.renderOwnership = composition.ownership.pass ? "pass" : "fail";
}

installFidelityOverlay(composition);
installSelectionOverlay(composition);
syncDatasets();

function render(): void {
  composition.render();
  app.dataset.frameRendered = "true";
}

function applyConfigurationAction(action: ViewerConfigurationAction): void {
  const proposed = reduceViewerConfiguration(configuration, action);
  const nextScene = deriveViewerScene(currentSceneBase, proposed);
  const nextAppearance = deriveViewerAppearance(styleAnchorAppearance, nextScene, proposed);

  switch (action.type) {
    case "set-module-visibility":
      composition.syncVisibility(nextScene, nextAppearance);
      break;
    case "set-front-preset":
    case "clear-front-preset":
    case "set-stone-preset":
      composition.syncMaterials(nextScene, nextAppearance);
      break;
    case "set-lighting-preset":
      composition.syncLighting(nextScene, nextAppearance);
      break;
    case "reset-configuration":
      composition.syncConfiguration(nextScene, nextAppearance);
      break;
  }

  configuration = proposed;
  selectionOverlay?.setSelectedModule(interaction.selectedModuleId);
  syncDatasets();
  render();
}

function selectModule(moduleId: string | null): void {
  interaction = reduceViewerInteraction(interaction, { type: "select-module", moduleId });
  selectionOverlay?.setSelectedModule(moduleId);
  syncDatasets();
  render();
}

function pointerNdc(event: MouseEvent): readonly [number, number] {
  const rect = renderer.domElement.getBoundingClientRect();
  if (rect.width <= 0 || rect.height <= 0) return [0, 0];
  return [
    ((event.clientX - rect.left) / rect.width) * 2 - 1,
    -(((event.clientY - rect.top) / rect.height) * 2 - 1)
  ];
}

renderer.domElement.addEventListener("pointermove", event => {
  const moduleId = pickModuleAtNdc(composition.adapter, composition.scenePackage, camera, pointerNdc(event));
  if (moduleId === interaction.hoveredModuleId) return;
  interaction = reduceViewerInteraction(interaction, { type: "hover-module", moduleId });
  app.dataset.viewerHoveredModule = moduleId ?? "none";
});

renderer.domElement.addEventListener("click", event => {
  const moduleId = pickModuleAtNdc(composition.adapter, composition.scenePackage, camera, pointerNdc(event));
  selectModule(moduleId);
});

export interface ViewerRuntimeControlApi {
  getConfiguration(): ViewerConfigurationState;
  getInteraction(): ViewerInteractionState;
  setModuleVisibility(alias: string, value: ViewerVisibilityOverride): void;
  setFrontPreset(alias: string, presetId: FrontPresetId): void;
  clearFrontPreset(alias: string): void;
  setStonePreset(presetId: StonePresetId): void;
  setLightingPreset(presetId: LightingPresetId): void;
  resetConfiguration(): void;
  selectModule(alias: string | null): void;
}

const runtimeApi: ViewerRuntimeControlApi = {
  getConfiguration: () => configuration,
  getInteraction: () => interaction,
  setModuleVisibility(alias, value): void {
    applyConfigurationAction({ type: "set-module-visibility", moduleId: moduleIdFromAlias(alias), value });
  },
  setFrontPreset(alias, presetId): void {
    applyConfigurationAction({ type: "set-front-preset", moduleId: moduleIdFromAlias(alias), presetId });
  },
  clearFrontPreset(alias): void {
    applyConfigurationAction({ type: "clear-front-preset", moduleId: moduleIdFromAlias(alias) });
  },
  setStonePreset(presetId): void {
    applyConfigurationAction({ type: "set-stone-preset", presetId });
  },
  setLightingPreset(presetId): void {
    applyConfigurationAction({ type: "set-lighting-preset", presetId });
  },
  resetConfiguration(): void {
    applyConfigurationAction({ type: "reset-configuration" });
  },
  selectModule(alias): void {
    selectModule(alias === null ? null : moduleIdFromAlias(alias));
  }
};

(window as Window & { __MOBILIPRESENTER_VIEWER__?: ViewerRuntimeControlApi }).__MOBILIPRESENTER_VIEWER__ = runtimeApi;

interface RendererResourceSnapshot {
  readonly geometries: number;
  readonly textures: number;
  readonly programs: number;
}

type LifecycleFamily = "visibility" | "appearance" | "lighting" | "selection";

function rendererResourceSnapshot(): RendererResourceSnapshot {
  return {
    geometries: renderer.info.memory.geometries,
    textures: renderer.info.memory.textures,
    programs: renderer.info.programs?.length ?? 0
  };
}

function resourceSnapshotText(value: RendererResourceSnapshot): string {
  return `${value.geometries},${value.textures},${value.programs}`;
}

function lifecycleCycle(family: LifecycleFamily): void {
  switch (family) {
    case "visibility":
      runtimeApi.setModuleVisibility("02", "off");
      runtimeApi.setModuleVisibility("02", "inherit");
      return;
    case "appearance":
      runtimeApi.setStonePreset("graphite-speckled");
      runtimeApi.setStonePreset("light-speckled");
      return;
    case "lighting":
      runtimeApi.setLightingPreset("warm-worktop");
      runtimeApi.setLightingPreset("canonical");
      return;
    case "selection":
      for (let index = 0; index < 20; index += 1) {
        runtimeApi.selectModule("03");
        runtimeApi.selectModule(null);
      }
      return;
  }
}

function runLifecycleExercise(family: LifecycleFamily): void {
  lifecycleCycle(family);
  const before = rendererResourceSnapshot();
  const startedMs = performance.now();
  lifecycleCycle(family);
  const durationMs = performance.now() - startedMs;
  const after = rendererResourceSnapshot();
  const pass =
    after.geometries <= before.geometries &&
    after.textures <= before.textures &&
    after.programs <= before.programs;

  app.dataset.viewerLifecycleFamily = family;
  app.dataset.viewerLifecycleBefore = resourceSnapshotText(before);
  app.dataset.viewerLifecycleAfter = resourceSnapshotText(after);
  app.dataset.viewerLifecycleDurationMs = durationMs.toFixed(1);
  app.dataset.viewerLifecycleStatus = pass ? "pass" : "fail";
  syncDatasets();
  render();
  if (!pass) {
    throw new Error(`VIEWER_RESOURCE_GROWTH:${family}:${resourceSnapshotText(before)}:${resourceSnapshotText(after)}`);
  }
}

function resize(): void {
  const widthPx = Math.max(1, Math.round(app.clientWidth));
  const heightPx = Math.max(1, Math.round(app.clientHeight));
  viewport = { widthPx, heightPx };
  renderer.setSize(widthPx, heightPx, false);
  if (fidelityCrop) updateThreeCameraCrop(camera, currentFixedCamera, fidelityFullViewport, fidelityCrop);
  else updateThreeCameraViewport(camera, currentFixedCamera, viewport);
  composition.setSize(widthPx, heightPx);
  render();
}

const observer = new ResizeObserver(resize);
observer.observe(app);
app.dataset.rendererReady = "true";
resize();
const lifecycleExercise = query.get("exercise");
if (lifecycleExercise?.startsWith("lifecycle-")) {
  const family = lifecycleExercise.slice("lifecycle-".length);
  if (!["visibility", "appearance", "lighting", "selection"].includes(family)) {
    throw new Error(`VIEWER_LIFECYCLE_FAMILY_UNKNOWN:${family}`);
  }
  runLifecycleExercise(family as LifecycleFamily);
}

window.addEventListener("pagehide", () => {
  observer.disconnect();
  selectionOverlay?.dispose();
  composition.dispose();
  renderer.dispose();
}, { once: true });
