import assert from "node:assert/strict";
import test from "node:test";
import { currentSceneBase } from "@mobilipresenter/scene-core";
import { styleAnchorAppearance } from "../dist-ts/src/fixtures/style-anchor.js";
import { attachParametricAppliances } from "../dist-ts/src/renderer/three/appliances.js";
import { applyFh06CooktopContact } from "../dist-ts/src/renderer/three/cooktop-contact.js";
import { measureCurrentCooktopStoneContact } from "../dist-ts/src/renderer/three/contact-fidelity.js";
import { ThreeMaterialRegistry } from "../dist-ts/src/renderer/three/materials.js";
import { buildThreeScene } from "../dist-ts/src/renderer/three/scene-adapter.js";

test("S10 Contact Fidelity measures the rendered cooktop exactly 1mm above stone-02", () => {
  const registry = new ThreeMaterialRegistry(styleAnchorAppearance);
  const adapter = buildThreeScene(currentSceneBase, (entityId, slot) => registry.resolve(entityId, slot));
  attachParametricAppliances(adapter, currentSceneBase, styleAnchorAppearance, registry);
  applyFh06CooktopContact(adapter, currentSceneBase);
  const measurement = measureCurrentCooktopStoneContact(adapter, currentSceneBase);
  assert.equal(measurement.id, "contact/cooktop/stone-02");
  assert.equal(measurement.expectedGapMm, 1);
  assert.ok(Math.abs(measurement.measuredGapMm - 1) <= 0.01, JSON.stringify(measurement));
  assert.equal(measurement.pass, true);
  registry.dispose();
});

test("Contact Fidelity fails deterministically when expected gap does not match rendered contact", () => {
  const registry = new ThreeMaterialRegistry(styleAnchorAppearance);
  const adapter = buildThreeScene(currentSceneBase, (entityId, slot) => registry.resolve(entityId, slot));
  attachParametricAppliances(adapter, currentSceneBase, styleAnchorAppearance, registry);
  applyFh06CooktopContact(adapter, currentSceneBase);
  const measurement = measureCurrentCooktopStoneContact(adapter, currentSceneBase, 5);
  assert.equal(measurement.pass, false);
  assert.ok(Math.abs(measurement.measuredGapMm - 1) <= 0.01);
  registry.dispose();
});

// CI checkpoint: first reusable Contact Fidelity hard gate.
