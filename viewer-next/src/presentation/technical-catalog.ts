import {
  STONE02_ID,
  STONE03_ID,
  UNDER_CAB_LIGHT_ITEM_ID,
  module01,
  module02,
  module03WithSink,
  module04,
  module05,
  module06,
  module07
} from "@mobilipresenter/scene-core";
import { STONE_PRESET_IDS } from "../fixtures/stone-presets.js";
import { FRONT_PRESET_IDS } from "../runtime/presets.js";
import {
  TECHNICAL_CATALOG_ENTRY_SCHEMA_VERSION,
  type TechnicalCatalogEntry,
  type TechnicalSourceRef
} from "./contracts.js";

const sheet = (reference: string): TechnicalSourceRef => ({
  authority: "technical-catalog",
  reference,
  status: "provided"
});

const core = (reference: string): TechnicalSourceRef => ({
  authority: "scene-core",
  reference,
  status: "confirmed"
});

const runtime = (reference: string): TechnicalSourceRef => ({
  authority: "viewer-runtime",
  reference,
  status: "confirmed"
});

const appearance = (reference: string): TechnicalSourceRef => ({
  authority: "appearance-catalog",
  reference,
  status: "confirmed"
});

const MODULE01_SHEET = "technical-sheet:module-01:user-provided-2026-08-31";
const MODULE02_SHEET = "technical-sheet:module-02:user-provided-2026-08-10";
const MODULE03_SHEET = "technical-sheet:module-03:user-provided-2026-08-10";
const MODULE04_SHEET = "technical-sheet:module-04:user-provided-2026-08-10";
const MODULE05_SHEET = "technical-sheet:module-05:user-provided-2026-08-31";
const MODULE06_SHEET = "technical-sheet:module-06:user-provided-2026-08-31";
const MODULE07_SHEET = "technical-sheet:module-07:user-provided-2026-08-31";
const LIGHT08_RULE = "user-rule:lighting-08-depends-on-modules-04-and-06:2026-08-10";

const OVEN_ID = "scene/traditional/appliance/oven";
const COOKTOP_ID = "scene/traditional/appliance/cooktop";
const STOVE_PLINTH_ID = "scene/traditional/accessory/stove-plinth";
const KITCHEN_SINK_ID = "scene/traditional/fixture/kitchen-sink";
const SINK_PLINTH_ID = "scene/traditional/accessory/sink-plinth";
const HOOD_ID = "scene/traditional/appliance/hood";
const MICROWAVE_ID = "scene/traditional/appliance/microwave";
const FRIDGE_ID = "scene/traditional/appliance/fridge";

const moduleDimensions = {
  order: ["width", "height", "depth"] as const,
  labels: { width: "L", height: "A", depth: "P" },
  prefer: "nominal" as const
};

const moduleControl = [
  { kind: "visibility" as const, label: "Exibir módulo", binding: "viewer-visibility" as const, implementationStatus: "bound" as const }
];

function frontFinish(id: string, entityId: string, label = "Frente") {
  return {
    id,
    label,
    targetEntityId: entityId,
    materialSlot: "front",
    optionFamily: "front-preset" as const,
    allowedOptionIds: FRONT_PRESET_IDS
  };
}

function standardViews(alias: string) {
  return [
    {
      id: `module${alias}/view/front`,
      label: "Vista frontal",
      kind: "orthographic" as const,
      plane: "width-height" as const,
      dimensionAxes: ["width", "height"] as const,
      source: "scene-geometry" as const
    },
    {
      id: `module${alias}/view/side`,
      label: "Vista lateral",
      kind: "orthographic" as const,
      plane: "depth-height" as const,
      dimensionAxes: ["depth", "height"] as const,
      source: "scene-envelope" as const
    },
    {
      id: `module${alias}/view/isometric`,
      label: "Vista isométrica",
      kind: "isometric" as const,
      source: "scene-envelope" as const
    }
  ];
}

