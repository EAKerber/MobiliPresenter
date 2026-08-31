import "./main.js";
import { createViewerUiApi, type ViewerEngineControlPort } from "./api/ui-adapter.js";
import { installProductUiEnhancements, type ProductUiEnhancements } from "./ui/product-enhancements.js";
import { mountRuntimeControls, type RuntimeControlsUi } from "./ui/runtime-controls.js";

const app = document.querySelector<HTMLElement>("#app");
if (!app) throw new Error("APP_ROOT_NOT_FOUND");

const query = new URLSearchParams(window.location.search);
const defaultUiMode = (import.meta as ImportMeta & {
  readonly env: { readonly VITE_DEFAULT_UI_MODE?: string };
}).env.VITE_DEFAULT_UI_MODE === "product";
const controlsPreference = query.get("controls");
const controlsEnabled = query.get("fidelity") !== "1" && (
  controlsPreference === "1" ||
  (controlsPreference !== "0" && defaultUiMode)
);
app.dataset.viewerControls = controlsEnabled ? "true" : "false";
app.dataset.viewerUiMode = controlsEnabled ? "product" : "renderer-only";

let controls: RuntimeControlsUi | null = null;
let productEnhancements: ProductUiEnhancements | null = null;

if (controlsEnabled) {
  const runtime = (window as Window & { __MOBILIPRESENTER_VIEWER__?: ViewerEngineControlPort }).__MOBILIPRESENTER_VIEWER__;
  if (!runtime) throw new Error("VIEWER_RUNTIME_API_NOT_FOUND");
  const uiApi = createViewerUiApi(runtime);

  controls = mountRuntimeControls(document.body, uiApi);
  productEnhancements = installProductUiEnhancements(uiApi, controls);

  const refreshAfterSceneClick = (event: MouseEvent): void => {
    if (!(event.target instanceof HTMLCanvasElement)) return;
    queueMicrotask(() => controls?.refresh());
  };
  document.addEventListener("click", refreshAfterSceneClick);

  window.addEventListener("pagehide", () => {
    document.removeEventListener("click", refreshAfterSceneClick);
    productEnhancements?.dispose();
    productEnhancements = null;
    controls?.dispose();
    controls = null;
  }, { once: true });
}
