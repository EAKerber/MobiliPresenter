import { STONE03_ID, type SceneItem, type ScenePackage } from "@mobilipresenter/scene-core";
import {
  Box3,
  BufferGeometry,
  CylinderGeometry,
  DoubleSide,
  ExtrudeGeometry,
  Float32BufferAttribute,
  Group,
  Mesh,
  MeshStandardMaterial,
  Path,
  Shape,
  ShapeGeometry,
  type Material
} from "three";
import type { ThreeSceneAdapter } from "./scene-adapter.js";
import type { ThreeMaterialRegistry } from "./materials.js";

const SINK_ITEM_ID = "scene/traditional/fixture/kitchen-sink";
const SINK_STONE_ID = STONE03_ID;
const SINK_STONE_PRIMITIVE_ID = `${STONE03_ID}/slab`;
const SINK_FAMILY_ID = "SINK-UNDERMOUNT-40X34-01";
const ARCHETYPE_WIDTH_MM = 400;
const ARCHETYPE_DEPTH_MM = 340;
const ARCHETYPE_BOWL_DEPTH_MM = 170;
const ARCHETYPE_FLANGE_MM = 15;
const ARCHETYPE_OUTER_RADIUS_MM = 38;
const RENDER_AABB_TOLERANCE_MM = 0.001;
const RIM_THICKNESS_MM = 3;
const LOOP_SEGMENTS_PER_CORNER = 8;
const STONE_CUTOUT_SIDE_DARKENING = 0.62;
const BOWL_SIDE_DARKENING = 0.58;
const BOWL_BOTTOM_DARKENING = 0.46;

interface FitData {
  readonly envelopeMm: { readonly width: number; readonly height: number; readonly depth: number };
  readonly fittedMm: { readonly width: number; readonly height: number; readonly depth: number };
  readonly offsetMm: readonly [number, number, number];
}

interface SinkGeometryContract {
  readonly fit: FitData;
  readonly openingMm: readonly [number, number, number, number];
  readonly flangeMm: number;
  readonly outerRadiusMm: number;
  readonly openingRadiusMm: number;
  readonly bowlDepthMm: number;
  readonly topAlignedOffsetZMm: number;
}

function itemById(scene: ScenePackage, id: string): SceneItem {
  const item = scene.items.find(candidate => candidate.id === id);
  if (!item) throw new Error(`SINK_REFINEMENT_ITEM_MISSING:${id}`);
  return item;
}

function sinkProxy(adapter: ThreeSceneAdapter): Group {
  const entity = adapter.entityGroups.get(SINK_ITEM_ID);
  if (!entity) throw new Error("SINK_ENTITY_GROUP_MISSING");
  const proxy = entity.getObjectByName(`${SINK_ITEM_ID}/parametric`);
  if (!(proxy instanceof Group)) throw new Error("SINK_PROXY_MISSING");
  return proxy;
}

function roundedRectPath(
  x: number,
  y: number,
  width: number,
  depth: number,
  radius: number,
  clockwise = false
): Path {
  const r = Math.max(0, Math.min(radius, width / 2, depth / 2));
  const path = new Path();
  if (!clockwise) {
    path.moveTo(x + r, y);
    path.lineTo(x + width - r, y);
    path.quadraticCurveTo(x + width, y, x + width, y + r);
    path.lineTo(x + width, y + depth - r);
    path.quadraticCurveTo(x + width, y + depth, x + width - r, y + depth);
    path.lineTo(x + r, y + depth);
    path.quadraticCurveTo(x, y + depth, x, y + depth - r);
    path.lineTo(x, y + r);
    path.quadraticCurveTo(x, y, x + r, y);
  } else {
    path.moveTo(x + r, y);
    path.quadraticCurveTo(x, y, x, y + r);
    path.lineTo(x, y + depth - r);
    path.quadraticCurveTo(x, y + depth, x + r, y + depth);
    path.lineTo(x + width - r, y + depth);
    path.quadraticCurveTo(x + width, y + depth, x + width, y + depth - r);
    path.lineTo(x + width, y + r);
    path.quadraticCurveTo(x + width, y, x + width - r, y);
    path.lineTo(x + r, y);
  }
  path.closePath();
  return path;
}

function roundedRectShape(
  x: number,
  y: number,
  width: number,
  depth: number,
  radius: number
): Shape {
  const source = roundedRectPath(x, y, width, depth, radius, false);
  const shape = new Shape();
  shape.curves = [...source.curves];
  shape.currentPoint.copy(source.currentPoint);
  return shape;
}

