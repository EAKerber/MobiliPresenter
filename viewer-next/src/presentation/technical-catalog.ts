import {
  STONE02_ID,
  STONE03_ID,
  UNDER_CAB_LIGHT_ITEM_ID,
  module02,
  module03WithSink,
  module04,
  module06
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

const MODULE02_SHEET = "technical-sheet:module-02:user-provided-2026-08-10";
const MODULE03_SHEET = "technical-sheet:module-03:user-provided-2026-08-10";
const MODULE04_SHEET = "technical-sheet:module-04:user-provided-2026-08-10";
const LIGHT08_RULE = "user-rule:lighting-08-depends-on-modules-04-and-06:2026-08-10";

export const module02TechnicalCatalog: TechnicalCatalogEntry = {
  schemaVersion: TECHNICAL_CATALOG_ENTRY_SCHEMA_VERSION,
  id: "technical/module-02",
  target: { kind: "module", entityId: module02.id },
  identity: { alias: "02", title: "Inferior do fogão", category: "módulo inferior" },
  dimensions: {
    order: ["width", "height", "depth"],
    labels: { width: "L", height: "A", depth: "P" },
    prefer: "nominal"
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
      source: sheet(MODULE02_SHEET)
    }
  ],
  components: [
    {
      id: "module02/component/pp-cable",
      kind: "electrical",
      label: "Cabo especial PP",
      specification: "4 mm",
      source: sheet(MODULE02_SHEET)
    },
    {
      id: "module02/component/outlet-20a",
      kind: "electrical",
      label: "Tomada 20 A",
      quantity: 2,
      unit: "unidade",
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
  controls: [
    { kind: "visibility", label: "Exibir módulo", binding: "viewer-visibility", implementationStatus: "bound" }
  ],
  finishes: [
    {
      id: "module02/finish/front",
      label: "Frente",
      targetEntityId: module02.id,
      materialSlot: "front",
      optionFamily: "front-preset",
      allowedOptionIds: FRONT_PRESET_IDS
    },
    {
      id: "module02/finish/stone",
      label: "Pedra",
      targetEntityId: STONE02_ID,
      materialSlot: "stone",
      optionFamily: "stone-preset",
      allowedOptionIds: STONE_PRESET_IDS
    }
  ],
  technicalViews: [
    {
      id: "module02/view/front",
      label: "Vista frontal",
      kind: "orthographic",
      plane: "width-height",
      dimensionAxes: ["width", "height"],
      source: "scene-geometry"
    },
    {
      id: "module02/view/side",
      label: "Vista lateral",
      kind: "orthographic",
      plane: "depth-height",
      dimensionAxes: ["depth", "height"],
      source: "scene-envelope"
    },
    { id: "module02/view/isometric", label: "Vista isométrica", kind: "isometric", source: "scene-envelope" }
  ],
  sourceRefs: [sheet(MODULE02_SHEET), core("scene-core:module02"), runtime("viewer-runtime:visibility/front/stone"), appearance("appearance-catalog:front+stone-presets")]
};

export const module03TechnicalCatalog: TechnicalCatalogEntry = {
  schemaVersion: TECHNICAL_CATALOG_ENTRY_SCHEMA_VERSION,
  id: "technical/module-03",
  target: { kind: "module", entityId: module03WithSink.id },
  identity: { alias: "03", title: "Inferior da pia", category: "módulo inferior" },
  dimensions: {
    order: ["width", "height", "depth"],
    labels: { width: "L", height: "A", depth: "P" },
    prefer: "nominal"
  },
  specifications: [
    {
      id: "module03/hardware/drawer-runners",
      category: "hardware",
      text: "Corrediças telescópicas reforçadas H45 nas 4 gavetas.",
      source: sheet(MODULE03_SHEET)
    },
    {
      id: "module03/hardware/hinges",
      category: "hardware",
      text: "Dobradiças com amortecimento.",
      source: sheet(MODULE03_SHEET)
    },
    {
      id: "module03/construction/mdf-18",
      category: "construction",
      text: "Estrutura em MDF 18 mm.",
      source: sheet(MODULE03_SHEET)
    },
    {
      id: "module03/construction/back-6",
      category: "construction",
      text: "Fundo de 6 mm duplamente melamínico.",
      source: sheet(MODULE03_SHEET)
    },
    {
      id: "module03/finish/edge-band",
      category: "finish",
      text: "Fita de borda na cor da frente.",
      source: sheet(MODULE03_SHEET)
    }
  ],
  components: [
    {
      id: "module03/component/runner-h45",
      kind: "hardware",
      label: "Corrediça telescópica reforçada H45",
      quantity: 4,
      unit: "gaveta atendida",
      source: sheet(MODULE03_SHEET)
    },
    {
      id: "module03/component/damped-hinge",
      kind: "hardware",
      label: "Dobradiça com amortecimento",
      source: sheet(MODULE03_SHEET)
    }
  ],
  notices: [],
  dependencies: [],
  controls: [
    { kind: "visibility", label: "Exibir módulo", binding: "viewer-visibility", implementationStatus: "bound" }
  ],
  finishes: [
    {
      id: "module03/finish/front",
      label: "Frentes",
      targetEntityId: module03WithSink.id,
      materialSlot: "front",
      optionFamily: "front-preset",
      allowedOptionIds: FRONT_PRESET_IDS
    },
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
    {
      id: "module03/view/front",
      label: "Vista frontal",
      kind: "orthographic",
      plane: "width-height",
      dimensionAxes: ["width", "height"],
      source: "scene-geometry"
    },
    {
      id: "module03/view/side",
      label: "Vista lateral",
      kind: "orthographic",
      plane: "depth-height",
      dimensionAxes: ["depth", "height"],
      source: "scene-envelope"
    },
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
    { id: "module03/view/isometric", label: "Vista isométrica", kind: "isometric", source: "scene-envelope" }
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
  specifications: [
    {
      id: "module04/function/support-upper-fridge",
      category: "function",
      text: "Dar sustentação para o aéreo da geladeira.",
      source: sheet(MODULE04_SHEET)
    },
    {
      id: "module04/function/front-alignment",
      category: "function",
      text: "Trazer o aéreo da geladeira para a frente para alinhamento frontal.",
      source: sheet(MODULE04_SHEET)
    },
    {
      id: "module04/function/light-finish",
      category: "function",
      text: "Dar acabamento na fiação da iluminação do aéreo da pia.",
      source: sheet(MODULE04_SHEET)
    },
    {
      id: "module04/function/switch-point",
      category: "installation",
      text: "Local para fixação do interruptor de acendimento da iluminação.",
      source: sheet(MODULE04_SHEET)
    },
    {
      id: "module04/construction/mdf-18",
      category: "construction",
      text: "Estrutura em MDF 18 mm.",
      source: sheet(MODULE04_SHEET)
    },
    {
      id: "module04/finish/edge-band",
      category: "finish",
      text: "Fita de borda na cor da peça.",
      source: sheet(MODULE04_SHEET)
    }
  ],
  components: [
    {
      id: "module04/interface/light-switch-fixing",
      kind: "interface",
      label: "Ponto de fixação do interruptor de iluminação",
      source: sheet(MODULE04_SHEET)
    }
  ],
  notices: [
    {
      id: "module04/notice/switch-client",
      severity: "important",
      title: "Importante",
      text: "Fixação do interruptor a critério do cliente.",
      source: sheet(MODULE04_SHEET)
    }
  ],
  dependencies: [],
  controls: [
    { kind: "visibility", label: "Exibir módulo", binding: "viewer-visibility", implementationStatus: "bound" }
  ],
  finishes: [
    {
      id: "module04/finish/panel",
      label: "Acabamento da lateral",
      targetEntityId: module04.id,
      materialSlot: "front",
      optionFamily: "front-preset",
      allowedOptionIds: FRONT_PRESET_IDS
    }
  ],
  technicalViews: [
    { id: "module04/view/isometric", label: "Vista isométrica", kind: "isometric", source: "scene-envelope" },
    {
      id: "module04/view/front",
      label: "Vista frontal",
      kind: "orthographic",
      plane: "depth-height",
      dimensionAxes: ["depth", "height"],
      source: "scene-envelope"
    },
    {
      id: "module04/view/thickness",
      label: "Vista lateral (espessura)",
      kind: "orthographic",
      plane: "width-height",
      dimensionAxes: ["width", "height"],
      source: "scene-envelope"
    }
  ],
  sourceRefs: [sheet(MODULE04_SHEET), core("scene-core:module04"), runtime("viewer-runtime:visibility/front"), appearance("appearance-catalog:front-presets")]
};

export const lighting08TechnicalCatalog: TechnicalCatalogEntry = {
  schemaVersion: TECHNICAL_CATALOG_ENTRY_SCHEMA_VERSION,
  id: "technical/lighting-08",
  target: { kind: "item", entityId: UNDER_CAB_LIGHT_ITEM_ID },
  identity: { alias: "08", title: "Iluminação", category: "iluminação técnica", shortLabel: "LED bancada" },
  specifications: [
    {
      id: "lighting08/function/worktop",
      category: "function",
      text: "Iluminação sob o aéreo da pia em perfil traseiro de canto.",
      source: core("scene-core:currentUnderCabLightContract")
    }
  ],
  components: [],
  notices: [],
  dependencies: [
    {
      relation: "requires-present",
      targetEntityId: module06.id,
      label: "Aéreo da pia",
      source: sheet(LIGHT08_RULE)
    },
    {
      relation: "requires-present",
      targetEntityId: module04.id,
      label: "Lateral da geladeira / acabamento elétrico",
      source: sheet(LIGHT08_RULE)
    },
    {
      relation: "control-point-host",
      targetEntityId: module04.id,
      label: "Ponto de fixação do interruptor",
      source: sheet(MODULE04_SHEET)
    }
  ],
  controls: [
    {
      kind: "visibility",
      label: "Exibir perfil",
      binding: "viewer-visibility",
      implementationStatus: "declared-not-bound"
    },
    {
      kind: "activation",
      label: "Ligar iluminação",
      binding: "feature-enabled",
      implementationStatus: "declared-not-bound",
      defaultEnabled: true
    }
  ],
  finishes: [],
  technicalViews: [
    { id: "lighting08/view/profile", label: "Detalhe do perfil", kind: "detail", source: "external-contract" }
  ],
  sourceRefs: [
    sheet(LIGHT08_RULE),
    sheet(MODULE04_SHEET),
    core("scene-core:currentUnderCabLightContract"),
    core("scene-core:under-cab-host=module06")
  ]
};

export const CURRENT_TECHNICAL_CATALOG: readonly TechnicalCatalogEntry[] = [
  module02TechnicalCatalog,
  module03TechnicalCatalog,
  module04TechnicalCatalog,
  lighting08TechnicalCatalog
];
