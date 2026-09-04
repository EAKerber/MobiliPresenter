import type {
  ApplianceDefinition,
  DimensionTripleMm,
  SceneItem,
  ScenePackage
} from "@mobilipresenter/scene-core";
import {
  Box3,
  Group,
  Mesh,
  Object3D,
  Vector3
} from "three";
import {
  buildParametricAppliance,
  resolveApplianceFit
} from "./appliances.js";
import type { ThreeMaterialRegistry } from "./materials.js";
import type { ThreeSceneAdapter } from "./scene-adapter.js";

export const APPLIANCE_VISUAL_SKIN_CONTRACT_VERSION = "ApplianceVisualSkin 0.1.0" as const;

export type ApplianceVisualMode =
  | "parametric"
  | "normalized-external"
  | "parametric-fallback";

export type ApplianceVisualProvider = (
  item: SceneItem,
  definition: ApplianceDefinition
) => Object3D | null | undefined;

export interface ApplianceVisualResolution {
  readonly root: Object3D;
  readonly mode: ApplianceVisualMode;
  readonly fallbackReason: string | null;
}

export interface ApplianceVisualAttachment {
  readonly itemId: string;
  readonly definitionId: string;
  readonly mode: ApplianceVisualMode;
  readonly fallbackReason: string | null;
}

const EXTERNAL_ROOT_SUFFIX = "external";
const PARAMETRIC_ROOT_SUFFIX = "parametric";
const MIN_BOUNDS_MM = 1e-9;
const BOUNDS_EPSILON_MM = 1e-6;

function rootName(item: SceneItem, suffix: string): string {
  return `${item.id}/${suffix}`;
}

function validDimension(value: number): boolean {
  return Number.isFinite(value) && value > MIN_BOUNDS_MM;
}

function assertTargetDimensions(targetMm: DimensionTripleMm): void {
  if (![targetMm.width, targetMm.height, targetMm.depth].every(validDimension)) {
    throw new Error("APPLIANCE_EXTERNAL_TARGET_INVALID");
  }
}

function cloneOwnedVisual(source: Object3D): Object3D {
  const clone = source.clone(true);
  clone.traverse(object => {
    if (!(object instanceof Mesh)) return;
    object.geometry = object.geometry.clone();
    object.material = Array.isArray(object.material)
      ? object.material.map(material => material.clone())
      : object.material.clone();
    object.castShadow = true;
    object.receiveShadow = true;
  });
  return clone;
}

function sourceBounds(object: Object3D): Box3 {
  object.updateWorldMatrix(true, true);
  const bounds = new Box3().setFromObject(object);
  if (bounds.isEmpty()) throw new Error("APPLIANCE_EXTERNAL_BOUNDS_EMPTY");
  const size = bounds.getSize(new Vector3());
  if (![size.x, size.y, size.z].every(validDimension)) {
    throw new Error("APPLIANCE_EXTERNAL_BOUNDS_INVALID");
  }
  return bounds;
}

function assertCanonicalBounds(object: Object3D, targetMm: DimensionTripleMm): void {
  const bounds = sourceBounds(object);
  const size = bounds.getSize(new Vector3());
  const values = [
    Math.abs(bounds.min.x),
    Math.abs(bounds.min.y),
    Math.abs(bounds.max.z),
    Math.abs(size.x - targetMm.width),
    Math.abs(size.y - targetMm.height),
    Math.abs(size.z - targetMm.depth)
  ];
  if (values.some(value => value > BOUNDS_EPSILON_MM)) {
    throw new Error("APPLIANCE_EXTERNAL_NORMALIZATION_FAILED");
  }
}

/**
 * Normalize a pre-oriented external visual into the renderer's local appliance frame.
 *
 * Source orientation is intentionally not inferred here. The provider must supply a
 * pre-oriented +X width / +Y height / Z depth object. This function owns metric
 * normalization only: canonical bounds become x=[0,width], y=[0,height],
 * z=[-depth,0]. Physical dimensions always come from resolveApplianceFit(), never
 * from the external asset.
 */
export function normalizeExternalApplianceVisual(
  source: Object3D,
  targetMm: DimensionTripleMm
): Object3D {
  assertTargetDimensions(targetMm);

  const owned = cloneOwnedVisual(source);
  const scaleFrame = new Group();
  scaleFrame.name = "appliance-external-scale-frame";
  scaleFrame.add(owned);

  const before = sourceBounds(scaleFrame);
  const sourceSize = before.getSize(new Vector3());
  scaleFrame.scale.set(
    targetMm.width / sourceSize.x,
    targetMm.height / sourceSize.y,
    targetMm.depth / sourceSize.z
  );
  scaleFrame.updateWorldMatrix(true, true);

  const scaled = sourceBounds(scaleFrame);
  scaleFrame.position.set(
    -scaled.min.x,
    -scaled.min.y,
    -scaled.max.z
  );
  scaleFrame.updateWorldMatrix(true, true);

  const canonical = new Group();
  canonical.name = "appliance-external-canonical-frame";
  canonical.userData.metricAuthority = "resolved-appliance-fit-mm";
  canonical.userData.targetMm = { ...targetMm };
  canonical.add(scaleFrame);
  canonical.updateWorldMatrix(true, true);
  assertCanonicalBounds(canonical, targetMm);
  return canonical;
}