function slabShapeWithHole(
  width: number,
  depth: number,
  opening: readonly [number, number, number, number],
  radius: number
): Shape {
  const shape = new Shape();
  shape.moveTo(0, 0);
  shape.lineTo(width, 0);
  shape.lineTo(width, depth);
  shape.lineTo(0, depth);
  shape.lineTo(0, 0);
  shape.closePath();
  shape.holes.push(roundedRectPath(opening[0], opening[1], opening[2], opening[3], radius, true));
  return shape;
}

function extrudedScenePlane(shape: Shape, heightMm: number): ExtrudeGeometry {
  const geometry = new ExtrudeGeometry(shape, {
    depth: heightMm,
    bevelEnabled: false,
    curveSegments: 8,
    steps: 1
  });
  geometry.rotateX(-Math.PI / 2);
  geometry.computeBoundingBox();
  geometry.computeBoundingSphere();
  return geometry;
}

function scenePlane(shape: Shape): ShapeGeometry {
  const geometry = new ShapeGeometry(shape, 8);
  geometry.rotateX(-Math.PI / 2);
  geometry.computeBoundingBox();
  geometry.computeBoundingSphere();
  return geometry;
}

function sinkContract(adapter: ThreeSceneAdapter, scene: ScenePackage): SinkGeometryContract {
  const stoneItem = itemById(scene, SINK_STONE_ID);
  const sinkItem = itemById(scene, SINK_ITEM_ID);
  if (!sinkItem.hostId || !sinkItem.slotId) throw new Error("SINK_SLOT_REFERENCE_MISSING");
  if (sinkItem.hostId !== stoneItem.hostId) throw new Error("SINK_STONE_HOST_MISMATCH");
  const host = scene.modules.find(module => module.id === sinkItem.hostId);
  if (!host) throw new Error("SINK_HOST_MODULE_MISSING");
  const slot = host.applianceSlots.find(candidate => candidate.id === sinkItem.slotId);
  if (!slot) throw new Error("SINK_SLOT_MISSING");

  const proxy = sinkProxy(adapter);
  const fit = proxy.userData.fit as FitData | undefined;
  if (!fit) throw new Error("SINK_FIT_MISSING");
  const scale = fit.fittedMm.width / ARCHETYPE_WIDTH_MM;
  const flangeMm = ARCHETYPE_FLANGE_MM * scale;
  const outerRadiusMm = ARCHETYPE_OUTER_RADIUS_MM * scale;
  const openingRadiusMm = Math.max(10, outerRadiusMm - flangeMm);
  const openingWidth = fit.fittedMm.width - 2 * flangeMm;
  const openingDepth = fit.fittedMm.depth - 2 * flangeMm;
  const slotInStoneX = slot.localTransform.translationMm.x - stoneItem.transform.translationMm.x;
  const slotInStoneY = slot.localTransform.translationMm.y - stoneItem.transform.translationMm.y;
  const openingX = slotInStoneX + fit.offsetMm[0] + flangeMm;
  const openingY = slotInStoneY + fit.offsetMm[1] + flangeMm;
  const topAlignedOffsetZMm = fit.envelopeMm.height - fit.fittedMm.height;
  const bowlDepthMm = ARCHETYPE_BOWL_DEPTH_MM * scale;

  return {
    fit,
    openingMm: [openingX, openingY, openingWidth, openingDepth],
    flangeMm,
    outerRadiusMm,
    openingRadiusMm,
    bowlDepthMm,
    topAlignedOffsetZMm
  };
}

function standardMaterial(material: Material | readonly Material[], role: string): MeshStandardMaterial {
  const first = Array.isArray(material) ? material[0] : material;
  if (!(first instanceof MeshStandardMaterial)) throw new Error(`SINK_STANDARD_MATERIAL_REQUIRED:${role}`);
  return first;
}

function darkerClone(
  source: MeshStandardMaterial,
  name: string,
  multiplier: number,
  roughness: number,
  metalness = source.metalness
): MeshStandardMaterial {
  const clone = source.clone();
  clone.name = name;
  clone.color.multiplyScalar(multiplier);
  clone.roughness = roughness;
  clone.metalness = metalness;
  clone.side = DoubleSide;
  clone.userData.transientVisualMaterial = true;
  clone.userData.luminanceMultiplier = multiplier;
  return clone;
}

