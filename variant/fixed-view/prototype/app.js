async function loadReferenceAsset(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) throw new Error(`Falha ao carregar ${path}: ${response.status}`);
  return (await response.text()).trim();
}

Promise.all([
  loadReferenceAsset("./i2-assets/project-reference.b64"),
  loadReferenceAsset("./i2-assets/reference-composition.b64")
]).then(([projectImage, referenceComposition]) => {
  window.MOBILI_I1_ASSETS = Object.freeze({
    projectImage: `data:image/webp;base64,${projectImage}`,
    referenceComposition: `data:image/webp;base64,${referenceComposition}`
  });
  return import("./i2/app.js");
}).catch(error => {
  console.error("Falha ao iniciar MobiliPresenter I2.", error);
  const target = document.querySelector("#diagnostics-summary");
  if (target) target.textContent = "Falha ao carregar os contratos ou referências I2. Consulte o console.";
});
