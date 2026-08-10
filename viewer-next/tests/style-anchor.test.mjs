import assert from "node:assert/strict";
import test from "node:test";
import { module02, module03WithSink } from "@mobilipresenter/scene-core";
import { styleAnchorAppearance } from "../dist-ts/src/fixtures/style-anchor.js";
import { ThreeMaterialRegistry } from "../dist-ts/src/renderer/three/materials.js";

test("S10 lower cabinetry uses one tuned wood material across module02 and module03", () => {
  const registry = new ThreeMaterialRegistry(styleAnchorAppearance);
  const ovenSurround = registry.resolve(module02.id, "front");
  const sinkFront = registry.resolve(module03WithSink.id, "front");
  assert.equal(ovenSurround.name, "front-wood");
  assert.equal(sinkFront.name, "front-wood");
  assert.deepEqual(ovenSurround.color.toArray(), sinkFront.color.toArray());
  assert.equal(ovenSurround.roughness, 0.62);
  registry.dispose();
});

test("S10 renderer palette stays neutral-warm rather than introducing screen-space tint", () => {
  const wood = styleAnchorAppearance.materials.find(material => material.id === "front-wood");
  const primary = styleAnchorAppearance.materials.find(material => material.id === "front-primary");
  const wall = styleAnchorAppearance.materials.find(material => material.id === "wall-white");
  assert.equal(wood?.baseColorSrgb, "#A8744D");
  assert.equal(primary?.baseColorSrgb, "#B2ADA5");
  assert.equal(wall?.baseColorSrgb, "#F1EEE8");
});
