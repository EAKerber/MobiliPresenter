import {
  createCurrentFidelityOverlayLines,
  CURRENT_FIDELITY_SUPERSAMPLE,
  CURRENT_FIDELITY_VIEWPORT,
  currentFixedCamera,
  currentSceneBase
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
import { createViewerComposition } from "./runtime/composition.js";
import { parseViewerConfiguration, parseViewerInteraction } from "./runtime/query.js";
import {
  configurationFingerprint,
  deriveViewerAppearance,
  deriveViewerScene
} from "./runtime/viewer-state.js";

const appElement = document.querySelector<HTMLElement>("#app");
if (appElement === null) throw new Error("APP_ROOT_NOT_FOUND");
const app: HTMLElement = appElement;

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

const configuration = parseViewerConfiguration(query);
const interaction = parseViewerInteraction(query);
const effectiveScene = deriveViewerScene(currentSceneBase, configuration);
const effectiveAppearance = deriveViewerAppearance(styleAnchorAppearance, effectiveScene, configuration);
const fidelityCrop = fidelityMode ? parseCrop(query.get("crop")) : null;
const fidelityFullViewport = {
  widthPx: CURRENT_FIDELITY_VIEWPORT.widthPx * CURRENT_FIDELITY_SUPERSAMPLE,
  heightPx: CURRENT_FIDELITY_VIEWPORT.heightPx * CURRENT_FIDELITY_SUPERSAMPLE
};

app.dataset.rendererBackend = "three-webgl2";
app.dataset.rendererReady = "false";
app.dataset.frameRendered = "false";
app.dataset.sceneId = effectiveScene.sceneId;
app.dataset.fidelityMode = fidelityMode ? "true" : "false";
app.dataset.fidelityOverlay = fidelityOverlayMode ? "true" : "false";
app.dataset.fidelityCrop = fidelityCrop ? `${fidelityCrop.xPx},${fidelityCrop.yPx},${fidelityCrop.widthPx},${fidelityCrop.heightPx}` : "none";
app.dataset.colorTreatment = "fh06-s10-neutral-warm-v1";
app.dataset.occlusion = "gtao-mm-v1";
app.dataset.occlusionRadiusMm = String(FH06_GTAO_PROFILE.radiusMm);
app.dataset.occlusionBlend = String(FH06_GTAO_PROFILE.blendIntensity);
app.dataset.viewerConfiguration = configurationFingerprint(configuration);
app.dataset.viewerSelectedModule = interaction.selectedModuleId ?? "none";
app.dataset.viewerStonePreset = configuration.stonePresetId;
app.dataset.viewerLightingPreset = configuration.lightingPresetId;

const renderer = new WebGLRenderer({ antialias: true, alpha: false, powerPreference: "high-performance" });
renderer.outputColorSpace = SRGBColorSpace;
renderer.toneMapping = ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.0;
renderer.shadowMap.enabled = true;
renderer.setPixelRatio(fidelityCrop ? 1 : Math.min(window.devicePixelRatio || 1, fidelityMode ? CURRENT_FIDELITY_SUPERSAMPLE : 2));
app.appendChild(renderer.domElement);

let viewport = { widthPx: 1, heightPx: 1 };
const camera = createThreeCamera(currentFixedCamera, fidelityCrop ? fidelityFullViewport : viewport);
const composition = createViewerComposition(
  renderer,
  camera,
  effectiveScene,
  effectiveAppearance,
  { widthPx: viewport.widthPx, heightPx: viewport.heightPx }
);

const diagnostics = composition.diagnostics;
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

if (fidelityOverlayMode && !fidelityCrop) {
  const fidelityLines = createCurrentFidelityOverlayLines();
  const fidelityOverlay = buildFidelityOverlay(fidelityLines, { xray: true, opacity: 0.72 });
  fidelityOverlay.renderOrder = 10_000;
  composition.adapter.scene.add(fidelityOverlay);
  app.dataset.fidelityLineCount = String(fidelityLines.length);
}

function render(): void {
  composition.render();
  app.dataset.frameRendered = "true";
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

window.addEventListener("pagehide", () => {
  observer.disconnect();
  composition.dispose();
  renderer.dispose();
}, { once: true });
