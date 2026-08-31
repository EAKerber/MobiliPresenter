import {
  currentSceneBase,
  module01,
  module02,
  module03WithSink,
  module04,
  module05,
  module06,
  module07,
  type ScenePackage
} from "@mobilipresenter/scene-core";
import {
  AmbientLight,
  Box3,
  DirectionalLight,
  HemisphereLight,
  MathUtils,
  Mesh,
  MeshStandardMaterial,
  PerspectiveCamera,
  Sphere,
  SRGBColorSpace,
  Vector3,
  WebGLRenderer
} from "three";
import { buildThreeScene } from "./renderer/three/scene-adapter.js";

const MODULES = {
  "01": module01,
  "02": module02,
  "03": module03WithSink,
  "04": module04,
  "05": module05,
  "06": module06,
  "07": module07
} as const;

const THUMBNAIL_WOOD = "#A8744D";
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

const renderer = new WebGLRenderer({
  antialias: true,
  alpha: true,
  preserveDrawingBuffer: true,
  powerPreference: "high-performance"
});
renderer.outputColorSpace = SRGBColorSpace;
renderer.setClearColor(0x000000, 0);
renderer.setPixelRatio(1);
app.append(renderer.domElement);

const camera = new PerspectiveCamera(30, 1, 1, 100_000);
const woodMaterial = new MeshStandardMaterial({
  color: THUMBNAIL_WOOD,
  roughness: 0.62,
  metalness: 0
});
woodMaterial.name = "front-wood-thumbnail-preview";
const adapter = buildThreeScene(scene, () => woodMaterial);
adapter.scene.background = null;

const hemisphere = new HemisphereLight(0xffffff, 0x8a8177, 2.2);
const ambient = new AmbientLight(0xffffff, 0.85);
const key = new DirectionalLight(0xffffff, 2.5);
key.position.set(-1800, 2400, 2200);
const fill = new DirectionalLight(0xfff5e8, 1.2);
fill.position.set(2200, 1200, 900);
adapter.scene.add(hemisphere, ambient, key, fill);

function fitCamera(): void {
  const group = adapter.entityGroups.get(moduleDefinition.id);
  if (!group) throw new Error(`THUMBNAIL_MODULE_GROUP_NOT_FOUND:${alias}`);
  if (!group.visible) throw new Error(`THUMBNAIL_MODULE_NOT_VISIBLE:${alias}`);
  group.updateWorldMatrix(true, true);
  const bounds = new Box3().setFromObject(group);
  if (bounds.isEmpty()) throw new Error(`THUMBNAIL_MODULE_BOUNDS_EMPTY:${alias}`);

  const sphere = bounds.getBoundingSphere(new Sphere());
  const center = sphere.center;
  const verticalFov = MathUtils.degToRad(camera.fov);
  const horizontalFov = 2 * Math.atan(Math.tan(verticalFov / 2) * camera.aspect);
  const fitDistance = Math.max(
    sphere.radius / Math.max(0.01, Math.sin(verticalFov / 2)),
    sphere.radius / Math.max(0.01, Math.sin(horizontalFov / 2))
  ) * 1.18;

  const viewingDirection = new Vector3(0.86, 0.48, 1.15).normalize();
  camera.position.copy(center).addScaledVector(viewingDirection, fitDistance);
  camera.near = Math.max(1, fitDistance - sphere.radius * 2.2);
  camera.far = fitDistance + sphere.radius * 3.5;
  camera.lookAt(center);
  camera.updateProjectionMatrix();

  const projectedCenter = center.clone().project(camera);
  if (Math.abs(projectedCenter.x) > 0.05 || Math.abs(projectedCenter.y) > 0.05 || projectedCenter.z < -1 || projectedCenter.z > 1) {
    throw new Error(`THUMBNAIL_CAMERA_FRAME_INVALID:${alias}:${projectedCenter.toArray().join(",")}`);
  }

  app.dataset.thumbnailBounds = [
    bounds.min.x, bounds.min.y, bounds.min.z,
    bounds.max.x, bounds.max.y, bounds.max.z
  ].map(value => value.toFixed(2)).join(",");
  app.dataset.thumbnailCamera = [camera.position.x, camera.position.y, camera.position.z]
    .map(value => value.toFixed(2)).join(",");
}

function assertRenderedPixels(widthPx: number, heightPx: number): void {
  const gl = renderer.getContext();
  const pixels = new Uint8Array(widthPx * heightPx * 4);
  gl.readPixels(0, 0, widthPx, heightPx, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
  let opaquePixels = 0;
  for (let index = 3; index < pixels.length; index += 4) {
    if (pixels[index]! > 0) opaquePixels += 1;
  }
  if (opaquePixels < 512) throw new Error(`THUMBNAIL_EMPTY_FRAME:${alias}:${opaquePixels}`);
  app.dataset.thumbnailOpaquePixels = String(opaquePixels);
}

function render(): void {
  const widthPx = Math.max(1, Math.round(app.clientWidth));
  const heightPx = Math.max(1, Math.round(app.clientHeight));
  renderer.setSize(widthPx, heightPx, false);
  camera.aspect = widthPx / heightPx;
  camera.updateProjectionMatrix();
  fitCamera();
  renderer.render(adapter.scene, camera);
  assertRenderedPixels(widthPx, heightPx);
  app.dataset.rendererReady = "true";
  app.dataset.frameRendered = "true";
  app.dataset.thumbnailModule = alias;
  app.dataset.thumbnailBackground = "transparent";
  app.dataset.thumbnailCameraPolicy = "isolated-product-three-quarter-v1";
  app.dataset.thumbnailMaterial = "warm-wood-preview";
}

render();

window.addEventListener("pagehide", () => {
  adapter.scene.traverse(object => {
    if (object instanceof Mesh) object.geometry.dispose();
  });
  woodMaterial.dispose();
  renderer.dispose();
}, { once: true });
