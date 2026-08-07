(() => {
  "use strict";

  const data = window.MOBILI_I1_DATA;
  const assets = window.MOBILI_I1_ASSETS;
  if (!data || !assets) {
    throw new Error("Dados ou assets do protótipo I1 não foram carregados.");
  }

  const STORAGE_KEY = "mobilipresenter.fixed-view.i1";
  const OPENING_LABELS = {
    "two-hole-handle": "Alça de dois furos",
    "one-hole-point": "Ponto de um furo",
    "pass-through": "Abertura passante"
  };
  const COLORS = [
    { id: "graphite", name: "Grafite", value: "#292b2c" },
    { id: "black", name: "Preto", value: "#111214" },
    { id: "sand", name: "Areia", value: "#b7a88f" },
    { id: "sage", name: "Sálvia", value: "#829180" },
    { id: "petroleum", name: "Azul petróleo", value: "#244e55" },
    { id: "white", name: "Branco", value: "#e9e7e1" }
  ];

  const moduleById = new Map(data.modules.map(module => [module.id, module]));
  const placementById = new Map(data.layout.placements.map(placement => [placement.moduleId, placement]));
  const orderedModules = data.assembly.moduleOrder.map(id => moduleById.get(id)).filter(Boolean);

  function recommendedOpening(module) {
    return module.recommendedOpeningOptions?.[0] ?? null;
  }

  function defaultState() {
    return {
      enabled: [],
      selectedId: null,
      lastEnabledId: null,
      colorId: "graphite",
      baseMode: "neutral-wall",
      openings: Object.fromEntries(
        orderedModules
          .filter(module => module.openingOptions.length)
          .map(module => [module.id, recommendedOpening(module)])
      )
    };
  }

  function loadState() {
    const fallback = defaultState();
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return fallback;
      const parsed = JSON.parse(raw);
      const validIds = new Set(orderedModules.map(module => module.id));
      return {
        ...fallback,
        ...parsed,
        enabled: Array.isArray(parsed.enabled) ? parsed.enabled.filter(id => validIds.has(id)) : [],
        selectedId: validIds.has(parsed.selectedId) ? parsed.selectedId : null,
        lastEnabledId: validIds.has(parsed.lastEnabledId) ? parsed.lastEnabledId : null,
        openings: { ...fallback.openings, ...(parsed.openings || {}) }
      };
    } catch (error) {
      console.warn("Estado local inválido; usando estado inicial.", error);
      return fallback;
    }
  }

  let state = loadState();
  let transientMessage = "";

  const elements = {
    moduleList: document.querySelector("#module-list"),
    rowTemplate: document.querySelector("#module-row-template"),
    selectionCount: document.querySelector("#selection-count"),
    catalogList: document.querySelector("#catalog-list-view"),
    catalogDetail: document.querySelector("#catalog-detail-view"),
    moduleDetail: document.querySelector("#module-detail"),
    backToList: document.querySelector("#back-to-list"),
    sceneWrap: document.querySelector("#scene-wrap"),
    sceneDefs: document.querySelector("#scene-defs"),
    sceneModules: document.querySelector("#scene-modules"),
    sceneHitAreas: document.querySelector("#scene-hit-areas"),
    sceneEmpty: document.querySelector("#scene-empty-state"),
    projectImage: document.querySelector("#project-image"),
    colorOptions: document.querySelector("#color-options"),
    selectedModuleConfig: document.querySelector("#selected-module-config"),
    selectedModuleName: document.querySelector("#selected-module-name"),
    openingSelect: document.querySelector("#opening-select"),
    openingRecommendation: document.querySelector("#opening-recommendation"),
    commercialCount: document.querySelector("#commercial-count"),
    modifierCount: document.querySelector("#modifier-count"),
    issuesList: document.querySelector("#issues-list"),
    diagnosticsSummary: document.querySelector("#diagnostics-summary"),
    finalizeButton: document.querySelector("#finalize-button"),
    enableAll: document.querySelector("#enable-all"),
    resetAll: document.querySelector("#reset-all"),
    applyRecommended: document.querySelector("#apply-recommended")
  };

  function saveState() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  }

  function selectedColor() {
    return COLORS.find(color => color.id === state.colorId) ?? COLORS[0];
  }

  function isEnabled(id) {
    return state.enabled.includes(id);
  }

  function setEnabled(id, enabled, { select = false } = {}) {
    const next = new Set(state.enabled);
    if (enabled) {
      next.add(id);
      state.lastEnabledId = id;
    } else {
      next.delete(id);
      if (state.selectedId === id) state.selectedId = null;
    }
    state.enabled = orderedModules.map(module => module.id).filter(moduleId => next.has(moduleId));
    if (select) state.selectedId = id;
    transientMessage = "";
    commit();
  }

  function selectModule(id, { showDetail = true } = {}) {
    if (!moduleById.has(id)) return;
    state.selectedId = id;
    if (showDetail) {
      elements.catalogList.hidden = true;
      elements.catalogDetail.hidden = false;
    }
    transientMessage = "";
    commit();
  }

  function issues() {
    const result = [];
    if (isEnabled("lighting") && !isEnabled("refrigerator-side-panel")) {
      result.push({
        id: "lighting-requires-refrigerator-side-panel",
        severity: "blocking",
        message: "A iluminação requer a lateral da geladeira (item 04).",
        resolutionLabel: "Incluir item 04",
        resolve: () => setEnabled("refrigerator-side-panel", true)
      });
    }

    for (const module of orderedModules) {
      if (!isEnabled(module.id) || !module.openingOptions.length) continue;
      const current = state.openings[module.id];
      if (!module.recommendedOpeningOptions.includes(current)) {
        result.push({
          id: `opening-${module.id}`,
          severity: "warning",
          moduleId: module.id,
          message: `${module.name}: ${OPENING_LABELS[current] || "opção atual"} diverge do preset recomendado.`,
          resolutionLabel: "Usar recomendado",
          resolve: () => {
            state.openings[module.id] = recommendedOpening(module);
            commit();
          }
        });
      }
    }
    return result;
  }

  function moduleSvg(module, { detail = false } = {}) {
    const color = selectedColor().value;
    const upper = module.placementClass === "upper";
    const lower = module.placementClass === "lower";
    const panel = module.placementClass === "vertical-panel";
    const lighting = module.placementClass === "feature";
    const width = detail ? 520 : 160;
    const height = detail ? 330 : 112;
    const stroke = "#68645e";

    if (lighting) {
      return `<svg viewBox="0 0 ${width} ${height}" aria-hidden="true">
        <rect width="${width}" height="${height}" fill="#eeeae2"/>
        <path d="M${width * .12} ${height * .5}H${width * .88}" stroke="#d6a83b" stroke-width="${detail ? 18 : 7}" stroke-linecap="round"/>
        <path d="M${width * .17} ${height * .58}H${width * .83}" stroke="#ffe078" stroke-width="${detail ? 10 : 4}" opacity=".85"/>
      </svg>`;
    }

    if (panel) {
      return `<svg viewBox="0 0 ${width} ${height}" aria-hidden="true">
        <rect width="${width}" height="${height}" fill="#eeeae2"/>
        <rect x="${width * .37}" y="${height * .08}" width="${width * .26}" height="${height * .84}" rx="3" fill="#f6f4ef" stroke="${stroke}" stroke-width="3"/>
        <path d="M${width * .44} ${height * .12}V${height * .88}" stroke="#d4d0c8" stroke-width="4"/>
      </svg>`;
    }

    const x = width * .12;
    const y = height * .12;
    const w = width * .76;
    const h = height * .76;
    const opening = state.openings[module.id];
    const split = upper ? 2 : lower ? 3 : 2;
    const parts = Array.from({ length: split }, (_, index) => {
      const partW = w / split;
      const px = x + partW * index;
      return `<rect x="${px}" y="${y}" width="${partW}" height="${h}" fill="${color}" stroke="#121314" stroke-width="2"/>`;
    }).join("");
    const handle = opening === "two-hole-handle"
      ? `<path d="M${x + w * .42} ${y + h * .78}H${x + w * .58}" stroke="#c9b184" stroke-width="${detail ? 8 : 3}" stroke-linecap="round"/>`
      : opening === "one-hole-point"
        ? `<circle cx="${x + w * .5}" cy="${y + h * .8}" r="${detail ? 7 : 3}" fill="#c9b184"/>`
        : `<path d="M${x + w * .2} ${y + h * .93}H${x + w * .8}" stroke="#eeeae2" stroke-width="${detail ? 11 : 5}"/>`;

    return `<svg viewBox="0 0 ${width} ${height}" aria-hidden="true">
      <defs><linearGradient id="box-${module.id}-${detail}" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#fff"/><stop offset="1" stop-color="#d9d6cf"/></linearGradient></defs>
      <rect width="${width}" height="${height}" fill="#eeeae2"/>
      <rect x="${x - width * .035}" y="${y - height * .035}" width="${w + width * .07}" height="${h + height * .07}" rx="4" fill="url(#box-${module.id}-${detail})" stroke="${stroke}" stroke-width="3"/>
      ${parts}${handle}
    </svg>`;
  }

  function renderModuleList(currentIssues) {
    const issueByModule = new Map(currentIssues.filter(issue => issue.moduleId).map(issue => [issue.moduleId, issue]));
    if (currentIssues.some(issue => issue.id === "lighting-requires-refrigerator-side-panel")) {
      issueByModule.set("lighting", currentIssues[0]);
    }

    elements.moduleList.replaceChildren();
    for (const module of orderedModules) {
      const fragment = elements.rowTemplate.content.cloneNode(true);
      const row = fragment.querySelector(".module-row");
      const checkbox = fragment.querySelector("input");
      const openButton = fragment.querySelector(".module-open");
      const thumb = fragment.querySelector(".module-thumb");
      const badge = fragment.querySelector(".module-badge");
      const enabled = isEnabled(module.id);
      const moduleIssue = issueByModule.get(module.id);

      row.dataset.moduleId = module.id;
      row.classList.toggle("is-enabled", enabled);
      row.classList.toggle("has-issue", Boolean(moduleIssue));
      checkbox.checked = enabled;
      checkbox.setAttribute("aria-label", `${enabled ? "Remover" : "Incluir"} ${module.name}`);
      checkbox.addEventListener("change", () => setEnabled(module.id, checkbox.checked));
      openButton.setAttribute("aria-label", `Detalhar ${module.name}`);
      openButton.addEventListener("click", () => selectModule(module.id));
      thumb.innerHTML = moduleSvg(module);
      fragment.querySelector(".module-number").textContent = `ITEM ${module.catalogNumber}`;
      fragment.querySelector(".module-name").textContent = module.name;
      fragment.querySelector(".module-status").textContent = enabled ? "Incluído na composição" : "Disponível";
      if (moduleIssue) {
        badge.hidden = false;
        badge.title = moduleIssue.message;
      }
      elements.moduleList.append(fragment);
    }
    elements.selectionCount.textContent = `${state.enabled.length}/8`;
  }

  function renderScene() {
    elements.sceneModules.replaceChildren();
    elements.sceneHitAreas.replaceChildren();
    const ns = "http://www.w3.org/2000/svg";
    const color = selectedColor().value;

    for (const module of orderedModules) {
      const placement = placementById.get(module.id);
      if (!placement) continue;
      const { x, y, width, height } = placement.sceneRect;
      const enabled = isEnabled(module.id);
      const selected = state.selectedId === module.id;
      const lastEnabled = state.lastEnabledId === module.id && enabled;

      const group = document.createElementNS(ns, "g");
      group.classList.add("scene-module");
      group.classList.toggle("is-enabled", enabled);
      group.classList.toggle("is-selected", selected);
      group.dataset.moduleId = module.id;
      group.style.zIndex = String(placement.zIndex);

      if (module.placementClass === "feature") {
        const glow = document.createElementNS(ns, "rect");
        glow.setAttribute("x", String(x));
        glow.setAttribute("y", String(y));
        glow.setAttribute("width", String(width));
        glow.setAttribute("height", String(height));
        glow.setAttribute("rx", "12");
        glow.setAttribute("fill", "#ffd766");
        glow.setAttribute("opacity", ".76");
        group.append(glow);
      } else {
        const box = document.createElementNS(ns, "rect");
        box.setAttribute("x", String(x));
        box.setAttribute("y", String(y));
        box.setAttribute("width", String(width));
        box.setAttribute("height", String(height));
        box.setAttribute("rx", "4");
        box.setAttribute("fill", module.frontColor.presetControlled ? color : "#f3f1ec");
        box.setAttribute("stroke", "#1f2022");
        box.setAttribute("stroke-width", "3");
        group.append(box);

        if (module.frontColor.presetControlled) {
          const splitCount = module.placementClass === "lower" ? 3 : 2;
          for (let index = 1; index < splitCount; index += 1) {
            const line = document.createElementNS(ns, "line");
            line.setAttribute("x1", String(x + width * index / splitCount));
            line.setAttribute("x2", String(x + width * index / splitCount));
            line.setAttribute("y1", String(y));
            line.setAttribute("y2", String(y + height));
            line.setAttribute("stroke", "#111214");
            line.setAttribute("stroke-width", "2");
            group.append(line);
          }
        }
      }
      elements.sceneModules.append(group);

      const hit = document.createElementNS(ns, "rect");
      hit.classList.add("scene-hit");
      hit.classList.toggle("is-enabled", enabled);
      hit.classList.toggle("is-selected", selected);
      hit.classList.toggle("is-last-enabled", lastEnabled);
      hit.dataset.moduleId = module.id;
      hit.setAttribute("x", String(x));
      hit.setAttribute("y", String(y));
      hit.setAttribute("width", String(width));
      hit.setAttribute("height", String(height));
      hit.setAttribute("rx", "5");
      hit.setAttribute("tabindex", enabled ? "0" : "-1");
      hit.setAttribute("aria-label", module.name);
      hit.addEventListener("click", () => selectModule(module.id));
      hit.addEventListener("keydown", event => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          selectModule(module.id);
        }
      });
      elements.sceneHitAreas.append(hit);
    }

    elements.sceneEmpty.classList.toggle("is-hidden", state.enabled.length > 0);
  }

  function dimensionsText(module) {
    const selected = module.dimensionsMm || module.measurementCandidates?.[0];
    if (!selected) return "Dimensões ainda não confirmadas.";
    const values = [selected.width, selected.height, selected.depth].filter(Number.isFinite);
    return values.length === 3 ? `${values[0]} × ${values[1]} × ${values[2]} mm` : "Dimensões parciais.";
  }

  function renderDetail() {
    const module = moduleById.get(state.selectedId);
    if (!module) {
      elements.catalogList.hidden = false;
      elements.catalogDetail.hidden = true;
      elements.moduleDetail.replaceChildren();
      return;
    }

    const materials = module.detail.materials?.length
      ? module.detail.materials.map(item => `<li>${item.label}: ${item.value || "não informado"}</li>`).join("")
      : "<li>Materiais ainda não consolidados.</li>";
    const hardware = module.detail.hardware?.length
      ? module.detail.hardware.map(item => `<li>${item.label}</li>`).join("")
      : "<li>Ferragens ainda não consolidadas.</li>";
    const notes = module.detail.notes?.length
      ? module.detail.notes.map(note => `<li>${note}</li>`).join("")
      : "<li>Sem observações adicionais registradas.</li>";

    elements.moduleDetail.innerHTML = `
      <p class="eyebrow">ITEM ${module.catalogNumber}</p>
      <h2>${module.name}</h2>
      <div class="detail-hero">${moduleSvg(module, { detail: true })}</div>
      <div class="detail-meta">
        <section class="detail-block">
          <h3>Dimensões</h3>
          <p class="field-note">${dimensionsText(module)}</p>
        </section>
        <section class="detail-block"><h3>Materiais</h3><ul class="detail-list">${materials}</ul></section>
        <section class="detail-block"><h3>Ferragens</h3><ul class="detail-list">${hardware}</ul></section>
        <section class="detail-block"><h3>Observações</h3><ul class="detail-list">${notes}</ul></section>
      </div>`;
  }

  function renderColors() {
    elements.colorOptions.replaceChildren();
    for (const color of COLORS) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "swatch";
      button.classList.toggle("is-active", color.id === state.colorId);
      button.style.setProperty("--swatch", color.value);
      button.title = color.name;
      button.setAttribute("aria-label", `Cor ${color.name}`);
      button.setAttribute("aria-pressed", String(color.id === state.colorId));
      button.addEventListener("click", () => {
        state.colorId = color.id;
        transientMessage = `Frentes alteradas para ${color.name}.`;
        commit();
      });
      elements.colorOptions.append(button);
    }
  }

  function renderSelectedConfig() {
    const module = moduleById.get(state.selectedId);
    const configurable = Boolean(module?.openingOptions.length);
    elements.selectedModuleConfig.disabled = !configurable;
    elements.selectedModuleName.textContent = module ? module.name : "Selecione um módulo";
    elements.openingSelect.replaceChildren();

    if (!configurable) {
      elements.openingRecommendation.textContent = module ? "Este item não possui abertura configurável." : "";
      return;
    }

    for (const option of module.openingOptions) {
      const element = document.createElement("option");
      element.value = option;
      element.textContent = OPENING_LABELS[option] || option;
      element.selected = state.openings[module.id] === option;
      elements.openingSelect.append(element);
    }
    elements.openingRecommendation.textContent = `Recomendado: ${module.recommendedOpeningOptions.map(option => OPENING_LABELS[option]).join(" ou ")}.`;
  }

  function renderIssues(currentIssues) {
    elements.issuesList.replaceChildren();
    for (const issue of currentIssues) {
      const card = document.createElement("article");
      card.className = `issue-card ${issue.severity}`;
      const label = document.createElement("strong");
      label.textContent = issue.severity === "blocking" ? "Ação necessária" : "Recomendação";
      const message = document.createElement("span");
      message.textContent = issue.message;
      const action = document.createElement("button");
      action.type = "button";
      action.textContent = issue.resolutionLabel;
      action.addEventListener("click", issue.resolve);
      card.append(label, message, action);
      elements.issuesList.append(card);
    }

    const blocking = currentIssues.filter(issue => issue.severity === "blocking");
    elements.diagnosticsSummary.classList.toggle("has-blocking", blocking.length > 0);
    elements.diagnosticsSummary.textContent = transientMessage || (
      blocking.length
        ? `${blocking.length} bloqueio impede a revisão.`
        : currentIssues.length
          ? `${currentIssues.length} recomendação disponível.`
          : state.enabled.length
            ? "Composição pronta para revisão."
            : "Nenhum módulo incluído."
    );
    elements.finalizeButton.disabled = blocking.length > 0 || state.enabled.length === 0;
  }

  function renderCommercial(currentIssues) {
    elements.commercialCount.textContent = String(state.enabled.length);
    const modified = orderedModules.filter(module => {
      if (!isEnabled(module.id) || !module.openingOptions.length) return false;
      return !module.recommendedOpeningOptions.includes(state.openings[module.id]);
    }).length;
    elements.modifierCount.textContent = modified
      ? `${modified} override${modified === 1 ? "" : "s"} de abertura`
      : "Nenhum override de abertura";
    renderIssues(currentIssues);
  }

  function renderBaseMode() {
    elements.sceneWrap.dataset.baseMode = state.baseMode;
    document.querySelectorAll("[data-base-mode]").forEach(button => {
      if (!(button instanceof HTMLButtonElement)) return;
      const active = button.dataset.baseMode === state.baseMode;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", String(active));
    });
    document.querySelector(".reference-context").src = assets.referenceComposition;
    elements.projectImage.src = assets.projectImage;
  }

  function render() {
    const currentIssues = issues();
    renderModuleList(currentIssues);
    renderScene();
    renderDetail();
    renderColors();
    renderSelectedConfig();
    renderCommercial(currentIssues);
    renderBaseMode();
  }

  function commit() {
    saveState();
    render();
  }

  elements.backToList.addEventListener("click", () => {
    elements.catalogList.hidden = false;
    elements.catalogDetail.hidden = true;
    transientMessage = "";
    render();
  });

  elements.openingSelect.addEventListener("change", () => {
    if (!state.selectedId) return;
    state.openings[state.selectedId] = elements.openingSelect.value;
    transientMessage = "Abertura atualizada; o cliente pode manter o override.";
    commit();
  });

  elements.applyRecommended.addEventListener("click", () => {
    for (const module of orderedModules) {
      if (module.openingOptions.length) state.openings[module.id] = recommendedOpening(module);
    }
    transientMessage = "Preset recomendado aplicado.";
    commit();
  });

  elements.enableAll.addEventListener("click", () => {
    state.enabled = orderedModules.map(module => module.id);
    state.lastEnabledId = orderedModules.at(-1)?.id ?? null;
    transientMessage = "Conjunto completo ativado.";
    commit();
  });

  elements.resetAll.addEventListener("click", () => {
    state = defaultState();
    elements.catalogList.hidden = false;
    elements.catalogDetail.hidden = true;
    transientMessage = "Seleção limpa.";
    commit();
  });

  elements.finalizeButton.addEventListener("click", () => {
    const blocking = issues().filter(issue => issue.severity === "blocking");
    if (blocking.length || !state.enabled.length) return;
    transientMessage = `Revisão liberada para ${state.enabled.length} módulo${state.enabled.length === 1 ? "" : "s"}.`;
    render();
  });

  document.querySelectorAll("[data-base-mode]").forEach(button => {
    button.addEventListener("click", () => {
      state.baseMode = button.dataset.baseMode;
      transientMessage = state.baseMode === "reference-context"
        ? "Contexto de referência ativado."
        : "Parede neutra ativada.";
      commit();
    });
  });

  render();
})();
