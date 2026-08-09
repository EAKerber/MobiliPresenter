import { currentFixedCamera, currentSceneBase } from "@mobilipresenter/scene-core";
import { Color, MeshBasicMaterial, SRGBColorSpace, WebGLRenderer } from "three";
import { createThreeCamera, updateThreeCameraViewport } from "./renderer/three/camera.js";
import { buildThreeScene } from "./renderer/three/scene-adapter.js";

const app = document.querySelector<HTMLElement>("#app");
if (!app) throw new Error("APP_ROOT_NOT_FOUND");

const renderer = new WebGLRenderer({ antialias: true, alpha: false });
renderer.outputColorSpace = SRGBColorSpace;
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
app.appendChild(renderer.domElement);

const materialColors: Readonly<Record<string, number>> = {
  wall: 0xf3f1ec,
  carcass: 0xf8f8f6,
  front: 0xaaa59f,
  stone: 0xb8b2a5,
  glass: 0xd7e4e8,
  emissive: 0xffd08a,
  __unassigned__: 0xc8c5bd
};

const adapter = buildThreeScene(currentSceneBase, (_entityId, slot) => new MeshBasicMaterial({
  color: materialColors[slot] ?? 0xc8c5bd,
  transparent: slot === "glass",
  opacity: slot === "glass" ? 0.2 : 1,
  depthWrite: slot !== "glass"
}));
adapter.scene.background = new Color(0xf3f2ee);

let viewport = { widthPx: 1, heightPx: 1 };
const camera = createThreeCamera(currentFixedCamera, viewport);

function render(): void {
  renderer.render(adapter.scene, camera);
}

function resize(): void {
  const widthPx = Math.max(1, Math.round(app.clientWidth));
  const heightPx = Math.max(1, Math.round(app.clientHeight));
  viewport = { widthPx, heightPx };
  renderer.setSize(widthPx, heightPx, false);
  updateThreeCameraViewport(camera, currentFixedCamera, viewport);
  render();
}

const observer = new ResizeObserver(resize);
observer.observe(app);
resize();