export const module01TechnicalCatalog: TechnicalCatalogEntry = {
  schemaVersion: TECHNICAL_CATALOG_ENTRY_SCHEMA_VERSION,
  id: "technical/module-01",
  target: { kind: "module", entityId: module01.id },
  identity: { alias: "01", title: "Aéreo da lavanderia", category: "módulo aéreo", shortLabel: "Lavanderia" },
  dimensions: moduleDimensions,
  presentation: { primaryEntityId: module01.id, companionEntityIds: [] },
  specifications: [
    { id: "module01/hardware/hinges", category: "hardware", text: "Dobradiças com amortecimento.", semanticKey: "hardware.hinge", source: sheet(MODULE01_SHEET) },
    { id: "module01/construction/shelf", category: "construction", text: "1 prateleira fixa.", source: core("scene-core:module01:shelf") },
    { id: "module01/construction/mdf-18", category: "construction", text: "Estrutura em MDF 18 mm.", source: sheet(MODULE01_SHEET) },
    { id: "module01/construction/back-6", category: "construction", text: "Fundo de 6 mm duplamente melamínico.", source: sheet(MODULE01_SHEET) },
    { id: "module01/construction/carcass", category: "construction", text: "Corpo (caixaria) em Branco TX.", source: sheet(MODULE01_SHEET) }
  ],
  components: [
    { id: "module01/component/damped-hinge", kind: "hardware", label: "Dobradiça com amortecimento", semanticKey: "hardware.hinge", source: sheet(MODULE01_SHEET) },
    { id: "module01/component/fixed-shelf", kind: "panel", label: "Prateleira fixa", quantity: 1, unit: "unidade", source: core("scene-core:module01:shelf") }
  ],
  notices: [],
  dependencies: [],
  controls: moduleControl,
  finishes: [frontFinish("module01/finish/front", module01.id, "Frentes")],
  technicalViews: standardViews("01"),
  sourceRefs: [sheet(MODULE01_SHEET), core("scene-core:module01"), runtime("viewer-runtime:visibility/front"), appearance("appearance-catalog:front-presets")]
};

export const module02TechnicalCatalog: TechnicalCatalogEntry = {
  schemaVersion: TECHNICAL_CATALOG_ENTRY_SCHEMA_VERSION,
  id: "technical/module-02",
  target: { kind: "module", entityId: module02.id },
  identity: { alias: "02", title: "Inferior do fogão", category: "módulo inferior" },
  dimensions: moduleDimensions,
  presentation: {
    primaryEntityId: module02.id,
    companionEntityIds: [OVEN_ID, COOKTOP_ID, STONE02_ID, STOVE_PLINTH_ID]
  },
  specifications: [
    {
      id: "module02/function/oven-space",
      category: "function",
      text: "Módulo inferior do fogão com espaço para instalação de forno embutido.",
      source: sheet(MODULE02_SHEET)
    },
    {
      id: "module02/electrical/preparation",
      category: "electrical",
      text: "Espera elétrica preparada com cabo especial PP 4 mm e 2 tomadas de 20 A para ligação do fogão e do forno.",
      semanticKey: "electrical.outlet",
      source: sheet(MODULE02_SHEET)
    }
  ],
  components: [
    {
      id: "module02/component/pp-cable",
      kind: "electrical",
      label: "Cabo especial PP",
      specification: "4 mm",
      semanticKey: "electrical.cable",
      source: sheet(MODULE02_SHEET)
    },
    {
      id: "module02/component/outlet-20a",
      kind: "electrical",
      label: "Tomada 20 A",
      quantity: 2,
      unit: "unidade",
      linkedEntityId: OVEN_ID,
      semanticKey: "electrical.outlet",
      source: sheet(MODULE02_SHEET)
    }
  ],
  notices: [
    {
      id: "module02/notice/electrical-wait",
      severity: "important",
      title: "Espera elétrica",
      text: "Prever pontos para alimentação do fogão e do forno conforme a especificação técnica.",
      source: sheet(MODULE02_SHEET)
    }
  ],
  dependencies: [],
  controls: moduleControl,
  finishes: [
    frontFinish("module02/finish/front", module02.id),
    {
      id: "module02/finish/stone",
      label: "Pedra",
      targetEntityId: STONE02_ID,
      materialSlot: "stone",
      optionFamily: "stone-preset",
      allowedOptionIds: STONE_PRESET_IDS
    }
  ],
  technicalViews: standardViews("02"),
  sourceRefs: [sheet(MODULE02_SHEET), core("scene-core:module02"), runtime("viewer-runtime:visibility/front/stone"), appearance("appearance-catalog:front+stone-presets")]
};

