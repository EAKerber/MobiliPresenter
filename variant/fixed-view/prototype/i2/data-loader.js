const MODULE_IDS = ["01","02","03","04","05","06","07","08"];

async function loadJson(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) throw new Error(`Falha ao carregar ${path}: ${response.status}`);
  return response.json();
}

export async function loadI2Data() {
  const [moduleDocs, assembly, rules, layout, presets, references] = await Promise.all([
    Promise.all(MODULE_IDS.map(id => loadJson(`./i2-data/module-${id}.json`))),
    loadJson("./i2-data/assembly.json"),
    loadJson("./i2-data/rules.json"),
    loadJson("./i2-data/layout.json"),
    loadJson("./i2-data/presets.json"),
    loadJson("./i2-data/references.json")
  ]);

  const modules = moduleDocs.map(doc => doc.module);
  const moduleById = new Map(modules.map(module => [module.id, module]));
  const orderedModules = assembly.moduleOrder.map(id => moduleById.get(id)).filter(Boolean);
  if (orderedModules.length !== 8) throw new Error("Contrato I2 incompleto: catálogo deve conter 8 módulos.");

  return {
    schemaVersion: "FixedViewRuntime 0.2",
    modules,
    moduleById,
    orderedModules,
    assembly,
    rules: rules.rules,
    layout,
    presets,
    references
  };
}
