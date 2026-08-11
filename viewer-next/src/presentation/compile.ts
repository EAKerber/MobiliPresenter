import {
  allSceneEntities,
  resolveEffectiveVisibility,
  resolveMaterialId,
  type AppearancePackage,
  type ModuleGeometry,
  type ScenePackage
} from "@mobilipresenter/scene-core";
import { FRONT_PRESETS, type FrontPresetId } from "../runtime/presets.js";
import { STONE_PRESETS, type StonePresetId } from "../fixtures/stone-presets.js";
import type { ViewerConfigurationState } from "../runtime/viewer-state.js";
import {
  TECHNICAL_CATALOG_ENTRY_SCHEMA_VERSION,
  TECHNICAL_PRESENTATION_PACKAGE_SCHEMA_VERSION,
  type CompiledFinishOption,
  type CompiledFinishPolicy,
  type CompiledTechnicalDimensions,
  type CompiledTechnicalDependency,
  type FinishPolicy,
  type TechnicalCatalogEntry,
  type TechnicalPresentationPackage
} from "./contracts.js";

export interface TechnicalPresentationCompilerInput {
  readonly scene: ScenePackage;
  readonly appearance: AppearancePackage;
  readonly configuration: ViewerConfigurationState;
  readonly catalog: readonly TechnicalCatalogEntry[];
}

function catalogByTarget(catalog: readonly TechnicalCatalogEntry[]): ReadonlyMap<string, TechnicalCatalogEntry> {
  return new Map(catalog.map(entry => [entry.target.entityId, entry] as const));
}

function moduleDimensions(module: ModuleGeometry, entry: TechnicalCatalogEntry): CompiledTechnicalDimensions {
  const presentation = entry.dimensions ?? {
    order: ["width", "height", "depth"] as const,
    labels: { width: "L", height: "A", depth: "P" },
    prefer: "nominal" as const
  };
  const nominal = module.dimensions.nominalMm;
  const useNominal = presentation.prefer === "nominal" && nominal !== undefined;
  return {
    primaryKind: useNominal ? "nominal" : "geometry",
    primaryMm: useNominal ? nominal : module.dimensions.geometryMm,
    ...(nominal ? { nominalMm: nominal } : {}),
    geometryMm: module.dimensions.geometryMm,
    order: presentation.order,
    labels: presentation.labels,
    evidence: module.dimensions.evidence
  };
}

function finishOptions(policy: FinishPolicy): readonly CompiledFinishOption[] {
  switch (policy.optionFamily) {
    case "front-preset":
      return policy.allowedOptionIds.map(rawId => {
        const preset = FRONT_PRESETS[rawId as FrontPresetId];
        if (!preset) throw new Error(`TECHNICAL_FINISH_OPTION_UNKNOWN:${policy.id}:${rawId}`);
        return { id: preset.id, label: preset.label, materialId: preset.materialId };
      });
    case "stone-preset":
      return policy.allowedOptionIds.map(rawId => {
        const preset = STONE_PRESETS[rawId as StonePresetId];
        if (!preset) throw new Error(`TECHNICAL_FINISH_OPTION_UNKNOWN:${policy.id}:${rawId}`);
        return { id: preset.id, label: preset.label, materialId: preset.materialId };
      });
  }
}

function currentFinishOption(policy: FinishPolicy, configuration: ViewerConfigurationState): string | null {
  switch (policy.optionFamily) {
    case "front-preset":
      return configuration.frontPresetByModule[policy.targetEntityId] ?? null;
    case "stone-preset":
      return configuration.stonePresetId;
  }
}

function compileFinish(
  policy: FinishPolicy,
  appearance: AppearancePackage,
  configuration: ViewerConfigurationState
): CompiledFinishPolicy {
  return {
    ...policy,
    options: finishOptions(policy),
    currentOptionId: currentFinishOption(policy, configuration),
    resolvedMaterialId: resolveMaterialId(appearance, policy.targetEntityId, policy.materialSlot)
  };
}

