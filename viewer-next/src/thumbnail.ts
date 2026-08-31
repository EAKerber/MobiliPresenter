import {
  currentFixedCamera,
  currentSceneBase,
  module01,
  module02,
  module03WithSink,
  module04,
  module05,
  module06,
  module07,
  setEntityMaterialOverride,
  type ScenePackage
} from "@mobilipresenter/scene-core";
import {
  ACESFilmicToneMapping,
  Box3,
  MathUtils,
  Sphere,
  SRGBColorSpace,
  Vector3,
  WebGLRenderer
} from "three";
import { styleAnchorAppearance } from "./fixtures/style-anchor.js";
import { createThreeCamera } from "./renderer/three/camera.js";
import { createViewerComposition } from "./runtime/composition.js";

const MODULES = {
  "01": module01,
  "02": module02,
  "03": module03WithSink,
  "04": module04,
  "05": module05,
  "06": module06,
  "07": module07
} as const;

type ThumbnailAlias = keyof typeof MODULES;

const appElement = document.querySelector<HTMLElement>("#app");
if (!appElement) throw new Error("THUMBNAIL_APP_ROOT_NOT_FOUND");
const app: HTMLElement = appElement;

const query = new URLSearchParams(window.location.search);
const aliasValue = query.get("module");
if (!aliasValue || !(aliasValue in MODULES)) {
  throw new Error(`THUMBNAIL_MODULE_UNKNOWN:${aliasValue ?? "none"}`);
}
const alias = aliasValue as ThumbnailAlias;
const moduleDefinition = MODULES[alias];

const scene: ScenePackage = {
  ...currentSceneBase,
  sceneId: `thumbnail-${alias}`,
  environment: [],
  items: [],
  modules: [moduleDefinition],
  sourceBindings: [],
  substitutionGroups: []
};

let appearance = setEntityMaterialOverride(styleAnchorAppearance, moduleDefinition.id, "front", "front-wood");
appearance = setEntityMaterialOverride(appearance, moduleDefinition.id, "carcass", "front-wood");

const renderer = new WebGLRenderer({
  antialias: true,
  alpha: true,
  powerPreference: "high-performance"
});
renderer.outputColorSpace = SRGBColorSpace;
renderer.toneMapping = ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.0;
renderer.shadowMap.enabled = true;
renderer.setClearColor(0x000000, 0);
renderer.setPixelRatio(1);
app.append(renderer.domElement);

const viewport = { widthPx: Math.max(1, app.clientWidth), heightPx: Math.max(1, app.clientHeight) };
const camera = createThreeCamera(currentFixedCamera, viewport);
const composition = createViewerComposition(renderer, camera, scene, appearance, viewport);
composition.adapter.scene.background = null;

function fitCamera(): void {
  const group = composition.adapter.entityGroups.get(moduleDefinition.id);
  if (!group) throw new Error(`THUMBNAIL_MODULE_GROUP_NOT_FOUND:${alias}`);
  group.updateWorldMatrix(true, true);
  const bounds = new Box3().setFromObject(group);
  if (bounds.isEmpty()) throw new Error(`THUMBNAIL_MODULE_BOUNDS_EMPTY:${alias}`);

  const sphere = bounds.getBoundingSphere(new Sphere());
  const center = sphere.center;
  const direction = camera.getWorldDirection(new Vector3()).normalize();
  const verticalFov = MathUtils.degToRad(camera.fov);
  const horizontalFov = 2 * Math.atan(Math.tan(verticalFov / 2) * camera.aspect);
  const fitDistance = Math.max(
    sphere.radius / Math.max(0.01, Math.sin(verticalFov / 2)),
    sphere.radius / Math.max(0.01, Math.sin(horizontalFov / 2))
  ) * 1.28;

  camera.position.copy(center).addScaledVector(direction, -fitDistance);
  camera.near = Math.max(1, fitDistance - sphere.radius * 2.4);
  camera.far = fitDistance + sphere.radius * 4;
  camera.lookAt(center);
  camera.updateProjectionMatrix();
}

function render(): void {
  const widthPx = Math.max(1, Math.round(app.clientWidth));
  const heightPx = Math.max(1, Math.round(app.clientHeight));
  renderer.setSize(widthPx, heightPx, false);
  camera.aspect = widthPx / heightPx;
  camera.updateProjectionMatrix();
  fitCamera();
  composition.setSize(widthPx, heightPx);
  composition.render();
  app.dataset.rendererReady = "true";
  app.dataset.frameRendered = "true";
  app.dataset.thumbnailModule = alias;
  app.dataset.thumbnailBackground = "transparent";
}

render();

window.addEventListener("pagehide", () => {
  composition.dispose();
  renderer.dispose();
}, { once: true });
