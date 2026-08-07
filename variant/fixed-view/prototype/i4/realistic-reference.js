const SVG_NS = "http://www.w3.org/2000/svg";

const calibration = window.MOBILI_I3_CALIBRATION;
const assets = window.MOBILI_I1_ASSETS;

if (!calibration || !assets) {
  throw new Error("I4 requer assets e calibração I3 já carregados.");
}

const style = document.createElement("link");
style.rel = "stylesheet";
style.href = "./i4/realistic-reference.css";
document.head.append(style);

const sceneWrap = document.querySelector("#scene-wrap");
const moduleScene = document.querySelector("#module-scene");
const sceneModules = document.querySelector("#scene-modules");
const sceneHits = document.querySelector("#scene-hit-areas");
const moduleList = document.querySelector("#module-list");
const moduleDetail = document.querySelector("#module-detail");
const neutralScene = document.querySelector(".neutral-scene");

if (!sceneWrap || !moduleScene || !sceneModules || !sceneHits || !moduleList || !moduleDetail || !neutralScene) {
  throw new Error("Estrutura DOM I4 incompleta.");
}

const evidence = calibration.evidenceSpace;
const placementById = new Map(calibration.placements.map(item => [item.moduleId, item]));

function svg(name, attrs = {}) {
  const node = document.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, String(value));
  return node;
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function paddedRect(rect, moduleId, mode = "thumb") {
  const narrow = moduleId === "refrigerator-side-panel";
  const basePadX = narrow ? (mode === "detail" ? 120 : 80) : Math.max(18, rect.width * (mode === "detail" ? .22 : .14));
  const basePadY = narrow ? 26 : Math.max(12, rect.height * (mode === "detail" ? .16 : .10));
  const x = clamp(rect.x - basePadX, 0, evidence.width);
  const y = clamp(rect.y - basePadY, 0, evidence.height);
  const right = clamp(rect.x + rect.width + basePadX, 0, evidence.width);
  const bottom = clamp(rect.y + rect.height + basePadY, 0, evidence.height);
  return { x, y, width: Math.max(1, right - x), height: Math.max(1, bottom - y) };
}

function buildCrop(moduleId, rect, mode = "thumb", focus = false) {
  const view = paddedRect(rect, moduleId, mode);
  const crop = document.createElement("div");
  crop.className = "i4-reference-crop";
  crop.style.aspectRatio = `${view.width} / ${view.height}`;

  const image = document.createElement("img");
  image.src = assets.referenceComposition;
  image.alt = "";
  image.setAttribute("aria-hidden", "true");
  image.style.width = `${evidence.width / view.width * 100}%`;
  image.style.height = `${evidence.height / view.height * 100}%`;
  image.style.left = `${-view.x / view.width * 100}%`;
  image.style.top = `${-view.y / view.height * 100}%`;
  crop.append(image);

  if (focus) {
    const box = document.createElement("span");
    box.className = "i4-focus-box";
    box.style.left = `${(rect.x - view.x) / view.width * 100}%`;
    box.style.top = `${(rect.y - view.y) / view.height * 100}%`;
    box.style.width = `${rect.width / view.width * 100}%`;
    box.style.height = `${rect.height / view.height * 100}%`;
    crop.append(box);
  }

  return crop;
}

function buildRealisticLayer() {
  const layer = svg("svg", {
    viewBox: `0 0 ${evidence.width} ${evidence.height}`,
    preserveAspectRatio: "none",
    "aria-hidden": "true"
  });
  layer.classList.add("realistic-reference-layer");

  const defs = svg("defs");
  layer.append(defs);

  for (const placement of calibration.placements) {
    const { moduleId, rect } = placement;
    const clipId = `i4-clip-${moduleId.replace(/[^a-z0-9_-]/gi, "-")}`;
    const clip = svg("clipPath", { id: clipId });
    clip.append(svg("rect", { x: rect.x, y: rect.y, width: rect.width, height: rect.height, rx: 2 }));
    defs.append(clip);

    const group = svg("g", { "data-realistic-module-id": moduleId });
    group.classList.add("realistic-module");

    const image = svg("image", {
      href: assets.referenceComposition,
      x: 0,
      y: 0,
      width: evidence.width,
      height: evidence.height,
      preserveAspectRatio: "none",
      "clip-path": `url(#${clipId})`
    });
    group.append(image);
    layer.append(group);
  }

  moduleScene.before(layer);
  return layer;
}