function replaceStoneSlabWithHole(
  adapter: ThreeSceneAdapter,
  scene: ScenePackage,
  contract: SinkGeometryContract
): { readonly before: Box3; readonly after: Box3; readonly cutoutSideMaterial: MeshStandardMaterial } {
  const stoneItem = itemById(scene, SINK_STONE_ID);
  const primitive = stoneItem.geometry?.find(candidate => candidate.id === SINK_STONE_PRIMITIVE_ID);
  if (!primitive || primitive.primitive !== "box") throw new Error("SINK_COUNTERTOP_BOX_MISSING");
  const group = adapter.entityGroups.get(stoneItem.id);
  if (!group) throw new Error("SINK_COUNTERTOP_GROUP_MISSING");
  const primitiveGroup = group.getObjectByName(primitive.id);
  if (!(primitiveGroup instanceof Group)) throw new Error("SINK_COUNTERTOP_PRIMITIVE_GROUP_MISSING");
  const original = primitiveGroup.getObjectByName(`${primitive.id}/mesh`);
  if (!(original instanceof Mesh)) throw new Error("SINK_COUNTERTOP_MESH_MISSING");

  const [openingX, openingY, openingWidth, openingDepth] = contract.openingMm;
  if (
    openingX < 0 || openingY < 0 ||
    openingX + openingWidth > primitive.sizeMm.width ||
    openingY + openingDepth > primitive.sizeMm.depth
  ) throw new Error("SINK_CUTOUT_OUTSIDE_COUNTERTOP");

  primitiveGroup.updateWorldMatrix(true, true);
  const before = new Box3().setFromObject(primitiveGroup);
  const capMaterial = standardMaterial(original.material, "stone-cap");
  const cutoutSideMaterial = darkerClone(
    capMaterial,
    `${capMaterial.name}/sink-cutout-side`,
    STONE_CUTOUT_SIDE_DARKENING,
    Math.min(1, capMaterial.roughness + 0.14),
    0
  );
  cutoutSideMaterial.userData.sinkCutoutSide = true;

  const shape = slabShapeWithHole(
    primitive.sizeMm.width,
    primitive.sizeMm.depth,
    contract.openingMm,
    contract.openingRadiusMm
  );
  const geometry = extrudedScenePlane(shape, primitive.sizeMm.height);
  geometry.userData.visualRefinement = "fh06-1-s9-stone-hole-readability-v1";
  geometry.userData.holeCount = 1;
  geometry.userData.openingMm = [...contract.openingMm];
  geometry.userData.openingRadiusMm = contract.openingRadiusMm;
  geometry.userData.capMaterialIndex = 0;
  geometry.userData.sideMaterialIndex = 1;

  const replacement = new Mesh(geometry, [capMaterial, cutoutSideMaterial]);
  replacement.name = `${primitive.id}/mesh`;
  replacement.castShadow = true;
  replacement.receiveShadow = true;
  replacement.userData.geometryId = primitive.id;
  replacement.userData.materialSlot = primitive.materialSlot ?? "stone";
  replacement.userData.visualRefinement = "fh06-1-s9-stone-hole-readability-v1";

  primitiveGroup.remove(original);
  original.geometry.dispose();
  primitiveGroup.add(replacement);
  primitiveGroup.updateWorldMatrix(true, true);
  const after = new Box3().setFromObject(primitiveGroup);
  return { before, after, cutoutSideMaterial };
}

interface PlanePoint {
  readonly x: number;
  readonly depth: number;
}

function roundedRectLoop(
  x: number,
  depthOrigin: number,
  width: number,
  depth: number,
  radius: number,
  segmentsPerCorner = LOOP_SEGMENTS_PER_CORNER
): readonly PlanePoint[] {
  const r = Math.max(0, Math.min(radius, width / 2, depth / 2));
  const corners = [
    { cx: x + width - r, cy: depthOrigin + r, a0: -Math.PI / 2 },
    { cx: x + width - r, cy: depthOrigin + depth - r, a0: 0 },
    { cx: x + r, cy: depthOrigin + depth - r, a0: Math.PI / 2 },
    { cx: x + r, cy: depthOrigin + r, a0: Math.PI }
  ] as const;
  const points: PlanePoint[] = [];
  for (const corner of corners) {
    for (let i = 0; i < segmentsPerCorner; i++) {
      const angle = corner.a0 + (Math.PI / 2) * (i / segmentsPerCorner);
      points.push({
        x: corner.cx + Math.cos(angle) * r,
        depth: corner.cy + Math.sin(angle) * r
      });
    }
  }
  return points;
}

