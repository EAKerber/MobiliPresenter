import type {
  AppearancePackage,
  RelativeLight,
  SemanticEmitterDefinition
} from "../contracts/appearance.js";
import type { ScenePackage } from "../contracts/model.js";
import { resolveEffectiveVisibility } from "../state/scene-state.js";

export interface ActiveSemanticEmitter extends SemanticEmitterDefinition {
  readonly instanceId: string;
  readonly entityId: string;
  readonly definitionId: string;
}

export interface ResolvedLighting {
  readonly environment: AppearancePackage["lighting"]["environment"];
  readonly baseRig: readonly RelativeLight[];
  readonly semanticEmitters: readonly ActiveSemanticEmitter[];
  readonly post: AppearancePackage["lighting"]["post"];
}

interface EmitterOwnerDefinition {
  readonly id: string;
  readonly emitters: readonly SemanticEmitterDefinition[];
}

export function resolveLighting(scene: ScenePackage, appearance: AppearancePackage): ResolvedLighting {
  const visibility = resolveEffectiveVisibility(scene);
  const definitions = new Map<string, EmitterOwnerDefinition>();
  for (const definition of appearance.applianceDefinitions) definitions.set(definition.id, definition);
  for (const definition of appearance.accessoryDefinitions) definitions.set(definition.id, definition);

  const semanticEmitters: ActiveSemanticEmitter[] = [];
  for (const item of scene.items) {
    if (!visibility.get(item.id)?.effectiveVisible) continue;
    const definition = definitions.get(item.definitionId);
    if (!definition) continue;
    for (const emitter of definition.emitters) {
      semanticEmitters.push({
        ...emitter,
        instanceId: `${item.id}/${emitter.id}`,
        entityId: item.id,
        definitionId: definition.id
      });
    }
  }

  semanticEmitters.sort((a, b) => a.instanceId.localeCompare(b.instanceId));
  return {
    environment: appearance.lighting.environment,
    baseRig: appearance.lighting.baseRig,
    semanticEmitters,
    post: appearance.lighting.post
  };
}
