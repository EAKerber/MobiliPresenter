import assert from "node:assert/strict";
import test from "node:test";
import {
  currentSceneBase,
  module02,
  module03WithSink,
  setVisibilityIntent
} from "@mobilipresenter/scene-core";
import { styleAnchorAppearance } from "../dist-ts/src/fixtures/style-anchor.js";
import {
  INTERACTION_HIGHLIGHT_ID,
  resolveModuleInteractionTargets
} from "../dist-ts/src/renderer/three/interaction-highlight.js";
import { ThreeMaterialRegistry } from "../dist-ts/src/renderer/three/materials.js";
import { moduleIdForEntity } from "../dist-ts/src/renderer/three/ownership.js";
import { INTERACTION_OUTLINE_PROFILE } from "../dist-ts/src/renderer/three/post.js";
import { buildThreeScene, syncThreeVisibility } from "../dist-ts/src/renderer/three/scene-adapter.js";

function build() {
  const registry = new ThreeMaterialRegistry(styleAnchorAppearance);
  const adapter = buildThreeScene(currentSceneBase, (entityId, slot) => registry.resolve(entityId, slot));
  return { registry, adapter };
}

function entityIdForGroup(adapter, group) {
  for (const [entityId, candidate] of adapter.entityGroups) {
    if (candidate === group) return entityId;
  }
  return null;
}

test("selection and hover resolve complete visible ownership domains without creating scene objects", () => {
  const { registry, adapter } = build();
  const sceneChildCount = adapter.scene.children.length;
  const module02Root = adapter.entityGroups.get(module02.id);
  const module03Root = adapter.entityGroups.get(module03WithSink.id);
  assert.ok(module02Root && module03Root);

  const targets = resolveModuleInteractionTargets(adapter, currentSceneBase, module03WithSink.id, module02.id);
  assert.ok(targets.selected.includes(module03Root));
  assert.ok(targets.hovered.includes(module02Root));
  assert.ok(targets.selected.length > 1, "module03 should include hosted technical entities in its highlight domain");
  assert.ok(targets.hovered.length > 1, "module02 should include hosted appliances/accessories in its highlight domain");
  assert.equal(targets.selectedModuleId, module03WithSink.id);
  assert.equal(targets.hoveredModuleId, module02.id);
  for (const group of targets.selected) {
    const entityId = entityIdForGroup(adapter, group);
    assert.ok(entityId);
    assert.equal(moduleIdForEntity(currentSceneBase, entityId), module03WithSink.id);
  }
  for (const group of targets.hovered) {
    const entityId = entityIdForGroup(adapter, group);
    assert.ok(entityId);
    assert.equal(moduleIdForEntity(currentSceneBase, entityId), module02.id);
  }
  assert.equal(adapter.scene.children.length, sceneChildCount);

  for (let index = 0; index < 100; index += 1) {
    const alternating = resolveModuleInteractionTargets(
      adapter,
      currentSceneBase,
      index % 2 === 0 ? module03WithSink.id : null,
      index % 2 === 0 ? module02.id : module03WithSink.id
    );
    assert.ok(alternating.selected.every(group => adapter.scene.children.includes(group)));
    assert.ok(alternating.hovered.every(group => adapter.scene.children.includes(group)));
  }
  assert.equal(adapter.scene.children.length, sceneChildCount);
  assert.equal(adapter.entityGroups.get(module02.id), module02Root);
  assert.equal(adapter.entityGroups.get(module03WithSink.id), module03Root);
  registry.dispose();
});

test("selected module suppresses hover outline on the same ownership domain", () => {
  const { registry, adapter } = build();
  const root = adapter.entityGroups.get(module03WithSink.id);
  assert.ok(root);
  const targets = resolveModuleInteractionTargets(
    adapter,
    currentSceneBase,
    module03WithSink.id,
    module03WithSink.id
  );
  assert.ok(targets.selected.includes(root));
  assert.ok(targets.selected.length > 1);
  assert.deepEqual(targets.hovered, []);
  assert.equal(targets.hoveredModuleId, null);
  registry.dispose();
});

test("hidden modules and hosted descendants cannot remain highlight targets", () => {
  const { registry, adapter } = build();
  const hiddenScene = setVisibilityIntent(currentSceneBase, module03WithSink.id, "off");
  syncThreeVisibility(adapter, hiddenScene);
  const selected = resolveModuleInteractionTargets(adapter, hiddenScene, module03WithSink.id, null);
  const hovered = resolveModuleInteractionTargets(adapter, hiddenScene, null, module03WithSink.id);
  assert.deepEqual(selected.selected, []);
  assert.equal(selected.selectedModuleId, null);
  assert.deepEqual(hovered.hovered, []);
  assert.equal(hovered.hoveredModuleId, null);
  registry.dispose();
});

test("interaction outline profile is stable, restrained and selection-dominant", () => {
  assert.equal(INTERACTION_HIGHLIGHT_ID, "module-outline-interaction-v1");
  assert.ok(INTERACTION_OUTLINE_PROFILE.selected.edgeStrength > INTERACTION_OUTLINE_PROFILE.hovered.edgeStrength);
  assert.ok(INTERACTION_OUTLINE_PROFILE.selected.edgeThickness > INTERACTION_OUTLINE_PROFILE.hovered.edgeThickness);
  assert.equal(INTERACTION_OUTLINE_PROFILE.selected.edgeGlow, 0.08);
  assert.equal(INTERACTION_OUTLINE_PROFILE.hovered.edgeGlow, 0);
});