function bowlSideGeometry(
  topLoop: readonly PlanePoint[],
  bottomLoop: readonly PlanePoint[],
  topZ: number,
  bottomZ: number
): BufferGeometry {
  if (topLoop.length !== bottomLoop.length || topLoop.length < 8) throw new Error("SINK_BOWL_LOOP_MISMATCH");
  const positions: number[] = [];
  for (const point of topLoop) positions.push(point.x, topZ, -point.depth);
  for (const point of bottomLoop) positions.push(point.x, bottomZ, -point.depth);
  const count = topLoop.length;
  const indices: number[] = [];
  for (let i = 0; i < count; i++) {
    const next = (i + 1) % count;
    const top = i;
    const topNext = next;
    const bottom = count + i;
    const bottomNext = count + next;
    indices.push(top, bottom, bottomNext, top, bottomNext, topNext);
  }
  const geometry = new BufferGeometry();
  geometry.setAttribute("position", new Float32BufferAttribute(positions, 3));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();
  geometry.computeBoundingBox();
  geometry.computeBoundingSphere();
  geometry.userData.continuousLoft = true;
  geometry.userData.loopSamples = count;
  return geometry;
}

function rebuildSinkBowl(
  adapter: ThreeSceneAdapter,
  registry: ThreeMaterialRegistry,
  contract: SinkGeometryContract
): { readonly proxy: Group; readonly sideMaterial: MeshStandardMaterial; readonly bottomMaterial: MeshStandardMaterial } {
  const proxy = sinkProxy(adapter);
  proxy.clear();
  const inox = registry.materialByDefinitionId("inox-brushed") as MeshStandardMaterial;
  const sideMaterial = darkerClone(inox, `${inox.name}/sink-bowl-side`, BOWL_SIDE_DARKENING, 0.46, 0.72);
  sideMaterial.userData.sinkBowlSide = true;
  const bottomMaterial = darkerClone(inox, `${inox.name}/sink-bowl-bottom`, BOWL_BOTTOM_DARKENING, 0.54, 0.62);
  bottomMaterial.userData.sinkBowlBottom = true;

  const visual = new Group();
  visual.name = `${SINK_ITEM_ID}/visual`;
  visual.position.set(
    contract.fit.offsetMm[0],
    contract.topAlignedOffsetZMm,
    -contract.fit.offsetMm[1]
  );

  const width = contract.fit.fittedMm.width;
  const height = contract.fit.fittedMm.height;
  const depth = contract.fit.fittedMm.depth;
  const flange = contract.flangeMm;
  const openingWidth = width - 2 * flange;
  const openingDepth = depth - 2 * flange;
  const topZ = height - RIM_THICKNESS_MM;
  const bottomZ = Math.max(5, height - contract.bowlDepthMm);
  const bottomInset = Math.min(32 * (width / ARCHETYPE_WIDTH_MM), openingWidth * 0.16, openingDepth * 0.16);
  const bottomWidth = openingWidth - 2 * bottomInset;
  const bottomDepth = openingDepth - 2 * bottomInset;
  const bottomRadius = Math.max(10, contract.openingRadiusMm * 0.62);

  const rimShape = roundedRectShape(0, 0, width, depth, contract.outerRadiusMm);
  rimShape.holes.push(roundedRectPath(
    flange,
    flange,
    openingWidth,
    openingDepth,
    contract.openingRadiusMm,
    true
  ));
  const rim = new Mesh(extrudedScenePlane(rimShape, RIM_THICKNESS_MM), inox);
  rim.name = `${SINK_ITEM_ID}/rim`;
  rim.position.y = topZ;
  rim.castShadow = true;
  rim.receiveShadow = true;
  rim.userData.visualRole = "bright-undermount-rim";
  visual.add(rim);

  const topLoop = roundedRectLoop(flange, flange, openingWidth, openingDepth, contract.openingRadiusMm);
  const bottomLoop = roundedRectLoop(
    flange + bottomInset,
    flange + bottomInset,
    bottomWidth,
    bottomDepth,
    bottomRadius
  );
  const bowlSide = new Mesh(bowlSideGeometry(topLoop, bottomLoop, topZ, bottomZ), sideMaterial);
  bowlSide.name = `${SINK_ITEM_ID}/bowl-side`;
  bowlSide.castShadow = true;
  bowlSide.receiveShadow = true;
  bowlSide.userData.visualRole = "occluded-brushed-inox-side";
  visual.add(bowlSide);

  const bottomShape = roundedRectShape(
    flange + bottomInset,
    flange + bottomInset,
    bottomWidth,
    bottomDepth,
    bottomRadius
  );
  const bottom = new Mesh(scenePlane(bottomShape), bottomMaterial);
  bottom.name = `${SINK_ITEM_ID}/bowl-bottom`;
  bottom.position.y = bottomZ;
  bottom.receiveShadow = true;
  bottom.userData.visualRole = "occluded-brushed-inox-bottom";
  visual.add(bottom);

  const drain = new Mesh(new CylinderGeometry(20, 20, 3, 48), sideMaterial);
  drain.name = `${SINK_ITEM_ID}/drain`;
  drain.position.set(width / 2, bottomZ + 1.6, -depth / 2);
  drain.receiveShadow = true;
  visual.add(drain);

  proxy.add(visual);
  proxy.userData.visualRefinement = "fh06-1-s9-undermount-sink-readability-v1";
  proxy.userData.sinkFamilyId = SINK_FAMILY_ID;
  proxy.userData.topAlignedOffsetZMm = contract.topAlignedOffsetZMm;
  proxy.userData.bowlDepthMm = contract.bowlDepthMm;
  proxy.userData.faucetSeparatedToS5 = true;
  proxy.userData.readabilityPolicy = "physical-surface-response-no-screen-outline";
  return { proxy, sideMaterial, bottomMaterial };
}

