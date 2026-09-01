import { readFileSync } from "node:fs";
import { join } from "node:path";

const runtimeRoot = "artifacts/runtime-ui";
const navigationRoot = "artifacts/product-ui-navigation";

function read(path) {
  return readFileSync(path, "utf8");
}

function requireMarkers(html, source, markers) {
  const missing = markers.filter(marker => !html.includes(marker));
  if (missing.length > 0) {
    throw new Error(`PRODUCT_CONTRACT_UI_MARKERS_MISSING:${source}:${JSON.stringify(missing)}`);
  }
}

function rejectMarkers(html, source, markers) {
  const present = markers.filter(marker => html.includes(marker));
  if (present.length > 0) {
    throw new Error(`PRODUCT_CONTRACT_UI_INTERNAL_COPY_LEAK:${source}:${JSON.stringify(present)}`);
  }
}

const module02 = read(join(runtimeRoot, "runtime-ui-desktop-modules-detail.html"));
requireMarkers(module02, "module02-detail", [
  'data-product-descriptor="true"',
  "Inferior do fogão",
  'data-product-descriptor-dimensions="true"',
  'data-product-semantic-icon-source="published-key"',
  'data-semantic-icon-key="electrical.outlet"',
  'data-product-finish-source="published-visual"'
]);

const module01 = read(join(runtimeRoot, "runtime-ui-desktop-cataloged-01.html"));
requireMarkers(module01, "module01-detail", [
  "Aéreo da lavanderia",
  'data-product-descriptor="true"',
  'data-semantic-icon-key="hardware.hinge"'
]);

const accessories = read(join(navigationRoot, "navigation-accessories.html"));
requireMarkers(accessories, "accessories", [
  "Acessórios ainda não disponíveis para seleção",
  "Puxadores e outros opcionais aparecerão aqui"
]);
rejectMarkers(accessories, "accessories", [
  "contrato público",
  "binding de runtime",
  "publicadas pelo contrato"
]);

const summary = read(join(navigationRoot, "navigation-summary.html"));
requireMarkers(summary, "summary", [
  'data-product-summary-furniture="true"',
  'data-product-finish-source="configuration-state"',
  "Cor dos móveis",
  "Aéreo da lavanderia",
  "Inferior do fogão",
  "Valor ainda não disponível"
]);
rejectMarkers(summary, "summary", [
  "contrato atual",
  "authority comercial",
  "Aguardando fonte comercial"
]);

process.stdout.write(`${JSON.stringify({
  status: "PASS",
  invariants: {
    moduleDescriptorsProjected: true,
    descriptorDimensionsProjected: true,
    semanticIconsUsePublishedKeys: true,
    finishDotsUsePublishedVisuals: true,
    summaryUsesPublishedModuleIdentity: true,
    summaryUsesFirstClassFurnitureFinish: true,
    implementationLanguageDoesNotLeakToProductPlaceholders: true
  }
}, null, 2)}\n`);
