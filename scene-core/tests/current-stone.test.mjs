import assert from "node:assert/strict";
import test from "node:test";
import {
  STONE02_ID,
  STONE03_ID,
  STONE_DESIGN_THICKNESS_MM,
  STONE_REAR_UPSTAND_DEPTH_MM,
  STONE_REAR_UPSTAND_HEIGHT_MM,
  currentSceneBase,
  module02,
  module03WithSink,
  resolveWorldTransforms
} from "../dist/src/index.js";

const WALL_PLANE_Y_MM = 8650.44;
const AUDITED_STONE_WALL_TOLERANCE_MM = 0.0021;

function stoneById(id) {
  const item = currentSceneBase.items.find(candidate => candidate.id === id);
  assert.ok(item, id);
  return item;
}

function primitiveBySuffix(item, suffix) {
  const primitive = item.geometry?.find(candidate => candidate.id.endsWith(suffix));
  assert.ok(primitive, `${item.id}:${suffix}`);
  assert.equal(primitive.primitive, "box");
  return primitive;
}

test("stone is exactly two independently owned hosted entities", () => {
  const stones = currentSceneBase.items.filter(item => item.definitionId === "ACC-STONE-COUNTERTOP");
  assert.deepEqual(stones.map(item => item.id).sort(), [STONE02_ID, STONE03_ID].sort());
  assert.equal(stoneById(STONE02_ID).hostId, module02.id);
  assert.equal(stoneById(STONE03_ID).hostId, module03WithSink.id);
});

test("stone-02 and stone-03 preserve current X spans and meet exactly at module boundary", () => {
  const world = resolveWorldTransforms(currentSceneBase);
  const stone02 = stoneById(STONE02_ID);
  const stone03 = stoneById(STONE03_ID);
  const slab02 = primitiveBySuffix(stone02, "/slab");
  const slab03 = primitiveBySuffix(stone03, "/slab");
  const world02 = world.get(stone02.id);
  const world03 = world.get(stone03.id);
  assert.ok(world02 && world03);

  const start02 = world02.translationMm.x + slab02.localTransform.translationMm.x;
  const end02 = start02 + slab02.sizeMm.width;
  const start03 = world03.translationMm.x + slab03.localTransform.translationMm.x;
  const end03 = start03 + slab03.sizeMm.width;

  assert.equal(start02, 3071.739);
  assert.equal(end02, 3862.749);
  assert.equal(start03, 3862.749);
  assert.equal(end03, 5079.429);
  assert.equal(end02, start03);
});

test("both stones use the same 30mm design thickness while retaining source provenance", () => {
  for (const id of [STONE02_ID, STONE03_ID]) {
    const stone = stoneById(id);
    const slab = primitiveBySuffix(stone, "/slab");
    assert.equal(slab.sizeMm.height, STONE_DESIGN_THICKNESS_MM);
    assert.ok(slab.sourceBindingIds.some(source => source.startsWith("provenance:promob-proxy-thickness-")));
  }
});

test("rear upstands are explicit, aligned and terminate on the main wall plane within audited source tolerance", () => {
  const world = resolveWorldTransforms(currentSceneBase);
  for (const id of [STONE02_ID, STONE03_ID]) {
    const stone = stoneById(id);
    const upstand = primitiveBySuffix(stone, "/upstand");
    const stoneWorld = world.get(stone.id);
    assert.ok(stoneWorld);
    assert.equal(upstand.sizeMm.height, STONE_REAR_UPSTAND_HEIGHT_MM);
    assert.equal(upstand.sizeMm.depth, STONE_REAR_UPSTAND_DEPTH_MM);
    assert.equal(upstand.localTransform.translationMm.z, STONE_DESIGN_THICKNESS_MM);
    const rearY = stoneWorld.translationMm.y + upstand.localTransform.translationMm.y + upstand.sizeMm.depth;
    assert.ok(
      Math.abs(rearY - WALL_PLANE_Y_MM) <= AUDITED_STONE_WALL_TOLERANCE_MM,
      `${id}: rearY=${rearY}`
    );
  }

  const upstand02 = primitiveBySuffix(stoneById(STONE02_ID), "/upstand");
  const upstand03 = primitiveBySuffix(stoneById(STONE03_ID), "/upstand");
  const z02 = world.get(STONE02_ID).translationMm.z + upstand02.localTransform.translationMm.z;
  const z03 = world.get(STONE03_ID).translationMm.z + upstand03.localTransform.translationMm.z;
  assert.ok(Math.abs(z02 - z03) <= 0.001);
});
