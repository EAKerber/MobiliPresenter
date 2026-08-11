import {
  Camera,
  Color,
  PerspectiveCamera,
  Scene,
  ShaderMaterial,
  Vector2,
  WebGLRenderer,
  type Object3D
} from "three";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { GTAOPass } from "three/addons/postprocessing/GTAOPass.js";
import { OutlinePass } from "three/addons/postprocessing/OutlinePass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { ShaderPass } from "three/addons/postprocessing/ShaderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import type { AppearancePackage } from "@mobilipresenter/scene-core";
import { BLOOM_LAYER } from "./lighting.js";

const BLACK = new Color(0x000000);

export const FH06_GTAO_PROFILE = {
  blendIntensity: 0.38,
  radiusMm: 72,
  distanceExponent: 2,
  thicknessMm: 38,
  distanceFallOff: 0.92,
  scale: 1,
  samples: 16,
  denoiseRadiusPx: 4,
  denoiseRings: 2,
  denoiseSamples: 16
} as const;

export const INTERACTION_OUTLINE_PROFILE = {
  selected: {
    visibleEdgeColor: 0xc5a35a,
    hiddenEdgeColor: 0x6f5a2f,
    edgeStrength: 2.7,
    edgeGlow: 0.08,
    edgeThickness: 1.15
  },
  hovered: {
    visibleEdgeColor: 0xe8e2d8,
    hiddenEdgeColor: 0x8c877e,
    edgeStrength: 1.35,
    edgeGlow: 0,
    edgeThickness: 0.75
  }
} as const;

const additiveShader = {
  uniforms: {
    baseTexture: { value: null },
    bloomTexture: { value: null }
  },
  vertexShader: `
    varying vec2 vUv;
    void main() {
      vUv = uv;
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }
  `,
  fragmentShader: `
    uniform sampler2D baseTexture;
    uniform sampler2D bloomTexture;
    varying vec2 vUv;
    void main() {
      vec4 base = texture2D(baseTexture, vUv);
      vec4 bloom = texture2D(bloomTexture, vUv);
      gl_FragColor = base + bloom;
    }
  `
};

export interface SelectiveBloomPipeline {
  readonly bloomCamera: PerspectiveCamera;
  readonly bloomComposer: EffectComposer;
  readonly gtaoPass: GTAOPass;
  readonly selectedOutlinePass: OutlinePass;
  readonly hoveredOutlinePass: OutlinePass;
  readonly finalComposer: EffectComposer;
  setInteractionTargets(selected: readonly Object3D[], hovered: readonly Object3D[]): void;
  render(): void;
  setSize(widthPx: number, heightPx: number): void;
  setAppearance(appearance: AppearancePackage): void;
  dispose(): void;
}

export function createBloomCamera(source: PerspectiveCamera): PerspectiveCamera {
  const camera = source.clone();
  camera.layers.set(BLOOM_LAYER);
  camera.updateMatrixWorld(true);
  return camera;
}

function syncBloomCamera(target: PerspectiveCamera, source: PerspectiveCamera): void {
  target.copy(source, false);
  target.layers.set(BLOOM_LAYER);
  target.projectionMatrix.copy(source.projectionMatrix);
  target.projectionMatrixInverse.copy(source.projectionMatrixInverse);
  target.updateMatrixWorld(true);
}

export function objectParticipatesInBloom(camera: Camera, objectLayersMask: number): boolean {
  return (camera.layers.mask & objectLayersMask) !== 0;
}

function configureOutlinePass(
  pass: OutlinePass,
  profile: typeof INTERACTION_OUTLINE_PROFILE.selected | typeof INTERACTION_OUTLINE_PROFILE.hovered
): void {
  pass.visibleEdgeColor.setHex(profile.visibleEdgeColor);
  pass.hiddenEdgeColor.setHex(profile.hiddenEdgeColor);
  pass.edgeStrength = profile.edgeStrength;
  pass.edgeGlow = profile.edgeGlow;
  pass.edgeThickness = profile.edgeThickness;
  pass.pulsePeriod = 0;
  pass.selectedObjects = [];
}