export function validateTechnicalCatalog(scene: ScenePackage, catalog: readonly TechnicalCatalogEntry[]): void {
  const entities = new Map(allSceneEntities(scene).map(entity => [entity.id, entity] as const));
  const ids = new Set<string>();
  const targets = new Set<string>();

  for (const entry of catalog) {
    if (entry.schemaVersion !== TECHNICAL_CATALOG_ENTRY_SCHEMA_VERSION) {
      throw new Error(`TECHNICAL_CATALOG_SCHEMA_UNSUPPORTED:${entry.id}:${entry.schemaVersion}`);
    }
    if (ids.has(entry.id)) throw new Error(`TECHNICAL_CATALOG_ID_DUPLICATE:${entry.id}`);
    if (targets.has(entry.target.entityId)) throw new Error(`TECHNICAL_CATALOG_TARGET_DUPLICATE:${entry.target.entityId}`);
    ids.add(entry.id);
    targets.add(entry.target.entityId);

    const target = entities.get(entry.target.entityId);
    if (!target) throw new Error(`TECHNICAL_CATALOG_TARGET_NOT_FOUND:${entry.target.entityId}`);
    if (entry.target.kind === "module" && target.kind !== "module") {
      throw new Error(`TECHNICAL_CATALOG_TARGET_KIND_MISMATCH:${entry.target.entityId}:${target.kind}`);
    }
    if (entry.target.kind === "item" && (target.kind === "module" || target.kind === "environment")) {
      throw new Error(`TECHNICAL_CATALOG_TARGET_KIND_MISMATCH:${entry.target.entityId}:${target.kind}`);
    }

    // Catalog authors may choose how dimensions are presented, but may not duplicate physical values.
    const dimensionPolicy = entry.dimensions as unknown as Record<string, unknown> | undefined;
    for (const forbidden of ["primaryMm", "nominalMm", "geometryMm", "widthMm", "heightMm", "depthMm"]) {
      if (dimensionPolicy && forbidden in dimensionPolicy) {
        throw new Error(`TECHNICAL_CATALOG_PHYSICAL_DIMENSION_FORBIDDEN:${entry.id}:${forbidden}`);
      }
    }

    for (const dependency of entry.dependencies) {
      if (!entities.has(dependency.targetEntityId)) {
        throw new Error(`TECHNICAL_DEPENDENCY_TARGET_NOT_FOUND:${entry.id}:${dependency.targetEntityId}`);
      }
    }
    for (const finish of entry.finishes) {
      if (!entities.has(finish.targetEntityId)) {
        throw new Error(`TECHNICAL_FINISH_TARGET_NOT_FOUND:${entry.id}:${finish.targetEntityId}`);
      }
      finishOptions(finish);
    }
    for (const view of entry.technicalViews) {
      if (view.kind === "internal" && !view.internalLayout) {
        throw new Error(`TECHNICAL_INTERNAL_LAYOUT_REQUIRED:${entry.id}:${view.id}`);
      }
      if (view.internalLayout) {
        if (view.internalLayout.segments.length === 0 || view.internalLayout.segments.some(segment => segment.spanMm <= 0)) {
          throw new Error(`TECHNICAL_INTERNAL_LAYOUT_INVALID:${entry.id}:${view.id}`);
        }
        for (const subdivision of view.internalLayout.subdivisions ?? []) {
          if (subdivision.segmentIndex < 0 || subdivision.segmentIndex >= view.internalLayout.segments.length || subdivision.count < 1) {
            throw new Error(`TECHNICAL_INTERNAL_SUBDIVISION_INVALID:${entry.id}:${view.id}`);
          }
        }
      }
    }
  }
}

export function compileTechnicalPresentation(
  input: TechnicalPresentationCompilerInput,
  targetEntityId: string
): TechnicalPresentationPackage {
  validateTechnicalCatalog(input.scene, input.catalog);
  const entry = catalogByTarget(input.catalog).get(targetEntityId);
  if (!entry) throw new Error(`TECHNICAL_PRESENTATION_TARGET_NOT_CATALOGED:${targetEntityId}`);

  const entities = new Map(allSceneEntities(input.scene).map(entity => [entity.id, entity] as const));
  const target = entities.get(targetEntityId);
  if (!target) throw new Error(`TECHNICAL_PRESENTATION_TARGET_NOT_FOUND:${targetEntityId}`);
  const visibility = resolveEffectiveVisibility(input.scene);

  const dependencies: readonly CompiledTechnicalDependency[] = entry.dependencies.map(dependency => {
    const entity = entities.get(dependency.targetEntityId);
    const effective = visibility.get(dependency.targetEntityId);
    if (!entity || !effective) throw new Error(`TECHNICAL_DEPENDENCY_UNRESOLVED:${dependency.targetEntityId}`);
    return {
      ...dependency,
      targetKind: entity.kind,
      effectiveVisible: effective.effectiveVisible
    };
  });
  const blockingDependencyIds = dependencies
    .filter(dependency => dependency.relation === "requires-present" && !dependency.effectiveVisible)
    .map(dependency => dependency.targetEntityId);

  return {
    schemaVersion: TECHNICAL_PRESENTATION_PACKAGE_SCHEMA_VERSION,
    target: entry.target,
    identity: entry.identity,
    dimensions: target.kind === "module" ? moduleDimensions(target, entry) : null,
    specifications: entry.specifications,
    components: entry.components,
    notices: entry.notices,
    dependencies,
    availability: { available: blockingDependencyIds.length === 0, blockingDependencyIds },
    controls: entry.controls,
    finishes: entry.finishes.map(policy => compileFinish(policy, input.appearance, input.configuration)),
    technicalViews: entry.technicalViews,
    sourceRefs: entry.sourceRefs,
    provenance: {
      physicalAuthority: "scene-core",
      authoredAuthority: "technical-catalog",
      appearanceAuthority: "appearance-catalog",
      runtimeAuthority: "viewer-runtime"
    }
  };
}

export function compileTechnicalPresentationByAlias(
  input: TechnicalPresentationCompilerInput,
  alias: string
): TechnicalPresentationPackage {
  const entry = input.catalog.find(candidate => candidate.identity.alias === alias);
  if (!entry) throw new Error(`TECHNICAL_PRESENTATION_ALIAS_NOT_FOUND:${alias}`);
  return compileTechnicalPresentation(input, entry.target.entityId);
}

export function technicalPresentationFingerprint(value: TechnicalPresentationPackage): string {
  return JSON.stringify(value);
}
