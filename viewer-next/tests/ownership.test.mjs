import assert from "node:assert/strict";
import test from "node:test";
import {
  currentFaucetAnchor,
  currentSceneBase,
  currentUnderCabLightContract,
  module02,
  module03WithSink,
  module06
} from "@mobilipresenter/scene-core";
import { styleAnchorAppearance } from "../dist-ts/src/fixtures/style-anchor.js";
import { attachParametricAppliances } from "../dist-ts/src/renderer/three/appliances.js";
import { applyFh06FaucetRefinement } from "../dist-ts/src/renderer/three/faucet-refinement.js";
import {
  auditRenderOwnership,
  selectableModuleIdForObject
} from "../dist-ts/src/renderer/three/ownership.js";
import { buildThreeScene } from "../dist-ts/src/renderer/three/scene-adapter.js";
import { applyFh06SinkRefinement } from "../dist-ts/src/renderer/three/sink-refinement.js";
import { applyFh06UnderCabProfile } from "../dist-ts/src/renderer/three/under-cab-profile.js";
import { ThreeMaterialRegistry } from "../dist-ts/src/renderer/three/materials.js";

test("S1-S10 owned refinements stay inside entity groups", () => {
  const registry = new ThreeMaterialRegistry(styleAnchorAppearance);
  const adapter = buildThreeScene(currentSceneBase, (entityId, slot) => registry.resolve(entityId, slot));
  attachParametricAppliances(adapter, currentSceneBase, styleAnchorAppearance, registry);
  applyFh06SinkRefinement(adapter, registry, currentSceneBase);
  applyFh06FaucetRefinement(adapter, registry, currentFaucetAnchor);
  applyFh06UnderCabProfile(adapter, registry, currentSceneBase, currentUnderCabLightContract);

  const audit = auditRenderOwnership(adapter);
  assert.equal(audit.pass, true, JSON.stringify(audit));
  assert.equal(audit.unownedTopLevelNames.length, 0);
  assert.equal(audit.entityGroupCount, adapter.entityGroups.size);
  registry.dispose();
});

test("picking an owned child maps through hosted ownership to its module", () => {
  const registry = new ThreeMaterialRegistry(styleAnchorAppearance);
  const adapter = buildThreeScene(currentSceneBase, (entityId, slot) => registry.resolve(entityId, slot));
  attachParametricAppliances(adapter, currentSceneBase, styleAnchorAppearance, registry);
  applyFh06SinkRefinement(adapter, registry, currentSceneBase);
  applyFh06FaucetRefinement(adapter, registry, currentFaucetAnchor);
  applyFh06UnderCabProfile(adapter, registry, currentSceneBase, currentUnderCabLightContract);

  const oven = adapter.entityGroups.get("scene/traditional/appliance/oven")?.children[0];
  assert.ok(oven);
  assert.equal(selectableModuleIdForObject(adapter, currentSceneBase, oven), module02.id);

  const sink = adapter.entityGroups.get("scene/traditional/fixture/kitchen-sink")?.children[0];
  assert.ok(sink);
  assert.equal(selectableModuleIdForObject(adapter, currentSceneBase, sink), module03WithSink.id);

  const led = adapter.entityGroups.get("scene/traditional/accessory/under-cab-led-06")?.children[0];
  assert.ok(led);
  assert.equal(selectableModuleIdForObject(adapter, currentSceneBase, led), module06.id);
  registry.dispose();
});
