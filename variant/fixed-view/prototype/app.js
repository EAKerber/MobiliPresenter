import("./i2/app.js").catch(error => {
  console.error("Falha ao iniciar MobiliPresenter I2.", error);
  const target = document.querySelector("#diagnostics-summary");
  if (target) target.textContent = "Falha ao carregar os contratos I2. Consulte o console.";
});
