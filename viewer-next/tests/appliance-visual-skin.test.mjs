import assert from "node:assert/strict";
import test from "node:test";
import {
  currentAppearance,
  currentSceneBase
} from "@mobilipresenter/scene-core";
import {
  BoxGeometry,
  Group,
  Mesh,
  MeshBasicMaterial,
  Vector3
} from "three";
import { applianceLocalBounds, resolveApplianceFit } from "../dist-ts/src/renderer/three/appliances.js";
import {
  APPLIANCE_VISUAL_SKIN_CONTRACT_VERSION,
  attachApplianceVisualSkins,
  buildApplianceVisualSkin,
  normalizeExternalApplianceVisual
} from "../dist-ts/src/renderer/three/appliance-visual-skin.js";
import { ThreeMaterialRegistry } from "../dist-ts/src/renderer/three/materials.js";
import { buildThreeScene } from "../dist-ts/src/renderer/three/scene-adapter.js";

const definitions = new Map(currentAppearance.applianceDefinitions.map(definition => [definition.id, definition]));
const applianceItems = currentSceneBase.items.filter(item => item.kind !== "accessory");

function itemAndDefinitionForRole(role) {
  const definition = currentAppearance.applianceDefinitions.find(candidate => candidate.role === role);
  assert.ok(definition, `definition:${role}`);
  const item = applianceItems.find(candidate => candidate.definitionId === definition.id);
  assert.ok(item, `item:${role}`);
  return { item, definition };
}

function syntheticExternalVisual() {
  const geometry = new BoxGeometry(2, 3, 4);
  const material = new MeshBasicMaterial();
  const mesh = new Mesh(geometry, material);
  mesh.name = "synthetic-appliance-mesh";
  mesh.position.set(12, 22, 34);
  const root = new Group();
  root.name = "synthetic-preloaded-appliance";
  root.add(mesh);
  return { root, mesh, geometry, material };
}

function approx(actual, expected, epsilon = 1e-6) {
  assert.ok(Math.abs(actual - expected) <= epsilon, `${actual} != ${expected}`);
}

function assertCanonicalBounds(object, target) {
  const bounds = applianceLocalBounds(object);
  const size = bounds.getSize(new Vector3());
  approx(bounds.min.x, 0);
  approx(bounds.min.y, 0);
  approx(bounds.max.z, 0);
  approx(size.x, target.width);
  approx(size.y, target.height);
  approx(size.z, target.depth);
}

function firstMesh(object) {
  let found = null;
  object.traverse(candidate => {
    if (!found && candidate instanceof Mesh) found = candidate;
  });
  assert.ok(found);
  return found;
}

test("external visual normalization derives metric bounds only from the authoritative fitted target", () => {
  const source = syntheticExternalVisual();
  const target = { width: 596, height: 596, depth: 525 };
  const normalized = normalizeExternalApplianceVisual(source.root, target);

  assertCanonicalBounds(normalized, target);
  assert.equal(source.root.parent, null);
  assert.equal(source.mesh.geometry, source.geometry);
  assert.equal(source.mesh.material, source.material);

  const clonedMesh = firstMesh(normalized);
  assert.notEqual(clonedMesh, source.mesh);
  assert.notEqual(clonedMesh.geometry, source.geometry);
  assert.notEqual(clonedMesh.material, source.material);
  assert.equal(clonedMesh.castShadow, true);
  assert.equal(clonedMesh.receiveShadow, true);
  assert.equal(normalized.userData.metricAuthority, "resolved-appliance-fit-mm");
  assert.deepEqual(normalized.userData.targetMm, target);
});

test("built-in oven can use a preloaded external visual without changing fit authority", () => {
  const { item, definition } = itemAndDefinitionForRole("built-in-oven");
  assert.equal(definition.assetPolicy, "normalized-external-allowed");
  const fit = resolveApplianceFit(currentSceneBase, item, definition);
  const source = syntheticExternalVisual();
  const registry = new ThreeMaterialRegistry(currentAppearance);
  let providerCalls = 0;

  const resolution = buildApplianceVisualSkin(
    currentSceneBase,
    item,
    definition,
    registry,
    () => {
      providerCalls += 1;
      return source.root;
    }
  );

  assert.equal(providerCalls, 1);
  assert.equal(resolution.mode, "normalized-external");
  assert.equal(resolution.fallbackReason, null);
  assert.equal(resolution.root.name, `${item.id}/external`);
  assert.equal(resolution.root.userData.applianceVisualSkinContract, APPLIANCE_VISUAL_SKIN_CONTRACT_VERSION);
  assert.deepEqual(resolution.root.userData.fit, fit);

  const bounds = applianceLocalBounds(resolution.root);
  const size = bounds.getSize(new Vector3());
  approx(size.x, fit.fittedMm.width);
  approx(size.y, fit.fittedMm.height);
  approx(size.z, fit.fittedMm.depth);
  approx(bounds.min.x, fit.offsetMm[0]);
  approx(bounds.min.y, fit.offsetMm[2]);
  approx(bounds.max.z, -fit.offsetMm[1]);
  assert.equal(source.root.parent, null);
  registry.dispose();
});

