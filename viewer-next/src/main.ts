import {
  createCurrentFidelityOverlayLines,
  CURRENT_FIDELITY_SUPERSAMPLE,
  CURRENT_FIDELITY_VIEWPORT,
  currentFaucetAnchor,
  currentFixedCamera,
  currentSceneBase
} from "@mobilipresenter/scene-core";
import {
  ACESFilmicToneMapping,
  Color,
  SRGBColorSpace,
  WebGLRenderer
} from "three";
import { styleAnchorAppearance } from "./fixtures/style-anchor.js";
import { attachParametricAppliances } from "./renderer/three/appliances.js";
import {
  createThreeCamera,
  updateThreeCameraCrop,
  updateThreeCameraViewport,
  type PixelCrop
} from "./renderer/three/camera.js";
import { applyFh06FaucetRefinement } from "./renderer/three/faucet-refinement.js";
import { buildFidelityOverlay } from "./renderer/three/fidelity-overlay.js";
import { buildThreeLighting, installNeutralRoomEnvironment } from "./renderer/three/lighting.js";
import { ThreeMaterialRegistry } from "./renderer/three/materials.js";
import { createSelectiveBloomPipeline } from "./renderer/three/post.js";
import { buildThreeScene } from "./renderer/three/scene-adapter.js";
import { applyFh06SinkRefinement } from "./renderer/three/sink-refinement.js";
import { applyFh06VisualRefinements } from "./renderer/three/visual-refinements.js";

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

const fidelityCrop = fidelityMode ? parseCrop(query.get("crop")) : null;
const fidelityFullViewport = {
  widthPx: CURRENT_FIDELITY_VIEWPORT.widthPx * CURRENT_FIDELITY_SUPERSAMPLE,
  heightPx: CURRENT_FIDELITY_VIEWPORT.heightPx * CURRENT_FIDELITY_SUPERSAMPLE
};

app.dataset.rendererBackend = "three-webgl2";
app.dataset.rendererReady = "false";
app.dataset.frameRendered = "false";
app.dataset.sceneId = currentSceneBase.sceneId;
app.dataset.fidelityMode = fidelityMode ? "true" : "false";
app.dataset.fidelityOverlay = fidelityOverlayMode ? "true" : "false";
app.dataset.fidelityCrop = fidelityCrop ? `${fidelityCrop.xPx},${fidelityCrop.yPx},${fidelityCrop.widthPx},${fidelityCrop.heightPx}` : "none";

const renderer = new WebGLRenderer({
  antialias: true,
  alpha: false,
  powerPreference: "high-performance"
});
renderer.outputColorSpace = SRGBColorSpace;
renderer.toneMapping = ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
renderer.shadowMap.enabled = true;
renderer.setPixelRatio(fidelityCrop ? 1 : Math.min(window.devicePixelRatio || 1, fidelityMode ? CURRENT_FIDELITY_SUPERSAMPLE : 2));
app.appendChild(renderer.domElement);

const materials = new ThreeMaterialRegistry(styleAnchorAppearance);
const adapter = buildThreeScene(
  currentSceneBase,
  (entityId, slot) => materials.resolve(entityId, slot)
);
attachParametricAppliances(adapter, currentSceneBase, styleAnchorAppearance, materials);
applyFh06VisualRefinements(adapter, materials);
const sinkRefinement = applyFh06SinkRefinement(adapter, materials, currentSceneBase);
const faucetRefinement = applyFh06FaucetRefinement(adapter, materials, currentFaucetAnchor);
app.dataset.sinkRefinement = sinkRefinement.sinkFamilyId;
app.dataset.sinkStoneHole = sinkRefinement.stoneHoleGeometry;
app.dataset.sinkContinuousBowl = sinkRefinement.continuousBowl ? "true" : "false";
app.dataset.faucetRefinement = faucetRefinement.presetId;
app.dataset.faucetHost = faucetRefinement.hostEntityId;
adapter.scene.background = new Color(0xf3f2ee);

if (fidelityOverlayMode && !fidelityCrop) {
  const fidelityLines = createCurrentFidelityOverlayLines();
  const fidelityOverlay = buildFidelityOverlay(fidelityLines, { xray: true, opacity: 0.72 });
  fidelityOverlay.renderOrder = 10_000;
  adapter.scene.add(fidelityOverlay);
  app.dataset.fidelityLineCount = String(fidelityLines.length);
}

const lighting = buildThreeLighting(currentSceneBase, styleAnchorAppearance);
adapter.scene.add(lighting.root);
const environment = installNeutralRoomEnvironment(
  renderer,
  adapter.scene,
  styleAnchorAppearance.lighting.environment.relativeIntensity
);

let viewport = { widthPx: 1, heightPx: 1 };
const camera = createThreeCamera(currentFixedCamera, fidelityCrop ? fidelityFullViewport : viewport);
const post = createSelectiveBloomPipeline(
  renderer,
  adapter.scene,
  camera,
  styleAnchorAppearance,
  viewport.widthPx,
  viewport.heightPx
);

function render(): void {
  post.render();
  app.dataset.frameRendered = "true";
}

function resize(): void {
  const widthPx = Math.max(1, Math.round(app.clientWidth));
  const heightPx = Math.max(1, Math.round(app.clientHeight));
  viewport = { widthPx, heightPx };
  renderer.setSize(widthPx, heightPx, false);
  if (fidelityCrop) {
    updateThreeCameraCrop(camera, currentFixedCamera, fidelityFullViewport, fidelityCrop);
  } else {
    updateThreeCameraViewport(camera, currentFixedCamera, viewport);
  }
  post.setSize(widthPx, heightPx);
  render();
}

const observer = new ResizeObserver(resize);
observer.observe(app);
app.dataset.rendererReady = "true";
resize();

window.addEventListener("pagehide", () => {
  observer.disconnect();
  post.dispose();
  environment.dispose();
  materials.dispose();
  renderer.dispose();
}, { once: true });
