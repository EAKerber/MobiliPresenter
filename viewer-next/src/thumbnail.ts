import {
  currentFixedCamera,
  currentSceneBase,
  setEntityMaterialOverride,
  setVisibilityIntent,
  type AppearancePackage,
  type ScenePackage
} from "@mobilipresenter/scene-core";
import {
  ACESFilmicToneMapping,
  SRGBColorSpace,
  WebGLRenderer
} from "three";
import { styleAnchorAppearance } from "./fixtures/style-anchor.js";
import { createThreeCamera } from "./renderer/three/camera.js";
import { createViewerComposition } from "./runtime/composition.js";
import { moduleIdFromAlias, type ModuleAlias } from "./runtime/query.js";
import { FRONT_PRESETS } from "./runtime/presets.js";

const MODULE_ALIASES = ["01", "02", "03", "04", "05", "06", "07"] as const satisfies readonly ModuleAlias[];
const THUMBNAIL_SIZE = 512;
const THUMBNAIL_PADDING = 42;
const ALPHA_THRESHOLD = 8;

const appElement = document.querySelector<HTMLElement>("#app");
if (!appElement) throw new Error("THUMBNAIL_APP_ROOT_NOT_FOUND");
const app: HTMLElement = appElement;

const query = new URLSearchParams(window.location.search);
const aliasValue = query.get("module");
if (!aliasValue || !MODULE_ALIASES.includes(aliasValue as ModuleAlias)) {
  throw new Error(`THUMBNAIL_MODULE_UNKNOWN:${aliasValue ?? "none"}`);
}
const alias = aliasValue as ModuleAlias;
const moduleId = moduleIdFromAlias(alias);

function isolateTargetModule(): ScenePackage {
  let scene = currentSceneBase;
  for (const entity of currentSceneBase.environment) {
    scene = setVisibilityIntent(scene, entity.id, "off");
  }
  for (const item of currentSceneBase.items) {
    scene = setVisibilityIntent(scene, item.id, "off");
  }
  for (const module of currentSceneBase.modules) {
    scene = setVisibilityIntent(scene, module.id, module.id === moduleId ? "on" : "off");
  }
  return scene;
}

function applyWarmWoodToTarget(scene: ScenePackage): AppearancePackage {
  const module = scene.modules.find(candidate => candidate.id === moduleId);
  if (!module) throw new Error(`THUMBNAIL_MODULE_NOT_FOUND:${alias}`);
  let appearance = styleAnchorAppearance;
  const materialId = FRONT_PRESETS["warm-wood"].materialId;
  const slots = new Set(
    module.geometry
      .map(primitive => primitive.materialSlot)
      .filter((slot): slot is string => Boolean(slot))
  );
  for (const slot of slots) {
    appearance = setEntityMaterialOverride(appearance, moduleId, slot, materialId);
  }
  return appearance;
}

function alphaBounds(data: Uint8ClampedArray, width: number, height: number): {
  readonly minX: number;
  readonly minY: number;
  readonly maxX: number;
  readonly maxY: number;
  readonly opaquePixels: number;
} | null {
  let minX = width;
  let minY = height;
  let maxX = -1;
  let maxY = -1;
  let opaquePixels = 0;
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const alpha = data[(y * width + x) * 4 + 3]!;
      if (alpha <= ALPHA_THRESHOLD) continue;
      opaquePixels += 1;
      minX = Math.min(minX, x);
      minY = Math.min(minY, y);
      maxX = Math.max(maxX, x);
      maxY = Math.max(maxY, y);
    }
  }
  return maxX >= minX && maxY >= minY
    ? { minX, minY, maxX, maxY, opaquePixels }
    : null;
}