test("parametric-preferred definitions never consult an external provider", () => {
  const { item, definition } = itemAndDefinitionForRole("cooktop");
  assert.equal(definition.assetPolicy, "parametric-preferred");
  const registry = new ThreeMaterialRegistry(currentAppearance);
  let providerCalls = 0;

  const resolution = buildApplianceVisualSkin(
    currentSceneBase,
    item,
    definition,
    registry,
    () => {
      providerCalls += 1;
      return syntheticExternalVisual().root;
    }
  );

  assert.equal(providerCalls, 0);
  assert.equal(resolution.mode, "parametric");
  assert.equal(resolution.fallbackReason, null);
  assert.equal(resolution.root.name, `${item.id}/parametric`);
  registry.dispose();
});

test("absence and external-provider failures fall back deterministically to parametric visuals", () => {
  const { item, definition } = itemAndDefinitionForRole("built-in-oven");
  const registry = new ThreeMaterialRegistry(currentAppearance);

  const absent = buildApplianceVisualSkin(
    currentSceneBase,
    item,
    definition,
    registry,
    () => null
  );
  assert.equal(absent.mode, "parametric-fallback");
  assert.equal(absent.fallbackReason, "APPLIANCE_EXTERNAL_VISUAL_UNAVAILABLE");
  assert.equal(absent.root.name, `${item.id}/parametric`);

  const thrown = buildApplianceVisualSkin(
    currentSceneBase,
    item,
    definition,
    registry,
    () => { throw new Error("SYNTHETIC_PROVIDER_FAILURE:private detail is discarded"); }
  );
  assert.equal(thrown.mode, "parametric-fallback");
  assert.equal(thrown.fallbackReason, "SYNTHETIC_PROVIDER_FAILURE");
  assert.equal(thrown.root.userData.applianceVisualFallbackReason, "SYNTHETIC_PROVIDER_FAILURE");

  const invalid = buildApplianceVisualSkin(
    currentSceneBase,
    item,
    definition,
    registry,
    () => new Group()
  );
  assert.equal(invalid.mode, "parametric-fallback");
  assert.equal(invalid.fallbackReason, "APPLIANCE_EXTERNAL_BOUNDS_EMPTY");
  registry.dispose();
});

test("no provider preserves the current parametric path even for external-allowed definitions", () => {
  const { item, definition } = itemAndDefinitionForRole("built-in-oven");
  const registry = new ThreeMaterialRegistry(currentAppearance);
  const resolution = buildApplianceVisualSkin(currentSceneBase, item, definition, registry);
  assert.equal(resolution.mode, "parametric");
  assert.equal(resolution.fallbackReason, null);
  assert.equal(resolution.root.name, `${item.id}/parametric`);
  registry.dispose();
});

test("construction-time attachment reports visual mode and remains fail-closed on duplicate attachment", () => {
  const adapter = buildThreeScene(currentSceneBase, () => new MeshBasicMaterial());
  const registry = new ThreeMaterialRegistry(currentAppearance);
  const ovenSource = syntheticExternalVisual();
  const { item: oven } = itemAndDefinitionForRole("built-in-oven");
  const { item: cooktop } = itemAndDefinitionForRole("cooktop");

  const attachments = attachApplianceVisualSkins(
    adapter,
    currentSceneBase,
    currentAppearance,
    registry,
    (_item, definition) => definition.role === "built-in-oven" ? ovenSource.root : null
  );

  assert.equal(attachments.length, applianceItems.length);
  const ovenAttachment = attachments.find(candidate => candidate.itemId === oven.id);
  const cooktopAttachment = attachments.find(candidate => candidate.itemId === cooktop.id);
  assert.deepEqual(ovenAttachment, {
    itemId: oven.id,
    definitionId: oven.definitionId,
    mode: "normalized-external",
    fallbackReason: null
  });
  assert.equal(cooktopAttachment?.mode, "parametric");
  assert.equal(cooktopAttachment?.fallbackReason, null);
  assert.ok(adapter.entityGroups.get(oven.id)?.getObjectByName(`${oven.id}/external`));
  assert.ok(adapter.entityGroups.get(cooktop.id)?.getObjectByName(`${cooktop.id}/parametric`));
  assert.equal(ovenSource.root.parent, null);

  assert.throws(
    () => attachApplianceVisualSkins(adapter, currentSceneBase, currentAppearance, registry),
    /APPLIANCE_VISUAL_ALREADY_ATTACHED/
  );
  registry.dispose();
});

test("fixture lookup stays complete for every active appliance definition", () => {
  for (const item of applianceItems) {
    assert.ok(definitions.get(item.definitionId), item.definitionId);
  }
});
