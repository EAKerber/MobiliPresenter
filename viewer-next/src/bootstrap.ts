import "./ui/product-polish-v2-final.css";
import { createViewerUiApi, type ViewerEngineControlPort } from "./api/ui-adapter.js";
import {
  installDesktopCompositionEnhancement,
  type DesktopCompositionEnhancement
} from "./ui/desktop-composition.js";
import {
  installProductCtaAccessibility,
  type ProductCtaAccessibility
} from "./ui/product-cta-accessibility.js";
import {
  installProductContractEnhancements,
  type ProductContractEnhancements
} from "./ui/product-contract-enhancements.js";
import { installProductPolishV2, type ProductPolishV2 } from "./ui/product-polish-v2.js";
import { installProductUiEnhancements, type ProductUiEnhancements } from "./ui/product-enhancements.js";
import { installGlobalFinishControl } from "./ui/global-finish-readiness.js";
import { mountRuntimeControls, type RuntimeControlsUi } from "./ui/runtime-controls.js";
import { migrateLegacyUniformFrontQuery } from "./runtime/query.js";

const initialQuery = new URLSearchParams(window.location.search);
const queryMigration = migrateLegacyUniformFrontQuery(initialQuery);
if (queryMigration.migratedLegacyUniformFront) {
  const canonicalUrl = new URL(window.location.href);
  canonicalUrl.search = queryMigration.query.toString();
  window.history.replaceState(window.history.state, "", canonicalUrl);
}

await import("./main.js");

const app = document.querySelector<HTMLElement>("#app");
if (!app) throw new Error("APP_ROOT_NOT_FOUND");

app.dataset.viewerQueryMigration = queryMigration.migratedLegacyUniformFront
  ? "legacy-uniform-front-to-finish"
  : "none";

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
let disposeGlobalFinishControl: (() => void) | null = null;
let productEnhancements: ProductUiEnhancements | null = null;
let desktopComposition: DesktopCompositionEnhancement | null = null;
let productPolishV2: ProductPolishV2 | null = null;
let productContractEnhancements: ProductContractEnhancements | null = null;
let productCtaAccessibility: ProductCtaAccessibility | null = null;

if (controlsEnabled) {
  const runtime = (window as Window & { __MOBILIPRESENTER_VIEWER__?: ViewerEngineControlPort }).__MOBILIPRESENTER_VIEWER__;
  if (!runtime) throw new Error("VIEWER_RUNTIME_API_NOT_FOUND");
  const uiApi = createViewerUiApi(runtime);

  controls = mountRuntimeControls(document.body, uiApi);
  disposeGlobalFinishControl = installGlobalFinishControl(uiApi, controls);
  productEnhancements = installProductUiEnhancements(uiApi, controls);
  desktopComposition = installDesktopCompositionEnhancement();
  productPolishV2 = installProductPolishV2(uiApi);
  productContractEnhancements = installProductContractEnhancements(uiApi);
  productCtaAccessibility = installProductCtaAccessibility();

  const refreshAfterSceneClick = (event: MouseEvent): void => {
    if (!(event.target instanceof HTMLCanvasElement)) return;
    queueMicrotask(() => controls?.refresh());
  };
  document.addEventListener("click", refreshAfterSceneClick);

  window.addEventListener("pagehide", () => {
    document.removeEventListener("click", refreshAfterSceneClick);
    productCtaAccessibility?.dispose();
    productCtaAccessibility = null;
    productContractEnhancements?.dispose();
    productContractEnhancements = null;
    productPolishV2?.dispose();
    productPolishV2 = null;
    desktopComposition?.dispose();
    desktopComposition = null;
    productEnhancements?.dispose();
    productEnhancements = null;
    disposeGlobalFinishControl?.();
    disposeGlobalFinishControl = null;
    controls?.dispose();
    controls = null;
  }, { once: true });
}
