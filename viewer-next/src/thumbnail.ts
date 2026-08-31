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
  Color,
  MeshBasicMaterial,
  NoToneMapping,
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
const MATTE_COLOR = new Color(0xf0ede7);

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

function readCanvas(source: HTMLCanvasElement): ImageData {
  const canvas = document.createElement("canvas");
  canvas.width = THUMBNAIL_SIZE;
  canvas.height = THUMBNAIL_SIZE;
  const context = canvas.getContext("2d", { alpha: true, willReadFrequently: true });
  if (!context) throw new Error("THUMBNAIL_READBACK_CONTEXT_UNAVAILABLE");
  context.clearRect(0, 0, THUMBNAIL_SIZE, THUMBNAIL_SIZE);
  context.drawImage(source, 0, 0, THUMBNAIL_SIZE, THUMBNAIL_SIZE);
  return context.getImageData(0, 0, THUMBNAIL_SIZE, THUMBNAIL_SIZE);
}

function isolateCompositionVisuals(
  composition: ReturnType<typeof createViewerComposition>
): void {
  const target = composition.adapter.entityGroups.get(moduleId);
  if (!target) throw new Error(`THUMBNAIL_TARGET_GROUP_MISSING:${alias}`);
  for (const child of composition.adapter.scene.children) {
    child.visible = child === target || child.name === "__lighting/base";
  }
}

function renderColorPass(
  renderer: WebGLRenderer,
  composition: ReturnType<typeof createViewerComposition>
): ImageData {
  composition.adapter.scene.overrideMaterial = null;
  composition.adapter.scene.background = MATTE_COLOR;
  renderer.toneMapping = ACESFilmicToneMapping;
  renderer.setClearColor(MATTE_COLOR, 1);
  composition.render();
  return readCanvas(renderer.domElement);
}

function renderMaskPass(
  renderer: WebGLRenderer,
  composition: ReturnType<typeof createViewerComposition>,
  camera: ReturnType<typeof createThreeCamera>
): ImageData {
  const maskMaterial = new MeshBasicMaterial({ color: 0xffffff, toneMapped: false });
  composition.adapter.scene.overrideMaterial = maskMaterial;
  composition.adapter.scene.background = new Color(0x000000);
  renderer.toneMapping = NoToneMapping;
  renderer.setClearColor(0x000000, 1);
  renderer.clear(true, true, true);
  renderer.render(composition.adapter.scene, camera);
  const result = readCanvas(renderer.domElement);
  composition.adapter.scene.overrideMaterial = null;
  maskMaterial.dispose();
  return result;
}

function transparentComposite(color: ImageData, mask: ImageData): ImageData {
  const output = new ImageData(THUMBNAIL_SIZE, THUMBNAIL_SIZE);
  const background = [color.data[0]!, color.data[1]!, color.data[2]!] as const;
  for (let index = 0; index < color.data.length; index += 4) {
    const maskValue = Math.max(mask.data[index]!, mask.data[index + 1]!, mask.data[index + 2]!);
    const alpha = Math.max(0, Math.min(1, maskValue / 255));
    if (alpha <= ALPHA_THRESHOLD / 255) continue;
    for (let channel = 0; channel < 3; channel += 1) {
      const observed = color.data[index + channel]!;
      const matte = background[channel]!;
      const foreground = alpha >= 0.999
        ? observed
        : (observed - matte * (1 - alpha)) / Math.max(alpha, 0.001);
      output.data[index + channel] = Math.max(0, Math.min(255, Math.round(foreground)));
    }
    output.data[index + 3] = Math.round(alpha * 255);
  }
  return output;
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

function cropRenderedModule(composite: ImageData): {
  readonly canvas: HTMLCanvasElement;
  readonly opaquePixels: number;
  readonly crop: readonly [number, number, number, number];
} {
  const source = document.createElement("canvas");
  source.width = THUMBNAIL_SIZE;
  source.height = THUMBNAIL_SIZE;
  const sourceContext = source.getContext("2d", { alpha: true });
  if (!sourceContext) throw new Error("THUMBNAIL_SOURCE_CONTEXT_UNAVAILABLE");
  sourceContext.putImageData(composite, 0, 0);

  const bounds = alphaBounds(composite.data, THUMBNAIL_SIZE, THUMBNAIL_SIZE);
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
    source,
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
composition.syncInteraction(null, null);
composition.setSize(THUMBNAIL_SIZE, THUMBNAIL_SIZE);
isolateCompositionVisuals(composition);

const colorPass = renderColorPass(renderer, composition);
const maskPass = renderMaskPass(renderer, composition, camera);
const composite = transparentComposite(colorPass, maskPass);
const cropped = cropRenderedModule(composite);
app.replaceChildren(cropped.canvas);
app.dataset.rendererReady = "true";
app.dataset.frameRendered = "true";
app.dataset.thumbnailModule = alias;
app.dataset.thumbnailRenderer = "viewer-composition-three-webgl2";
app.dataset.thumbnailScenePolicy = "current-scene-isolated-entity-visibility-v2";
app.dataset.thumbnailCameraPolicy = "current-fixed-camera-then-crop-v1";
app.dataset.thumbnailMaskPolicy = "same-renderer-geometry-mask-v1";
app.dataset.thumbnailBackground = "transparent";
app.dataset.thumbnailMaterial = FRONT_PRESETS["warm-wood"].materialId;
app.dataset.thumbnailOpaquePixels = String(cropped.opaquePixels);
app.dataset.thumbnailCrop = cropped.crop.join(",");

window.addEventListener("pagehide", () => {
  composition.dispose();
  renderer.dispose();
}, { once: true });
