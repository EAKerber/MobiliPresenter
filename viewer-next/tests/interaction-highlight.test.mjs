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
import { INTERACTION_OUTLINE_PROFILE } from "../dist-ts/src/renderer/three/post.js";
import { ThreeMaterialRegistry } from "../dist-ts/src/renderer/three/materials.js";
import { buildThreeScene, syncThreeVisibility } from "../dist-ts/src/renderer/three/scene-adapter.js";

function build() {
  const registry = new ThreeMaterialRegistry(styleAnchorAppearance);
  const adapter = buildThreeScene(currentSceneBase, (entityId, slot) => registry.resolve(entityId, slot));
  return { registry, adapter };
}

test("selection and hover resolve to stable module roots without creating scene objects", () => {
  const { registry, adapter } = build();
  const sceneChildCount = adapter.scene.children.length;
  const module02Root = adapter.entityGroups.get(module02.id);
  const module03Root = adapter.entityGroups.get(module03WithSink.id);
  assert.ok(module02Root && module03Root);

  const targets = resolveModuleInteractionTargets(adapter, currentSceneBase, module03WithSink.id, module02.id);
  assert.deepEqual(targets.selected, [module03Root]);
  assert.deepEqual(targets.hovered, [module02Root]);
  assert.equal(targets.selectedModuleId, module03WithSink.id);
  assert.equal(targets.hoveredModuleId, module02.id);
  assert.equal(adapter.scene.children.length, sceneChildCount);

  for (let index = 0; index < 100; index += 1) {
    const alternating = resolveModuleInteractionTargets(
      adapter,
      currentSceneBase,
      index % 2 === 0 ? module03WithSink.id : null,
      index % 2 === 0 ? module02.id : module03WithSink.id
    );
    assert.ok(alternating.selected.length <= 1);
    assert.ok(alternating.hovered.length <= 1);
  }
  assert.equal(adapter.scene.children.length, sceneChildCount);
  assert.equal(adapter.entityGroups.get(module02.id), module02Root);
  assert.equal(adapter.entityGroups.get(module03WithSink.id), module03Root);
  registry.dispose();
});

test("selected module suppresses hover outline on the same module", () => {
  const { registry, adapter } = build();
  const root = adapter.entityGroups.get(module03WithSink.id);
  assert.ok(root);
  const targets = resolveModuleInteractionTargets(
    adapter,
    currentSceneBase,
    module03WithSink.id,
    module03WithSink.id
  );
  assert.deepEqual(targets.selected, [root]);
  assert.deepEqual(targets.hovered, []);
  assert.equal(targets.hoveredModuleId, null);
  registry.dispose();
});

test("hidden modules cannot remain selected or hovered highlight targets", () => {
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
