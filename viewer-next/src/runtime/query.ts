import {
  module01,
  module02,
  module03WithSink,
  module04,
  module05,
  module06,
  module07
} from "@mobilipresenter/scene-core";
import { FRONT_PRESET_IDS, LIGHTING_PRESET_IDS, type FrontPresetId, type LightingPresetId } from "./presets.js";
import {
  createDefaultViewerConfiguration,
  createDefaultViewerInteraction,
  reduceViewerConfiguration,
  reduceViewerInteraction,
  type ViewerConfigurationState,
  type ViewerInteractionState
} from "./viewer-state.js";
import { STONE_PRESET_IDS, type StonePresetId } from "../fixtures/stone-presets.js";

const MODULE_ALIASES = {
  "01": module01.id,
  "02": module02.id,
  "03": module03WithSink.id,
  "04": module04.id,
  "05": module05.id,
  "06": module06.id,
  "07": module07.id
} as const;

const MODULE_ALIAS_ORDER = ["01", "02", "03", "04", "05", "06", "07"] as const;

export type ModuleAlias = keyof typeof MODULE_ALIASES;

interface FrontAssignment {
  readonly alias: ModuleAlias;
  readonly moduleId: string;
  readonly presetId: FrontPresetId;
}

export interface ViewerQueryMigration {
  readonly query: URLSearchParams;
  readonly migratedLegacyUniformFront: boolean;
  readonly migratedFurnitureFinishPresetId: FrontPresetId | null;
}

export function moduleIdFromAlias(alias: string): string {
  const id = MODULE_ALIASES[alias as ModuleAlias];
  if (!id) throw new Error(`VIEWER_MODULE_ALIAS_UNKNOWN:${alias}`);
  return id;
}

function splitNonEmpty(raw: string | null): readonly string[] {
  return raw ? raw.split(",").map(value => value.trim()).filter(Boolean) : [];
}

function frontPreset(rawPreset: string): FrontPresetId {
  if (!FRONT_PRESET_IDS.includes(rawPreset as FrontPresetId)) {
    throw new Error(`VIEWER_FRONT_PRESET_NOT_FOUND:${rawPreset}`);
  }
  return rawPreset as FrontPresetId;
}

function parseFrontAssignments(raw: string | null): readonly FrontAssignment[] {
  return splitNonEmpty(raw).map(assignment => {
    const [rawAlias, rawPreset] = assignment.split(":");
    if (!rawAlias || !rawPreset) throw new Error(`VIEWER_FRONT_QUERY_INVALID:${assignment}`);
    const alias = rawAlias as ModuleAlias;
    return {
      alias,
      moduleId: moduleIdFromAlias(alias),
      presetId: frontPreset(rawPreset)
    };
  });
}

function canonicalFurnitureFinish(query: URLSearchParams): FrontPresetId | null {
  const raw = query.get("finish");
  return raw ? frontPreset(raw) : null;
}

export function migrateLegacyUniformFrontQuery(query: URLSearchParams): ViewerQueryMigration {
  const next = new URLSearchParams(query.toString());
  const assignments = parseFrontAssignments(query.get("front"));
  if (assignments.length !== MODULE_ALIAS_ORDER.length) {
    return {
      query: next,
      migratedLegacyUniformFront: false,
      migratedFurnitureFinishPresetId: null
    };
  }

  const aliases = new Set(assignments.map(assignment => assignment.alias));
  const coversEveryModule = aliases.size === MODULE_ALIAS_ORDER.length
    && MODULE_ALIAS_ORDER.every(alias => aliases.has(alias));
  if (!coversEveryModule) {
    return {
      query: next,
      migratedLegacyUniformFront: false,
      migratedFurnitureFinishPresetId: null
    };
  }

  const presetId = assignments[0]!.presetId;
  if (assignments.some(assignment => assignment.presetId !== presetId)) {
    return {
      query: next,
      migratedLegacyUniformFront: false,
      migratedFurnitureFinishPresetId: null
    };
  }

  const canonical = canonicalFurnitureFinish(query);
  if (canonical !== null && canonical !== presetId) {
    throw new Error(`VIEWER_FINISH_QUERY_CONFLICT:${canonical}:${presetId}`);
  }

  next.set("finish", presetId);
  next.delete("front");
  return {
    query: next,
    migratedLegacyUniformFront: true,
    migratedFurnitureFinishPresetId: presetId
  };
}

export function parseViewerConfiguration(query: URLSearchParams): ViewerConfigurationState {
  let state = createDefaultViewerConfiguration();

  for (const alias of splitNonEmpty(query.get("hide"))) {
    state = reduceViewerConfiguration(state, {
      type: "set-module-visibility",
      moduleId: moduleIdFromAlias(alias),
      value: "off"
    });
  }

  const finish = canonicalFurnitureFinish(query);
  if (finish !== null) {
    state = reduceViewerConfiguration(state, {
      type: "set-furniture-finish-preset",
      presetId: finish
    });
  }

  for (const assignment of parseFrontAssignments(query.get("front"))) {
    state = reduceViewerConfiguration(state, {
      type: "set-front-preset",
      moduleId: assignment.moduleId,
      presetId: assignment.presetId
    });
  }

  const stone = query.get("stone");
  if (stone) {
    if (!STONE_PRESET_IDS.includes(stone as StonePresetId)) throw new Error(`VIEWER_STONE_PRESET_NOT_FOUND:${stone}`);
    state = reduceViewerConfiguration(state, { type: "set-stone-preset", presetId: stone as StonePresetId });
  }

  const light = query.get("light");
  if (light) {
    if (!LIGHTING_PRESET_IDS.includes(light as LightingPresetId)) throw new Error(`VIEWER_LIGHTING_PRESET_NOT_FOUND:${light}`);
    state = reduceViewerConfiguration(state, { type: "set-lighting-preset", presetId: light as LightingPresetId });
  }

  return state;
}

export function parseViewerInteraction(query: URLSearchParams): ViewerInteractionState {
  let state = createDefaultViewerInteraction();
  const selected = query.get("select");
  if (selected) {
    state = reduceViewerInteraction(state, {
      type: "select-module",
      moduleId: moduleIdFromAlias(selected)
    });
  }
  const hovered = query.get("hover");
  if (hovered) {
    state = reduceViewerInteraction(state, {
      type: "hover-module",
      moduleId: moduleIdFromAlias(hovered)
    });
  }
  return state;
}
