const MODULE_IDS = ["01","02","03","04","05","06","07","08"];

async function loadJson(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) throw new Error(`Falha ao carregar ${path}: ${response.status}`);
  return response.json();
}

export async function loadI2Data() {
  const calibrationPromise = window.MOBILI_I3_CALIBRATION
    ? Promise.resolve(window.MOBILI_I3_CALIBRATION)
    : loadJson("./i3-data/calibration.json");

  const [moduleDocs, assembly, rules, baseLayout, presets, references, calibration] = await Promise.all([
    Promise.all(MODULE_IDS.map(id => loadJson(`./i2-data/module-${id}.json`))),
    loadJson("./i2-data/assembly.json"),
    loadJson("./i2-data/rules.json"),
    loadJson("./i2-data/layout.json"),
    loadJson("./i2-data/presets.json"),
    loadJson("./i2-data/references.json"),
    calibrationPromise
  ]);

  const modules = moduleDocs.map(doc => doc.module);
  const moduleById = new Map(modules.map(module => [module.id, module]));
  const orderedModules = assembly.moduleOrder.map(id => moduleById.get(id)).filter(Boolean);
  if (orderedModules.length !== 8) throw new Error("Contrato incompleto: catálogo deve conter 8 módulos.");

  const calibrationIds = new Set(calibration.placements.map(item => item.moduleId));
  for (const module of orderedModules) {
    if (!calibrationIds.has(module.id)) {
      throw new Error(`Calibração I3 ausente para ${module.id}.`);
    }
  }

  const zIndexById = new Map(baseLayout.placements.map(item => [item.moduleId, item.zIndex]));
  const layout = {
    ...baseLayout,
    schemaVersion: "FixedViewLayout 0.2",
    status: calibration.status,
    calibrationId: calibration.id,
    placements: calibration.placements.map(item => ({
      moduleId: item.moduleId,
      sceneRect: item.rect,
      zIndex: zIndexById.get(item.moduleId) ?? 0,
      confidence: item.confidence,
      basis: item.basis,
      metricUseAllowed: false
    })),
    fallbacks: calibration.fallbacks.map(item => ({
      id: item.id,
      when: item.when,
      sceneRect: item.rect,
      confidence: item.confidence,
      basis: item.basis,
      metricUseAllowed: false
    }))
  };

  return {
    schemaVersion: "FixedViewRuntime 0.3",
    modules,
    moduleById,
    orderedModules,
    assembly,
    rules: rules.rules,
    layout,
    presets,
    references,
    calibration
  };
}