export const module03TechnicalCatalog: TechnicalCatalogEntry = {
  schemaVersion: TECHNICAL_CATALOG_ENTRY_SCHEMA_VERSION,
  id: "technical/module-03",
  target: { kind: "module", entityId: module03WithSink.id },
  identity: { alias: "03", title: "Inferior da pia", category: "módulo inferior" },
  dimensions: moduleDimensions,
  presentation: {
    primaryEntityId: module03WithSink.id,
    companionEntityIds: [KITCHEN_SINK_ID, STONE03_ID, SINK_PLINTH_ID]
  },
  specifications: [
    { id: "module03/hardware/drawer-runners", category: "hardware", text: "Corrediças telescópicas reforçadas H45 nas 4 gavetas.", semanticKey: "hardware.drawer-runner", source: sheet(MODULE03_SHEET) },
    { id: "module03/hardware/hinges", category: "hardware", text: "Dobradiças com amortecimento.", semanticKey: "hardware.hinge", source: sheet(MODULE03_SHEET) },
    { id: "module03/construction/mdf-18", category: "construction", text: "Estrutura em MDF 18 mm.", source: sheet(MODULE03_SHEET) },
    { id: "module03/construction/back-6", category: "construction", text: "Fundo de 6 mm duplamente melamínico.", source: sheet(MODULE03_SHEET) },
    { id: "module03/finish/edge-band", category: "finish", text: "Fita de borda na cor da frente.", source: sheet(MODULE03_SHEET) }
  ],
  components: [
    { id: "module03/component/runner-h45", kind: "hardware", label: "Corrediça telescópica reforçada H45", quantity: 4, unit: "gaveta atendida", semanticKey: "hardware.drawer-runner", source: sheet(MODULE03_SHEET) },
    { id: "module03/component/damped-hinge", kind: "hardware", label: "Dobradiça com amortecimento", semanticKey: "hardware.hinge", source: sheet(MODULE03_SHEET) }
  ],
  notices: [],
  dependencies: [],
  controls: moduleControl,
  finishes: [
    frontFinish("module03/finish/front", module03WithSink.id, "Frentes"),
    {
      id: "module03/finish/stone",
      label: "Pedra",
      targetEntityId: STONE03_ID,
      materialSlot: "stone",
      optionFamily: "stone-preset",
      allowedOptionIds: STONE_PRESET_IDS
    }
  ],
  technicalViews: [
    standardViews("03")[0]!,
    standardViews("03")[1]!,
    {
      id: "module03/view/internal-front",
      label: "Vista interna (frente)",
      kind: "internal",
      plane: "width-height",
      dimensionAxes: ["width", "height"],
      source: "authored-internal-layout",
      internalLayout: {
        axis: "width",
        segments: [
          { label: "gavetas", spanMm: 390 },
          { label: "porta central", spanMm: 400 },
          { label: "porta direita", spanMm: 400 }
        ],
        subdivisions: [{ segmentIndex: 0, count: 4, label: "4 gavetas" }],
        source: sheet(MODULE03_SHEET)
      }
    },
    standardViews("03")[2]!
  ],
  sourceRefs: [sheet(MODULE03_SHEET), core("scene-core:module03"), runtime("viewer-runtime:visibility/front/stone"), appearance("appearance-catalog:front+stone-presets")]
};