function cropRenderedModule(source: HTMLCanvasElement): {
  readonly canvas: HTMLCanvasElement;
  readonly opaquePixels: number;
  readonly crop: readonly [number, number, number, number];
} {
  const scratch = document.createElement("canvas");
  scratch.width = THUMBNAIL_SIZE;
  scratch.height = THUMBNAIL_SIZE;
  const scratchContext = scratch.getContext("2d", { alpha: true, willReadFrequently: true });
  if (!scratchContext) throw new Error("THUMBNAIL_SCRATCH_CONTEXT_UNAVAILABLE");
  scratchContext.clearRect(0, 0, THUMBNAIL_SIZE, THUMBNAIL_SIZE);
  scratchContext.drawImage(source, 0, 0, THUMBNAIL_SIZE, THUMBNAIL_SIZE);
  const pixels = scratchContext.getImageData(0, 0, THUMBNAIL_SIZE, THUMBNAIL_SIZE);
  const bounds = alphaBounds(pixels.data, THUMBNAIL_SIZE, THUMBNAIL_SIZE);
  if (!bounds || bounds.opaquePixels < 1_000) {
    throw new Error(`THUMBNAIL_EMPTY_RENDERED_FRAME:${alias}:${bounds?.opaquePixels ?? 0}`);
  }

  const cropX = bounds.minX;
  const cropY = bounds.minY;
  const cropWidth = bounds.maxX - bounds.minX + 1;
  const cropHeight = bounds.maxY - bounds.minY + 1;
  const output = document.createElement("canvas");
  output.width = THUMBNAIL_SIZE;
  output.height = THUMBNAIL_SIZE;
  output.style.width = "100%";
  output.style.height = "100%";
  output.setAttribute("aria-hidden", "true");
  output.dataset.thumbnailOutput = "true";
  const outputContext = output.getContext("2d", { alpha: true });
  if (!outputContext) throw new Error("THUMBNAIL_OUTPUT_CONTEXT_UNAVAILABLE");
  outputContext.clearRect(0, 0, THUMBNAIL_SIZE, THUMBNAIL_SIZE);
  const available = THUMBNAIL_SIZE - THUMBNAIL_PADDING * 2;
  const scale = Math.min(available / cropWidth, available / cropHeight);
  const drawWidth = cropWidth * scale;
  const drawHeight = cropHeight * scale;
  const drawX = (THUMBNAIL_SIZE - drawWidth) / 2;
  const drawY = (THUMBNAIL_SIZE - drawHeight) / 2;
  outputContext.drawImage(
    scratch,
    cropX,
    cropY,
    cropWidth,
    cropHeight,
    drawX,
    drawY,
    drawWidth,
    drawHeight
  );
  return {
    canvas: output,
    opaquePixels: bounds.opaquePixels,
    crop: [cropX, cropY, cropWidth, cropHeight]
  };
}

const scene = isolateTargetModule();
const appearance = applyWarmWoodToTarget(scene);
const renderer = new WebGLRenderer({
  antialias: true,
  alpha: true,
  preserveDrawingBuffer: true,
  premultipliedAlpha: false,
  powerPreference: "high-performance"
});
renderer.outputColorSpace = SRGBColorSpace;
renderer.toneMapping = ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.0;
renderer.shadowMap.enabled = true;
renderer.setPixelRatio(1);
renderer.setClearColor(0x000000, 0);
renderer.setSize(THUMBNAIL_SIZE, THUMBNAIL_SIZE, false);
renderer.domElement.style.width = "100%";
renderer.domElement.style.height = "100%";
app.append(renderer.domElement);

const camera = createThreeCamera(currentFixedCamera, {
  widthPx: THUMBNAIL_SIZE,
  heightPx: THUMBNAIL_SIZE
});
const composition = createViewerComposition(renderer, camera, scene, appearance, {
  widthPx: THUMBNAIL_SIZE,
  heightPx: THUMBNAIL_SIZE
});
composition.adapter.scene.background = null;
composition.syncInteraction(null, null);
composition.setSize(THUMBNAIL_SIZE, THUMBNAIL_SIZE);
composition.render();

const cropped = cropRenderedModule(renderer.domElement);
app.replaceChildren(cropped.canvas);
app.dataset.rendererReady = "true";
app.dataset.frameRendered = "true";
app.dataset.thumbnailModule = alias;
app.dataset.thumbnailRenderer = "viewer-composition-three-webgl2";
app.dataset.thumbnailScenePolicy = "current-scene-isolated-entity-visibility-v1";
app.dataset.thumbnailCameraPolicy = "current-fixed-camera-then-crop-v1";
app.dataset.thumbnailBackground = "transparent";
app.dataset.thumbnailMaterial = FRONT_PRESETS["warm-wood"].materialId;
app.dataset.thumbnailOpaquePixels = String(cropped.opaquePixels);
app.dataset.thumbnailCrop = cropped.crop.join(",");

window.addEventListener("pagehide", () => {
  composition.dispose();
  renderer.dispose();
}, { once: true });