export function createSelectiveBloomPipeline(
  renderer: WebGLRenderer,
  scene: Scene,
  camera: PerspectiveCamera,
  appearance: AppearancePackage,
  widthPx: number,
  heightPx: number
): SelectiveBloomPipeline {
  const bloomCamera = createBloomCamera(camera);

  const bloomComposer = new EffectComposer(renderer);
  bloomComposer.renderToScreen = false;
  const bloomRenderPass = new RenderPass(scene, bloomCamera);
  const bloomPass = new UnrealBloomPass(
    new Vector2(widthPx, heightPx),
    appearance.lighting.post.bloomStrength,
    appearance.lighting.post.bloomRadius,
    0
  );
  bloomPass.threshold = 0;
  bloomComposer.addPass(bloomRenderPass);
  bloomComposer.addPass(bloomPass);

  const finalComposer = new EffectComposer(renderer);
  const basePass = new RenderPass(scene, camera);
  finalComposer.addPass(basePass);

  const gtaoPass = new GTAOPass(scene, camera, widthPx, heightPx);
  gtaoPass.updateGtaoMaterial({
    radius: FH06_GTAO_PROFILE.radiusMm,
    distanceExponent: FH06_GTAO_PROFILE.distanceExponent,
    thickness: FH06_GTAO_PROFILE.thicknessMm,
    distanceFallOff: FH06_GTAO_PROFILE.distanceFallOff,
    scale: FH06_GTAO_PROFILE.scale,
    samples: FH06_GTAO_PROFILE.samples,
    screenSpaceRadius: false
  });
  gtaoPass.updatePdMaterial({
    radius: FH06_GTAO_PROFILE.denoiseRadiusPx,
    rings: FH06_GTAO_PROFILE.denoiseRings,
    samples: FH06_GTAO_PROFILE.denoiseSamples
  });
  gtaoPass.blendIntensity = FH06_GTAO_PROFILE.blendIntensity;
  finalComposer.addPass(gtaoPass);

  const hoveredOutlinePass = new OutlinePass(new Vector2(widthPx, heightPx), scene, camera);
  configureOutlinePass(hoveredOutlinePass, INTERACTION_OUTLINE_PROFILE.hovered);
  finalComposer.addPass(hoveredOutlinePass);

  const selectedOutlinePass = new OutlinePass(new Vector2(widthPx, heightPx), scene, camera);
  configureOutlinePass(selectedOutlinePass, INTERACTION_OUTLINE_PROFILE.selected);
  finalComposer.addPass(selectedOutlinePass);

  const mixMaterial = new ShaderMaterial({
    uniforms: {
      baseTexture: { value: null },
      bloomTexture: { value: bloomComposer.renderTarget2.texture }
    },
    vertexShader: additiveShader.vertexShader,
    fragmentShader: additiveShader.fragmentShader,
    depthWrite: false,
    depthTest: false
  });
  const mixPass = new ShaderPass(mixMaterial, "baseTexture");
  finalComposer.addPass(mixPass);
  finalComposer.addPass(new OutputPass());

  const applyAppearance = (next: AppearancePackage): void => {
    bloomPass.strength = next.lighting.post.bloomEnabled ? next.lighting.post.bloomStrength : 0;
    bloomPass.radius = next.lighting.post.bloomRadius;
  };
  applyAppearance(appearance);

  return {
    bloomCamera,
    bloomComposer,
    gtaoPass,
    selectedOutlinePass,
    hoveredOutlinePass,
    finalComposer,
    setInteractionTargets(selected, hovered): void {
      selectedOutlinePass.selectedObjects = [...selected];
      hoveredOutlinePass.selectedObjects = [...hovered];
    },
    render(): void {
      syncBloomCamera(bloomCamera, camera);
      const previousBackground = scene.background;
      scene.background = BLACK;
      bloomComposer.render();
      scene.background = previousBackground;
      finalComposer.render();
    },
    setSize(nextWidthPx: number, nextHeightPx: number): void {
      bloomComposer.setSize(nextWidthPx, nextHeightPx);
      finalComposer.setSize(nextWidthPx, nextHeightPx);
    },
    setAppearance(next: AppearancePackage): void {
      applyAppearance(next);
    },
    dispose(): void {
      bloomComposer.dispose();
      hoveredOutlinePass.dispose();
      selectedOutlinePass.dispose();
      gtaoPass.dispose();
      finalComposer.dispose();
      mixMaterial.dispose();
    }
  };
}

// CI checkpoint: typed GTAO configuration for S10.