export const module04TechnicalCatalog: TechnicalCatalogEntry = {
  schemaVersion: TECHNICAL_CATALOG_ENTRY_SCHEMA_VERSION,
  id: "technical/module-04",
  target: { kind: "module", entityId: module04.id },
  identity: { alias: "04", title: "Lateral da geladeira", category: "lateral técnica" },
  dimensions: {
    order: ["height", "depth", "width"],
    labels: { height: "A", depth: "P", width: "E" },
    prefer: "nominal"
  },
  presentation: { primaryEntityId: module04.id, companionEntityIds: [FRIDGE_ID] },
  specifications: [
    { id: "module04/function/support-upper-fridge", category: "function", text: "Dar sustentação para o aéreo da geladeira.", source: sheet(MODULE04_SHEET) },
    { id: "module04/function/front-alignment", category: "function", text: "Trazer o aéreo da geladeira para a frente para alinhamento frontal.", source: sheet(MODULE04_SHEET) },
    { id: "module04/function/light-finish", category: "function", text: "Dar acabamento na fiação da iluminação do aéreo da pia.", source: sheet(MODULE04_SHEET) },
    { id: "module04/function/switch-point", category: "installation", text: "Local para fixação do interruptor de acendimento da iluminação.", semanticKey: "electrical.switch", source: sheet(MODULE04_SHEET) },
    { id: "module04/construction/mdf-18", category: "construction", text: "Estrutura em MDF 18 mm.", source: sheet(MODULE04_SHEET) },
    { id: "module04/finish/edge-band", category: "finish", text: "Fita de borda na cor da peça.", source: sheet(MODULE04_SHEET) }
  ],
  components: [
    { id: "module04/interface/light-switch-fixing", kind: "interface", label: "Ponto de fixação do interruptor de iluminação", semanticKey: "electrical.switch", source: sheet(MODULE04_SHEET) }
  ],
  notices: [
    { id: "module04/notice/switch-client", severity: "important", title: "Importante", text: "Fixação do interruptor a critério do cliente.", source: sheet(MODULE04_SHEET) }
  ],
  dependencies: [],
  controls: moduleControl,
  finishes: [frontFinish("module04/finish/panel", module04.id, "Acabamento da lateral")],
  technicalViews: [
    { id: "module04/view/isometric", label: "Vista isométrica", kind: "isometric", source: "scene-envelope" },
    { id: "module04/view/front", label: "Vista frontal", kind: "orthographic", plane: "depth-height", dimensionAxes: ["depth", "height"], source: "scene-envelope" },
    { id: "module04/view/thickness", label: "Vista lateral (espessura)", kind: "orthographic", plane: "width-height", dimensionAxes: ["width", "height"], source: "scene-envelope" }
  ],
  sourceRefs: [sheet(MODULE04_SHEET), core("scene-core:module04"), runtime("viewer-runtime:visibility/front"), appearance("appearance-catalog:front-presets")]
};

export const module05TechnicalCatalog: TechnicalCatalogEntry = {
  schemaVersion: TECHNICAL_CATALOG_ENTRY_SCHEMA_VERSION,
  id: "technical/module-05",
  target: { kind: "module", entityId: module05.id },
  identity: { alias: "05", title: "Aéreo do fogão", category: "módulo aéreo" },
  dimensions: moduleDimensions,
  presentation: { primaryEntityId: module05.id, companionEntityIds: [HOOD_ID] },
  specifications: [
    { id: "module05/hardware/hinges", category: "hardware", text: "Dobradiças com amortecimento.", semanticKey: "hardware.hinge", source: sheet(MODULE05_SHEET) },
    { id: "module05/construction/shelf", category: "construction", text: "1 prateleira fixa.", source: sheet(MODULE05_SHEET) },
    { id: "module05/construction/mdf-18", category: "construction", text: "Estrutura em MDF 18 mm.", source: sheet(MODULE05_SHEET) },
    { id: "module05/construction/back-6", category: "construction", text: "Fundo de 6 mm duplamente melamínico.", source: sheet(MODULE05_SHEET) },
    { id: "module05/construction/carcass", category: "construction", text: "Corpo (caixaria) em Branco TX.", source: sheet(MODULE05_SHEET) },
    { id: "module05/finish/edge-band", category: "finish", text: "Fita de borda na cor da frente.", source: sheet(MODULE05_SHEET) }
  ],
  components: [
    { id: "module05/component/damped-hinge", kind: "hardware", label: "Dobradiça com amortecimento", semanticKey: "hardware.hinge", source: sheet(MODULE05_SHEET) },
    { id: "module05/component/fixed-shelf", kind: "panel", label: "Prateleira fixa", quantity: 1, unit: "unidade", source: sheet(MODULE05_SHEET) }
  ],
  notices: [],
  dependencies: [],
  controls: moduleControl,
  finishes: [frontFinish("module05/finish/front", module05.id, "Frentes")],
  technicalViews: standardViews("05"),
  sourceRefs: [sheet(MODULE05_SHEET), core("scene-core:module05"), runtime("viewer-runtime:visibility/front"), appearance("appearance-catalog:front-presets")]
};