function installArchitectureColumn() {
  const column = calibration.architecture?.laundryColumn;
  const rect = column?.cameraRect;
  if (!column || !rect) return;

  const plane = document.createElement("div");
  plane.className = "architecture-column";
  plane.dataset.architectureId = "laundry-column";
  plane.title = `Coluna fixa: ${column.wallSpanMm} mm × ${column.internalProjectionMm} mm de avanço interno.`;
  plane.style.left = `${rect.x / evidence.width * 100}%`;
  plane.style.width = `${rect.width / evidence.width * 100}%`;
  neutralScene.append(plane);
}

function activeModuleId() {
  return sceneHits.querySelector(".scene-hit.is-selected")?.dataset.moduleId ?? null;
}

function syncRealisticLayer(layer) {
  const enabled = new Set(
    [...sceneModules.querySelectorAll(".scene-module[data-module-id].is-enabled")]
      .map(node => node.dataset.moduleId)
      .filter(Boolean)
  );
  const selected = activeModuleId();
  const last = sceneHits.querySelector(".scene-hit.is-last-enabled")?.dataset.moduleId ?? null;

  for (const node of layer.querySelectorAll("[data-realistic-module-id]")) {
    const id = node.dataset.realisticModuleId;
    node.classList.toggle("is-enabled", enabled.has(id));
    node.classList.toggle("is-selected", selected === id);
    node.classList.toggle("is-last-enabled", last === id && enabled.has(id));
  }
}

function syncThumbs() {
  for (const row of moduleList.querySelectorAll(".module-row[data-module-id]")) {
    const id = row.dataset.moduleId;
    const placement = placementById.get(id);
    const thumb = row.querySelector(".module-thumb");
    if (!placement || !thumb || thumb.dataset.i4Ready === "true") continue;
    thumb.dataset.i4Ready = "true";
    thumb.classList.add("i4-realistic-thumb");
    thumb.append(buildCrop(id, placement.rect, "thumb", false));
  }
}

function syncDetail() {
  const id = activeModuleId();
  const placement = id ? placementById.get(id) : null;
  const hero = moduleDetail.querySelector(".detail-hero");
  if (!placement || !hero || hero.dataset.i4ModuleId === id) return;

  hero.dataset.i4ModuleId = id;
  hero.classList.add("i4-realistic-detail");
  hero.replaceChildren(buildCrop(id, placement.rect, "detail", true));

  const label = document.createElement("span");
  label.className = "i4-preview-label";
  label.textContent = id === "refrigerator-side-panel" ? "Referência visual · painel 18 mm" : "Referência visual do módulo";
  hero.append(label);

  if (!moduleDetail.querySelector(".i4-realistic-note")) {
    const note = document.createElement("p");
    note.className = "i4-realistic-note";
    note.textContent = "Prévia recortada da composição fornecida; serve para consistência visual, não para derivar cotas.";
    hero.after(note);
  }
}

function relabelModeButton() {
  const button = document.querySelector('button[data-base-mode="reference-context"]');
  if (!button) return;
  button.textContent = "Render realista β";
  button.title = "Usa recortes da própria composição de referência para testar o pipeline visual realista.";
}

function installStatusChip() {
  const actions = document.querySelector(".topbar-actions");
  if (!actions || actions.querySelector("[data-i4-chip]")) return;
  const chip = document.createElement("span");
  chip.className = "status-chip";
  chip.dataset.i4Chip = "true";
  chip.textContent = "I4 · referência realista β";
  chip.title = "Pixels reais da referência são usados como overlays; módulos sem overlay continuam protegidos pelo fallback estrutural.";
  actions.prepend(chip);
}

const realisticLayer = buildRealisticLayer();
installArchitectureColumn();
relabelModeButton();
installStatusChip();

function syncAll() {
  syncRealisticLayer(realisticLayer);
  syncThumbs();
  syncDetail();
}

const observer = new MutationObserver(() => queueMicrotask(syncAll));
observer.observe(sceneModules, { subtree: true, childList: true, attributes: true, attributeFilter: ["class"] });
observer.observe(sceneHits, { subtree: true, childList: true, attributes: true, attributeFilter: ["class"] });
observer.observe(moduleList, { subtree: true, childList: true });
observer.observe(moduleDetail, { subtree: true, childList: true });

document.querySelectorAll("[data-base-mode]").forEach(button => button.addEventListener("click", () => setTimeout(syncAll, 0)));

syncAll();
