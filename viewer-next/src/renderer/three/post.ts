import { Camera, Color, PerspectiveCamera, Scene, ShaderMaterial, Vector2, WebGLRenderer } from "three";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { ShaderPass } from "three/addons/postprocessing/ShaderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import type { AppearancePackage } from "@mobilipresenter/scene-core";
import { BLOOM_LAYER } from "./lighting.js";

const BLACK = new Color(0x000000);

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
  readonly finalComposer: EffectComposer;
  render(): void;
  setSize(widthPx: number, heightPx: number): void;
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

  return {
    bloomCamera,
    bloomComposer,
    finalComposer,
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
    dispose(): void {
      bloomComposer.dispose();
      finalComposer.dispose();
      mixMaterial.dispose();
    }
  };
}