function maxAabbDriftMm(before: Box3, after: Box3): number {
  return Math.max(
    Math.abs(before.min.x - after.min.x),
    Math.abs(before.min.y - after.min.y),
    Math.abs(before.min.z - after.min.z),
    Math.abs(before.max.x - after.max.x),
    Math.abs(before.max.y - after.max.y),
    Math.abs(before.max.z - after.max.z)
  );
}

export interface SinkRefinementResult {
  readonly sinkFamilyId: typeof SINK_FAMILY_ID;
  readonly openingMm: readonly [number, number, number, number];
  readonly openingRadiusMm: number;
  readonly flangeMm: number;
  readonly fittedOuterMm: { readonly width: number; readonly height: number; readonly depth: number };
  readonly bowlDepthMm: number;
  readonly topAlignedOffsetZMm: number;
  readonly countertopOuterEnvelopePreserved: boolean;
  readonly countertopOuterEnvelopeDriftMm: number;
  readonly countertopOuterEnvelopeToleranceMm: number;
  readonly stoneHoleGeometry: "extruded-shape-with-rounded-hole";
  readonly continuousBowl: true;
  readonly faucetSeparatedToS5: true;
  readonly readabilityPolicy: "physical-surface-response-no-screen-outline";
  readonly stoneCutoutSideDarkening: number;
  readonly bowlSideDarkening: number;
  readonly bowlBottomDarkening: number;
}

export function applyFh06SinkRefinement(
  adapter: ThreeSceneAdapter,
  registry: ThreeMaterialRegistry,
  scene: ScenePackage
): SinkRefinementResult {
  const contract = sinkContract(adapter, scene);
  const stone = replaceStoneSlabWithHole(adapter, scene, contract);
  rebuildSinkBowl(adapter, registry, contract);
  const driftMm = maxAabbDriftMm(stone.before, stone.after);
  return {
    sinkFamilyId: SINK_FAMILY_ID,
    openingMm: contract.openingMm,
    openingRadiusMm: contract.openingRadiusMm,
    flangeMm: contract.flangeMm,
    fittedOuterMm: contract.fit.fittedMm,
    bowlDepthMm: contract.bowlDepthMm,
    topAlignedOffsetZMm: contract.topAlignedOffsetZMm,
    countertopOuterEnvelopePreserved: driftMm <= RENDER_AABB_TOLERANCE_MM,
    countertopOuterEnvelopeDriftMm: driftMm,
    countertopOuterEnvelopeToleranceMm: RENDER_AABB_TOLERANCE_MM,
    stoneHoleGeometry: "extruded-shape-with-rounded-hole",
    continuousBowl: true,
    faucetSeparatedToS5: true,
    readabilityPolicy: "physical-surface-response-no-screen-outline",
    stoneCutoutSideDarkening: STONE_CUTOUT_SIDE_DARKENING,
    bowlSideDarkening: BOWL_SIDE_DARKENING,
    bowlBottomDarkening: BOWL_BOTTOM_DARKENING
  };
}
