async function loadReferenceAsset(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) throw new Error(`Falha ao carregar ${path}: ${response.status}`);
  return (await response.text()).trim();
}

async function loadJson(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) throw new Error(`Falha ao carregar ${path}: ${response.status}`);
  return response.json();
}

Promise.all([
  loadReferenceAsset("./i2-assets/project-reference.b64"),
  loadReferenceAsset("./i2-assets/reference-composition.b64"),
  loadJson("./i3-data/calibration.json")
]).then(async ([projectImage, referenceComposition, calibration]) => {
  window.MOBILI_I1_ASSETS = Object.freeze({
    projectImage: `data:image/webp;base64,${projectImage}`,
    referenceComposition: `data:image/webp;base64,${referenceComposition}`
  });
  window.MOBILI_I3_CALIBRATION = Object.freeze(calibration);

  document.body.dataset.geometryStatus = calibration.status;
  const actions = document.querySelector(".topbar-actions");
  if (actions && !document.querySelector("[data-calibration-chip]")) {
    const chip = document.createElement("span");
    chip.className = "status-chip";
    chip.dataset.calibrationChip = "true";
    chip.textContent = "Calibração visual · não fabril";
    chip.title = "Posições calibradas na referência visual; pixels não representam cotas de fabricação.";
    actions.prepend(chip);
  }

  await import("./i2/app.js");
  await import("./i4/realistic-reference.js");
}).catch(error => {
  console.error("Falha ao iniciar MobiliPresenter I4.", error);
  const target = document.querySelector("#diagnostics-summary");
  if (target) target.textContent = "Falha ao carregar contratos, referências ou a camada visual I4. Consulte o console.";
});
