import "./main.js";
import { moduleIdFromAlias } from "./runtime/query.js";
import { mountRuntimeControls, type RuntimeControlsUi } from "./ui/runtime-controls.js";
import type { ViewerRuntimeControlApi } from "./main.js";

const app = document.querySelector<HTMLElement>("#app");
if (!app) throw new Error("APP_ROOT_NOT_FOUND");

const query = new URLSearchParams(window.location.search);
// Preview-only policy: controls are visible by default on the temporary Netlify branch.
// `controls=0` remains available for baseline inspection; fidelity mode always suppresses UI.
const controlsEnabled = query.get("controls") !== "0" && query.get("fidelity") !== "1";
app.dataset.viewerControls = controlsEnabled ? "true" : "false";

let controls: RuntimeControlsUi | null = null;

if (controlsEnabled) {
  const runtime = (window as Window & { __MOBILIPRESENTER_VIEWER__?: ViewerRuntimeControlApi }).__MOBILIPRESENTER_VIEWER__;
  if (!runtime) throw new Error("VIEWER_RUNTIME_API_NOT_FOUND");

  controls = mountRuntimeControls(document.body, {
    ...runtime,
    isModuleVisible(alias: string): boolean {
      const moduleId = moduleIdFromAlias(alias);
      return runtime.getConfiguration().visibilityByModule[moduleId] !== "off";
    }
  });

  const refreshAfterSceneClick = (event: MouseEvent): void => {
    if (!(event.target instanceof HTMLCanvasElement)) return;
    queueMicrotask(() => controls?.refresh());
  };
  document.addEventListener("click", refreshAfterSceneClick);

  window.addEventListener("pagehide", () => {
    document.removeEventListener("click", refreshAfterSceneClick);
    controls?.dispose();
    controls = null;
  }, { once: true });
}
