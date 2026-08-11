import "./main.js";
import { createViewerUiApi, type ViewerEngineControlPort } from "./api/ui-adapter.js";
import { mountRuntimeControls, type RuntimeControlsUi } from "./ui/runtime-controls.js";
import { mountEditorialEnhancements, type EditorialEnhancements } from "./ui/editorial-enhancements.js";

const app = document.querySelector<HTMLElement>("#app");
if (!app) throw new Error("APP_ROOT_NOT_FOUND");

const query = new URLSearchParams(window.location.search);
const controlsEnabled = query.get("controls") === "1" && query.get("fidelity") !== "1";
app.dataset.viewerControls = controlsEnabled ? "true" : "false";

let controls: RuntimeControlsUi | null = null;
let editorial: EditorialEnhancements | null = null;

if (controlsEnabled) {
  const runtime = (window as Window & { __MOBILIPRESENTER_VIEWER__?: ViewerEngineControlPort }).__MOBILIPRESENTER_VIEWER__;
  if (!runtime) throw new Error("VIEWER_RUNTIME_API_NOT_FOUND");
  const uiApi = createViewerUiApi(runtime);

  controls = mountRuntimeControls(document.body, uiApi);
  editorial = mountEditorialEnhancements(document.body, uiApi);

  const refreshAfterSceneClick = (event: MouseEvent): void => {
    if (!(event.target instanceof HTMLCanvasElement)) return;
    queueMicrotask(() => {
      controls?.refresh();
      editorial?.refresh();
    });
  };
  document.addEventListener("click", refreshAfterSceneClick);

  window.addEventListener("pagehide", () => {
    document.removeEventListener("click", refreshAfterSceneClick);
    editorial?.dispose();
    editorial = null;
    controls?.dispose();
    controls = null;
  }, { once: true });
}
