import assert from "node:assert/strict";
import test from "node:test";
import {
  currentAppearance,
  currentSceneBase,
  resolveItemPlacementTransform,
  setVisibilityIntent
} from "@mobilipresenter/scene-core";
import { MeshBasicMaterial } from "three";
import {
  applianceLocalBounds,
  attachParametricAppliances,
  buildParametricAppliance,
  resolveApplianceFit
} from "../dist-ts/src/renderer/three/appliances.js";
import { ThreeMaterialRegistry } from "../dist-ts/src/renderer/three/materials.js";
import { buildThreeScene, syncThreeVisibility } from "../dist-ts/src/renderer/three/scene-adapter.js";

const definitions = new Map(currentAppearance.applianceDefinitions.map(definition => [definition.id, definition]));
const applianceItems = currentSceneBase.items.filter(item => item.kind !== "accessory");

function definitionFor(item) {
  const definition = definitions.get(item.definitionId);
  assert.ok(definition, item.definitionId);
  return definition;
}

function assertAtMost(actual, limit, epsilon = 1e-9) {
  assert.ok(actual <= limit + epsilon, `${actual} > ${limit}`);
}

test("every active appliance/fixture has deterministic fit inside its authorized body envelope", () => {
  for (const item of applianceItems) {
    const fit = resolveApplianceFit(currentSceneBase, item, definitionFor(item));
    assertAtMost(fit.fittedMm.width, fit.envelopeMm.width);
    assertAtMost(fit.fittedMm.height, fit.envelopeMm.height);
    assertAtMost(fit.fittedMm.depth, fit.envelopeMm.depth);
    assert.ok(fit.offsetMm.every(value => value >= -1e-9), `${item.id}: negative fit offset`);
  }
});

test("washer and fridge honor Promob target envelopes rather than source-style dimensions", () => {
  const washer = applianceItems.find(item => item.definitionId === "AP-WASHER-01");
  const fridge = applianceItems.find(item => item.definitionId === "AP-FRIDGE-01");
  assert.ok(washer && fridge);
  const washerFit = resolveApplianceFit(currentSceneBase, washer, definitionFor(washer));
  const fridgeFit = resolveApplianceFit(currentSceneBase, fridge, definitionFor(fridge));
  assert.deepEqual(washerFit.envelopeMm, { width: 690, height: 990, depth: 730 });
  assert.equal(washerFit.fittedMm.width, 690);
  assert.ok(washerFit.fittedMm.height < 990);
  assert.equal(washerFit.fittedMm.depth, 730);
  assert.deepEqual(fridgeFit.fittedMm, { width: 809, height: 1900, depth: 750 });
});

test("micro uses letterbox fit and oven preserves 596x596 front inside explicit 600x600 opening", () => {
  const micro = applianceItems.find(item => item.definitionId === "AP-MICRO-01");
  const oven = applianceItems.find(item => item.definitionId === "AP-OVEN-01");
  assert.ok(micro && oven);
  const microFit = resolveApplianceFit(currentSceneBase, micro, definitionFor(micro));
  const ovenFit = resolveApplianceFit(currentSceneBase, oven, definitionFor(oven));
  assert.equal(microFit.fittedMm.width, 550);
  assert.ok(microFit.offsetMm[2] > 0);
  assert.deepEqual(ovenFit.envelopeMm, { width: 600, height: 600, depth: 525 });
  assert.deepEqual(ovenFit.fittedMm, { width: 596, height: 596, depth: 525 });
  assert.equal(ovenFit.offsetMm[0], 2);
  assert.equal(ovenFit.offsetMm[2], 0);

  const placement = resolveItemPlacementTransform(currentSceneBase, oven);
  assert.deepEqual(placement.translationMm, { x: 3167.244, y: 8102.44, z: 181 });
  const visualFrontOrigin = {
    x: placement.translationMm.x + ovenFit.offsetMm[0],
    y: placement.translationMm.y,
    z: placement.translationMm.z + ovenFit.offsetMm[2]
  };
  assert.deepEqual(visualFrontOrigin, { x: 3169.244, y: 8102.44, z: 181 });
});

test("parametric family generation is deterministic for same definition and fit", () => {
  const registry = new ThreeMaterialRegistry(currentAppearance);
  for (const item of applianceItems) {
    const definition = definitionFor(item);
    const first = buildParametricAppliance(currentSceneBase, item, definition, registry);
    const second = buildParametricAppliance(currentSceneBase, item, definition, registry);
    assert.deepEqual(first.userData.fit, second.userData.fit);
    assert.equal(first.name, second.name);
    assert.equal(first.children[0]?.children.length, second.children[0]?.children.length, item.id);
    const firstBounds = applianceLocalBounds(first);
    const secondBounds = applianceLocalBounds(second);
    assert.deepEqual(firstBounds.min.toArray(), secondBounds.min.toArray());
    assert.deepEqual(firstBounds.max.toArray(), secondBounds.max.toArray());
    assert.equal(firstBounds.isEmpty(), false, item.id);
  }
  registry.dispose();
});

test("parametric appliances attach to existing semantic groups and preserve world placement", () => {
  const registry = new ThreeMaterialRegistry(currentAppearance);
  const adapter = buildThreeScene(currentSceneBase, () => new MeshBasicMaterial());
  const beforeGroups = new Map(adapter.entityGroups);
  attachParametricAppliances(adapter, currentSceneBase, currentAppearance, registry);

  for (const item of applianceItems) {
    const group = adapter.entityGroups.get(item.id);
    assert.equal(group, beforeGroups.get(item.id));
    assert.ok(group?.getObjectByName(`${item.id}/parametric`), item.id);
    const placement = resolveItemPlacementTransform(currentSceneBase, item);
    assert.deepEqual(group?.userData.entityId, item.id);
    assert.ok(Number.isFinite(placement.translationMm.x));
  }
  registry.dispose();
});

test("host hide keeps appliance geometry attached but only changes visibility", () => {
  const registry = new ThreeMaterialRegistry(currentAppearance);
  const adapter = buildThreeScene(currentSceneBase, () => new MeshBasicMaterial());
  attachParametricAppliances(adapter, currentSceneBase, currentAppearance, registry);
  const micro = applianceItems.find(item => item.definitionId === "AP-MICRO-01");
  assert.ok(micro?.hostId);
  const group = adapter.entityGroups.get(micro.id);
  const parametric = group?.getObjectByName(`${micro.id}/parametric`);
  assert.ok(group && parametric);
  syncThreeVisibility(adapter, setVisibilityIntent(currentSceneBase, micro.hostId, "off"));
  assert.equal(group.visible, false);
  assert.equal(group.getObjectByName(`${micro.id}/parametric`), parametric);
  registry.dispose();
});
