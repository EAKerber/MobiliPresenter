import type { FaucetAnchor } from "@mobilipresenter/scene-core";
import {
  CatmullRomCurve3,
  CylinderGeometry,
  Group,
  Mesh,
  MeshStandardMaterial,
  TubeGeometry,
  Vector3
} from "three";
import { FAUCET_HIGH_ARC_01, type FaucetPreset } from "../../fixtures/faucet-presets.js";
import { applySceneTransform } from "./coordinates.js";
import type { ThreeMaterialRegistry } from "./materials.js";
import type { ThreeSceneAdapter } from "./scene-adapter.js";

function cylinder(
  radiusTop: number,
  radiusBottom: number,
  height: number,
  material: MeshStandardMaterial,
  x: number,
  y: number,
  z: number,
  segments = 32
): Mesh {
  const mesh = new Mesh(new CylinderGeometry(radiusTop, radiusBottom, height, segments), material);
  mesh.position.set(x, y, z);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  return mesh;
}

function buildFaucetVisual(
  preset: FaucetPreset,
  material: MeshStandardMaterial
): Group {
  const visual = new Group();
  visual.name = `${preset.id}/visual`;

  const base = cylinder(
    preset.baseRadiusMm,
    preset.baseRadiusMm,
    preset.baseHeightMm,
    material,
    0,
    preset.baseHeightMm / 2,
    0,
    40
  );
  base.name = `${preset.id}/base`;
  visual.add(base);

  const body = cylinder(
    preset.bodyRadiusMm,
    preset.bodyRadiusMm * 1.08,
    preset.bodyHeightMm,
    material,
    0,
    preset.baseHeightMm + preset.bodyHeightMm / 2,
    0,
    36
  );
  body.name = `${preset.id}/body`;
  visual.add(body);

  const peakCenterlineY = preset.heightMm - preset.tubeRadiusMm;
  const curve = new CatmullRomCurve3([
    new Vector3(0, 62, 0),
    new Vector3(0, 185, 4),
    new Vector3(0, 286, 42),
    new Vector3(0, peakCenterlineY, 120),
    new Vector3(0, 306, 205),
    new Vector3(0, 270, preset.centerlineReachMm)
  ]);
  const spout = new Mesh(new TubeGeometry(curve, 64, preset.tubeRadiusMm, 16, false), material);
  spout.name = `${preset.id}/spout`;
  spout.castShadow = true;
  spout.receiveShadow = true;
  visual.add(spout);

  const nozzleCenterY = 270 - preset.nozzleLengthMm / 2;
  const nozzle = cylinder(
    preset.nozzleRadiusMm,
    preset.nozzleRadiusMm,
    preset.nozzleLengthMm,
    material,
    0,
    nozzleCenterY,
    preset.centerlineReachMm,
    28
  );
  nozzle.name = `${preset.id}/nozzle`;
  visual.add(nozzle);

  const aerator = cylinder(
    preset.aeratorRadiusMm,
    preset.aeratorRadiusMm,
    preset.aeratorHeightMm,
    material,
    0,
    270 - preset.nozzleLengthMm - preset.aeratorHeightMm / 2,
    preset.centerlineReachMm,
    28
  );
  aerator.name = `${preset.id}/aerator`;
  visual.add(aerator);

  const lever = cylinder(3.5, 3.5, preset.leverLengthMm, material, 18, 72, 0, 18);
  lever.name = `${preset.id}/lever`;
  lever.rotation.z = -Math.PI / 3.2;
  visual.add(lever);

  const leverKnob = cylinder(5.5, 5.5, 12, material, 39, 86, 0, 18);
  leverKnob.name = `${preset.id}/lever-knob`;
  leverKnob.rotation.z = Math.PI / 2;
  visual.add(leverKnob);

  visual.userData.faucetPresetId = preset.id;
  visual.userData.heightMm = preset.heightMm;
  visual.userData.centerlineReachMm = preset.centerlineReachMm;
  visual.userData.requiredVisualFeatures = [
    "deck-mounted-base",
    "continuous-high-arc",
    "downward-nozzle-and-aerator",
    "single-side-lever"
  ];
  return visual;
}

export interface FaucetRefinementResult {
  readonly faucetId: string;
  readonly presetId: string;
  readonly hostEntityId: string;
  readonly heightMm: number;
  readonly centerlineReachMm: number;
  readonly anchorLocalMm: readonly [number, number, number];
  readonly childCount: number;
}

export function applyFh06FaucetRefinement(
  adapter: ThreeSceneAdapter,
  registry: ThreeMaterialRegistry,
  anchor: FaucetAnchor,
  preset: FaucetPreset = FAUCET_HIGH_ARC_01
): FaucetRefinementResult {
  const host = adapter.entityGroups.get(anchor.hostEntityId);
  if (!host) throw new Error(`FAUCET_HOST_MISSING:${anchor.hostEntityId}`);
  const existing = host.getObjectByName(anchor.id);
  if (existing) host.remove(existing);

  const root = new Group();
  root.name = anchor.id;
  root.userData.fixtureAnchorId = anchor.id;
  root.userData.faucetPresetId = preset.id;
  root.userData.placementStatus = anchor.placementStatus;
  applySceneTransform(root, anchor.localTransform);

  const material = registry.materialByDefinitionId(preset.materialDefinitionId) as MeshStandardMaterial;
  const visual = buildFaucetVisual(preset, material);
  root.add(visual);
  host.add(root);

  return {
    faucetId: anchor.id,
    presetId: preset.id,
    hostEntityId: anchor.hostEntityId,
    heightMm: preset.heightMm,
    centerlineReachMm: preset.centerlineReachMm,
    anchorLocalMm: [
      anchor.localTransform.translationMm.x,
      anchor.localTransform.translationMm.y,
      anchor.localTransform.translationMm.z
    ],
    childCount: visual.children.length
  };
}