function stableFallbackReason(error: unknown): string {
  if (!(error instanceof Error)) return "APPLIANCE_EXTERNAL_PROVIDER_ERROR";
  const code = error.message.split(":", 1)[0]?.trim() ?? "";
  return /^[A-Z0-9_]+$/.test(code) && code.length > 0
    ? code
    : "APPLIANCE_EXTERNAL_PROVIDER_ERROR";
}

function decorateParametricFallback(
  root: Object3D,
  mode: "parametric" | "parametric-fallback",
  fallbackReason: string | null
): ApplianceVisualResolution {
  root.userData.applianceVisualSkinContract = APPLIANCE_VISUAL_SKIN_CONTRACT_VERSION;
  root.userData.applianceVisualMode = mode;
  if (fallbackReason !== null) root.userData.applianceVisualFallbackReason = fallbackReason;
  return { root, mode, fallbackReason };
}

function buildExternalResolution(
  scene: ScenePackage,
  item: SceneItem,
  definition: ApplianceDefinition,
  source: Object3D
): ApplianceVisualResolution {
  const fit = resolveApplianceFit(scene, item, definition);
  const root = new Group();
  root.name = rootName(item, EXTERNAL_ROOT_SUFFIX);
  root.userData.applianceDefinitionId = definition.id;
  root.userData.fit = fit;
  root.userData.applianceVisualSkinContract = APPLIANCE_VISUAL_SKIN_CONTRACT_VERSION;
  root.userData.applianceVisualMode = "normalized-external";

  const visual = normalizeExternalApplianceVisual(source, fit.fittedMm);
  visual.position.set(fit.offsetMm[0], fit.offsetMm[2], -fit.offsetMm[1]);
  root.add(visual);
  return {
    root,
    mode: "normalized-external",
    fallbackReason: null
  };
}

export function buildApplianceVisualSkin(
  scene: ScenePackage,
  item: SceneItem,
  definition: ApplianceDefinition,
  registry: ThreeMaterialRegistry,
  provider?: ApplianceVisualProvider
): ApplianceVisualResolution {
  if (definition.assetPolicy !== "normalized-external-allowed" || provider === undefined) {
    return decorateParametricFallback(
      buildParametricAppliance(scene, item, definition, registry),
      "parametric",
      null
    );
  }

  try {
    const source = provider(item, definition);
    if (source === null || source === undefined) {
      return decorateParametricFallback(
        buildParametricAppliance(scene, item, definition, registry),
        "parametric-fallback",
        "APPLIANCE_EXTERNAL_VISUAL_UNAVAILABLE"
      );
    }
    return buildExternalResolution(scene, item, definition, source);
  } catch (error) {
    return decorateParametricFallback(
      buildParametricAppliance(scene, item, definition, registry),
      "parametric-fallback",
      stableFallbackReason(error)
    );
  }
}

/**
 * Construction-time attachment path for appliance visual skins.
 *
 * This function is intentionally synchronous and expects already-loaded objects.
 * Asset loading, URLs, caching and network failure policy stay outside the renderer.
 * It is intended to replace attachParametricAppliances() at composition construction
 * time once a real approved provider exists.
 */
export function attachApplianceVisualSkins(
  adapter: ThreeSceneAdapter,
  scene: ScenePackage,
  definitionsSource: { readonly applianceDefinitions: readonly ApplianceDefinition[] },
  registry: ThreeMaterialRegistry,
  provider?: ApplianceVisualProvider
): readonly ApplianceVisualAttachment[] {
  const definitions = new Map(
    definitionsSource.applianceDefinitions.map(definition => [definition.id, definition] as const)
  );
  const attachments: ApplianceVisualAttachment[] = [];

  for (const item of scene.items) {
    if (item.kind === "accessory") continue;
    const definition = definitions.get(item.definitionId);
    if (!definition) throw new Error(`APPLIANCE_DEFINITION_NOT_FOUND:${item.definitionId}`);
    const group = adapter.entityGroups.get(item.id);
    if (!group) throw new Error(`APPLIANCE_ENTITY_GROUP_NOT_FOUND:${item.id}`);

    const existingParametric = group.getObjectByName(rootName(item, PARAMETRIC_ROOT_SUFFIX));
    const existingExternal = group.getObjectByName(rootName(item, EXTERNAL_ROOT_SUFFIX));
    if (existingParametric || existingExternal) {
      throw new Error(`APPLIANCE_VISUAL_ALREADY_ATTACHED:${item.id}`);
    }

    const resolution = buildApplianceVisualSkin(scene, item, definition, registry, provider);
    group.add(resolution.root);
    attachments.push({
      itemId: item.id,
      definitionId: definition.id,
      mode: resolution.mode,
      fallbackReason: resolution.fallbackReason
    });
  }

  return attachments;
}
