import {
  createCurrentFidelityOverlayLines,
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
import { createThreeCamera, updateThreeCameraViewport } from "./renderer/three/camera.js";
import { buildFidelityOverlay } from "./renderer/three/fidelity-overlay.js";
import { buildThreeLighting, installNeutralRoomEnvironment } from "./renderer/three/lighting.js";
import { ThreeMaterialRegistry } from "./renderer/three/materials.js";
import { createSelectiveBloomPipeline } from "./renderer/three/post.js";
import { buildThreeScene } from "./renderer/three/scene-adapter.js";

const appElement = document.querySelector<HTMLElement>("#app");
if (appElement === null) throw new Error("APP_ROOT_NOT_FOUND");
const app: HTMLElement = appElement;

const fidelityMode = new URLSearchParams(window.location.search).get("fidelity") === "1";

app.dataset.rendererBackend = "three-webgl2";
app.dataset.rendererReady = "false";
app.dataset.frameRendered = "false";
app.dataset.sceneId = currentSceneBase.sceneId;
app.dataset.fidelityOverlay = fidelityMode ? "true" : "false";

const renderer = new WebGLRenderer({
  antialias: true,
  alpha: false,
  powerPreference: "high-performance"
});
renderer.outputColorSpace = SRGBColorSpace;
renderer.toneMapping = ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
renderer.shadowMap.enabled = true;
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, fidelityMode ? 4 : 2));
app.appendChild(renderer.domElement);

const materials = new ThreeMaterialRegistry(styleAnchorAppearance);
const adapter = buildThreeScene(
  currentSceneBase,
  (entityId, slot) => materials.resolve(entityId, slot)
);
attachParametricAppliances(adapter, currentSceneBase, styleAnchorAppearance, materials);
adapter.scene.background = new Color(0xf3f2ee);

if (fidelityMode) {
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
const camera = createThreeCamera(currentFixedCamera, viewport);
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
  updateThreeCameraViewport(camera, currentFixedCamera, viewport);
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