export const module06TechnicalCatalog: TechnicalCatalogEntry = {
  schemaVersion: TECHNICAL_CATALOG_ENTRY_SCHEMA_VERSION,
  id: "technical/module-06",
  target: { kind: "module", entityId: module06.id },
  identity: { alias: "06", title: "Aéreo da pia", category: "módulo aéreo com nicho" },
  dimensions: moduleDimensions,
  presentation: { primaryEntityId: module06.id, companionEntityIds: [MICROWAVE_ID, UNDER_CAB_LIGHT_ITEM_ID] },
  specifications: [
    { id: "module06/hardware/hinges", category: "hardware", text: "2 portas de abrir com dobradiças com amortecimento.", semanticKey: "hardware.hinge", source: sheet(MODULE06_SHEET) },
    { id: "module06/hardware/lift", category: "hardware", text: "1 porta basculante com pistão.", semanticKey: "hardware.lift-piston", source: sheet(MODULE06_SHEET) },
    { id: "module06/function/microwave", category: "function", text: "Nicho para forno micro-ondas.", source: sheet(MODULE06_SHEET) },
    { id: "module06/electrical/microwave-outlet", category: "electrical", text: "Espera de tomada para o forno micro-ondas.", semanticKey: "electrical.outlet", source: sheet(MODULE06_SHEET) },
    { id: "module06/construction/mdf-18", category: "construction", text: "Estrutura em MDF 18 mm.", source: sheet(MODULE06_SHEET) },
    { id: "module06/construction/back-6", category: "construction", text: "Fundo de 6 mm duplamente melamínico.", source: sheet(MODULE06_SHEET) },
    { id: "module06/construction/carcass", category: "construction", text: "Corpo (caixaria) em Branco TX.", source: sheet(MODULE06_SHEET) },
    { id: "module06/finish/edge-band", category: "finish", text: "Fita de borda na cor da frente.", source: sheet(MODULE06_SHEET) }
  ],
  components: [
    { id: "module06/component/damped-hinge", kind: "hardware", label: "Dobradiça com amortecimento", semanticKey: "hardware.hinge", source: sheet(MODULE06_SHEET) },
    { id: "module06/component/lift-piston", kind: "hardware", label: "Pistão da porta basculante", quantity: 1, unit: "conjunto", semanticKey: "hardware.lift-piston", source: sheet(MODULE06_SHEET) },
    { id: "module06/component/microwave-outlet", kind: "electrical", label: "Espera de tomada para micro-ondas", linkedEntityId: MICROWAVE_ID, semanticKey: "electrical.outlet", source: sheet(MODULE06_SHEET) }
  ],
  notices: [],
  dependencies: [],
  controls: moduleControl,
  finishes: [frontFinish("module06/finish/front", module06.id, "Frentes")],
  technicalViews: standardViews("06"),
  sourceRefs: [sheet(MODULE06_SHEET), core("scene-core:module06"), runtime("viewer-runtime:visibility/front"), appearance("appearance-catalog:front-presets")]
};

