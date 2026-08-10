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

export type ModuleAlias = keyof typeof MODULE_ALIASES;

export function moduleIdFromAlias(alias: string): string {
  const id = MODULE_ALIASES[alias as ModuleAlias];
  if (!id) throw new Error(`VIEWER_MODULE_ALIAS_UNKNOWN:${alias}`);
  return id;
}

function splitNonEmpty(raw: string | null): readonly string[] {
  return raw ? raw.split(",").map(value => value.trim()).filter(Boolean) : [];
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

  for (const assignment of splitNonEmpty(query.get("front"))) {
    const [alias, rawPreset] = assignment.split(":");
    if (!alias || !rawPreset) throw new Error(`VIEWER_FRONT_QUERY_INVALID:${assignment}`);
    if (!FRONT_PRESET_IDS.includes(rawPreset as FrontPresetId)) {
      throw new Error(`VIEWER_FRONT_PRESET_NOT_FOUND:${rawPreset}`);
    }
    state = reduceViewerConfiguration(state, {
      type: "set-front-preset",
      moduleId: moduleIdFromAlias(alias),
      presetId: rawPreset as FrontPresetId
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
  const selected = query.get("select");
  if (!selected) return createDefaultViewerInteraction();
  return reduceViewerInteraction(createDefaultViewerInteraction(), {
    type: "select-module",
    moduleId: moduleIdFromAlias(selected)
  });
}
