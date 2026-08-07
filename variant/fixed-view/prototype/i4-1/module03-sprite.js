async function loadText(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) throw new Error(`Falha ao carregar ${path}: ${response.status}`);
  return (await response.text()).trim();
}

const [sceneB64, detailB64, manifest] = await Promise.all([
  loadText("./i4-1-assets/module03-sprite.b64"),
  loadText("./i4-1-assets/module03-detail.b64"),
  fetch("./i4-1-assets/manifest.json", { cache: "no-store" }).then(r => {
    if (!r.ok) throw new Error(`Falha ao carregar manifest I4.1: ${r.status}`);
    return r.json();
  })
]);

const sceneWrap = document.querySelector("#scene-wrap");
const moduleScene = document.querySelector("#module-scene");
const sceneModules = document.querySelector("#scene-modules");
const sceneHits = document.querySelector("#scene-hit-areas");
const moduleList = document.querySelector("#module-list");
const moduleDetail = document.querySelector("#module-detail");
if (!sceneWrap || !moduleScene || !sceneModules || !sceneHits || !moduleList || !moduleDetail) {
  throw new Error("DOM incompleto para o I4.1.");
}

const style = document.createElement("link");
style.rel = "stylesheet";
style.href = "./i4-1/module03-sprite.css";
document.head.append(style);

const sceneSprite = document.createElement("img");
sceneSprite.className = "i41-module03-sprite";
sceneSprite.src = `data:image/webp;base64,${sceneB64}`;
sceneSprite.alt = "";
sceneSprite.setAttribute("aria-hidden", "true");
sceneSprite.dataset.moduleId = manifest.moduleId;
moduleScene.before(sceneSprite);

function selectedId() {
  return sceneHits.querySelector(".scene-hit.is-selected")?.dataset.moduleId ?? null;
}

function enabled() {
  return Boolean(sceneModules.querySelector('.scene-module[data-module-id="lower-sink"].is-enabled'));
}

function syncScene() {
  sceneSprite.classList.toggle("is-enabled", enabled());
  sceneSprite.classList.toggle("is-selected", selectedId() === manifest.moduleId);
}

function syncThumb() {
  const row = moduleList.querySelector('.module-row[data-module-id="lower-sink"]');
  const thumb = row?.querySelector(".module-thumb");
  if (!thumb || thumb.dataset.i41Ready === "true") return;
  thumb.dataset.i41Ready = "true";
  thumb.classList.add("i41-realistic-thumb");
  thumb.replaceChildren();
  const img = document.createElement("img");
  img.src = `data:image/webp;base64,${detailB64}`;
  img.alt = "Módulo 03, quatro gavetas e duas portas";
  thumb.append(img);
}

function syncDetail() {
  if (selectedId() !== manifest.moduleId) return;
  const hero = moduleDetail.querySelector(".detail-hero");
  if (!hero || hero.dataset.i41Ready === "true") return;
  hero.dataset.i41Ready = "true";
  hero.classList.add("i41-realistic-detail");
  hero.replaceChildren();
  const img = document.createElement("img");
  img.src = `data:image/webp;base64,${detailB64}`;
  img.alt = "Prévia realista do módulo 03 com quatro gavetas e duas portas";
  hero.append(img);
  const label = document.createElement("span");
  label.className = "i41-label";
  label.textContent = "Sprite independente · 4 gavetas + 2 portas";
  hero.append(label);
}

function relabelMode() {
  const button = document.querySelector('button[data-base-mode="reference-context"]');
  if (!button) return;
  button.textContent = "Sprite realista 03 β";
  button.title = "Prova do pipeline de sprite independente do módulo 03; os demais módulos continuam no fallback estrutural.";
}

function installChip() {
  const actions = document.querySelector(".topbar-actions");
  if (!actions || actions.querySelector("[data-i41-chip]")) return;
  const chip = document.createElement("span");
  chip.className = "status-chip";
  chip.dataset.i41Chip = "true";
  chip.textContent = "I4.1 · sprite 03";
  chip.title = "Primeiro módulo realista independente; medidas continuam não fabris.";
  actions.prepend(chip);
}

function syncAll() {
  syncScene();
  syncThumb();
  syncDetail();
}

relabelMode();
installChip();
syncAll();

const observer = new MutationObserver(() => queueMicrotask(syncAll));
observer.observe(sceneModules, { subtree: true, childList: true, attributes: true, attributeFilter: ["class"] });
observer.observe(sceneHits, { subtree: true, childList: true, attributes: true, attributeFilter: ["class"] });
observer.observe(moduleList, { subtree: true, childList: true });
observer.observe(moduleDetail, { subtree: true, childList: true });

window.MOBILI_I41 = Object.freeze({ manifest });