export const module07TechnicalCatalog: TechnicalCatalogEntry = {
  schemaVersion: TECHNICAL_CATALOG_ENTRY_SCHEMA_VERSION,
  id: "technical/module-07",
  target: { kind: "module", entityId: module07.id },
  identity: { alias: "07", title: "Aéreo da geladeira", category: "módulo aéreo" },
  dimensions: moduleDimensions,
  presentation: { primaryEntityId: module07.id, companionEntityIds: [FRIDGE_ID] },
  specifications: [
    { id: "module07/hardware/hinges", category: "hardware", text: "Dobradiças com amortecimento.", semanticKey: "hardware.hinge", source: sheet(MODULE07_SHEET) },
    { id: "module07/construction/shelf", category: "construction", text: "1 prateleira fixa.", source: sheet(MODULE07_SHEET) },
    { id: "module07/construction/mdf-18", category: "construction", text: "Estrutura em MDF 18 mm.", source: sheet(MODULE07_SHEET) },
    { id: "module07/construction/back-6", category: "construction", text: "Fundo de 6 mm duplamente melamínico.", source: sheet(MODULE07_SHEET) },
    { id: "module07/construction/carcass", category: "construction", text: "Corpo (caixaria) em Branco TX.", source: sheet(MODULE07_SHEET) },
    { id: "module07/finish/edge-band", category: "finish", text: "Fita de borda na cor da frente.", source: sheet(MODULE07_SHEET) }
  ],
  components: [
    { id: "module07/component/damped-hinge", kind: "hardware", label: "Dobradiça com amortecimento", semanticKey: "hardware.hinge", source: sheet(MODULE07_SHEET) },
    { id: "module07/component/fixed-shelf", kind: "panel", label: "Prateleira fixa", quantity: 1, unit: "unidade", source: sheet(MODULE07_SHEET) }
  ],
  notices: [],
  dependencies: [],
  controls: moduleControl,
  finishes: [frontFinish("module07/finish/front", module07.id, "Frentes")],
  technicalViews: standardViews("07"),
  sourceRefs: [sheet(MODULE07_SHEET), core("scene-core:module07"), runtime("viewer-runtime:visibility/front"), appearance("appearance-catalog:front-presets")]
};

export const lighting08TechnicalCatalog: TechnicalCatalogEntry = {
  schemaVersion: TECHNICAL_CATALOG_ENTRY_SCHEMA_VERSION,
  id: "technical/lighting-08",
  target: { kind: "item", entityId: UNDER_CAB_LIGHT_ITEM_ID },
  identity: { alias: "08", title: "Iluminação", category: "iluminação técnica", shortLabel: "LED bancada" },
  specifications: [
    { id: "lighting08/function/worktop", category: "function", text: "Iluminação sob o aéreo da pia em perfil traseiro de canto.", source: core("scene-core:currentUnderCabLightContract") }
  ],
  components: [],
  notices: [],
  dependencies: [
    { relation: "requires-present", targetEntityId: module06.id, label: "Aéreo da pia", source: sheet(LIGHT08_RULE) },
    { relation: "requires-present", targetEntityId: module04.id, label: "Lateral da geladeira / acabamento elétrico", source: sheet(LIGHT08_RULE) },
    { relation: "control-point-host", targetEntityId: module04.id, label: "Ponto de fixação do interruptor", source: sheet(MODULE04_SHEET) }
  ],
  controls: [
    { kind: "visibility", label: "Exibir perfil", binding: "viewer-visibility", implementationStatus: "declared-not-bound" },
    { kind: "activation", label: "Ligar iluminação", binding: "feature-enabled", implementationStatus: "declared-not-bound", defaultEnabled: true }
  ],
  finishes: [],
  technicalViews: [
    { id: "lighting08/view/profile", label: "Detalhe do perfil", kind: "detail", source: "external-contract" }
  ],
  sourceRefs: [sheet(LIGHT08_RULE), sheet(MODULE04_SHEET), core("scene-core:currentUnderCabLightContract"), core("scene-core:under-cab-host=module06")]
};

export const CURRENT_TECHNICAL_CATALOG: readonly TechnicalCatalogEntry[] = [
  module01TechnicalCatalog,
  module02TechnicalCatalog,
  module03TechnicalCatalog,
  module04TechnicalCatalog,
  module05TechnicalCatalog,
  module06TechnicalCatalog,
  module07TechnicalCatalog,
  lighting08TechnicalCatalog
];
