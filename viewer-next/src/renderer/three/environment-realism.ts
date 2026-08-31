import type { ScenePackage } from "@mobilipresenter/scene-core";
import {
  BoxGeometry,
  Group,
  Mesh,
  MeshBasicMaterial,
  MeshPhysicalMaterial,
  MeshStandardMaterial,
  PlaneGeometry,
  RectAreaLight
} from "three";
import { sceneVectorToThree } from "./coordinates.js";
import { kelvinToColor } from "./lighting.js";
import type { ThreeSceneAdapter } from "./scene-adapter.js";

export const ENVIRONMENT_REALISM_ID = "window-daylight-relief-v1" as const;

const ROOT_NAME = "__environment-realism";
const LAUNDRY_WALL_Y_MM = 8638.827;
const EXTENSION_X_MIN_MM = 700;
const EXTENSION_X_MAX_MM = 1568.684;
const WALL_HEIGHT_MM = 2601.63;
const WINDOW_X_MIN_MM = 870;
const WINDOW_X_MAX_MM = 1435;
const WINDOW_SILL_MM = 780;
const WINDOW_HEAD_MM = 2250;
const WINDOW_FRAME_MM = 45;
const WINDOW_FRAME_DEPTH_MM = 42;
const WINDOW_LIGHT_OFFSET_MM = 160;
const WINDOW_DAYLIGHT_INTENSITY = 58;
const SURFACE_TOWARD_ROOM_MM = 1.4;

const WINDOW_WIDTH_MM = WINDOW_X_MAX_MM - WINDOW_X_MIN_MM;
const WINDOW_HEIGHT_MM = WINDOW_HEAD_MM - WINDOW_SILL_MM;
const WINDOW_CENTER_X_MM = (WINDOW_X_MIN_MM + WINDOW_X_MAX_MM) / 2;
const WINDOW_CENTER_Z_MM = (WINDOW_SILL_MM + WINDOW_HEAD_MM) / 2;

function planePatch(
  name: string,
  xMinMm: number,
  xMaxMm: number,
  zMinMm: number,
  zMaxMm: number,
  sceneYMm: number,
  material: MeshStandardMaterial | MeshBasicMaterial | MeshPhysicalMaterial
): Mesh {
  const width = xMaxMm - xMinMm;
  const height = zMaxMm - zMinMm;
  const mesh = new Mesh(new PlaneGeometry(width, height), material);
  mesh.name = name;
  mesh.position.copy(sceneVectorToThree({
    x: (xMinMm + xMaxMm) / 2,
    y: sceneYMm,
    z: (zMinMm + zMaxMm) / 2
  }));
  mesh.receiveShadow = true;
  return mesh;
}

function frameBox(
  name: string,
  widthMm: number,
  heightMm: number,
  depthMm: number,
  centerX: number,
  centerZ: number,
  material: MeshStandardMaterial
): Mesh {
  const mesh = new Mesh(new BoxGeometry(widthMm, heightMm, depthMm), material);
  mesh.name = name;
  mesh.position.copy(sceneVectorToThree({
    x: centerX,
    y: LAUNDRY_WALL_Y_MM - depthMm / 2 - SURFACE_TOWARD_ROOM_MM,
    z: centerZ
  }));
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  return mesh;
}

function addWallExtension(root: Group): void {
  const wall = new MeshStandardMaterial({
    color: 0xf2f0ea,
    roughness: 0.88,
    metalness: 0
  });
  wall.name = "environment-realism/wall";

  const y = LAUNDRY_WALL_Y_MM - SURFACE_TOWARD_ROOM_MM;
  root.add(
    planePatch("environment-realism/wall-left", EXTENSION_X_MIN_MM, WINDOW_X_MIN_MM, 0, WALL_HEIGHT_MM, y, wall),
    planePatch("environment-realism/wall-right", WINDOW_X_MAX_MM, EXTENSION_X_MAX_MM, 0, WALL_HEIGHT_MM, y, wall),
    planePatch("environment-realism/wall-below", WINDOW_X_MIN_MM, WINDOW_X_MAX_MM, 0, WINDOW_SILL_MM, y, wall),
    planePatch("environment-realism/wall-above", WINDOW_X_MIN_MM, WINDOW_X_MAX_MM, WINDOW_HEAD_MM, WALL_HEIGHT_MM, y, wall)
  );
}

function addWindowAssembly(root: Group): void {
  const frame = new MeshStandardMaterial({
    color: 0xf5f5f2,
    roughness: 0.28,
    metalness: 0.02
  });
  frame.name = "environment-realism/window-frame";

  const sky = new MeshBasicMaterial({ color: 0xc5d6d8, toneMapped: false });
  sky.name = "environment-realism/outdoor-sky";
  const greenery = new MeshBasicMaterial({ color: 0x728a72, toneMapped: false });
  greenery.name = "environment-realism/outdoor-greenery";
  const glass = new MeshPhysicalMaterial({
    color: 0xe2edf0,
    roughness: 0.08,
    metalness: 0,
    opacity: 0.28,
    transparent: true,
    transmission: 0.16,
    ior: 1.45,
    depthWrite: false
  });
  glass.name = "environment-realism/window-glass";

  root.add(
    planePatch(
      "environment-realism/outdoor-sky",
      WINDOW_X_MIN_MM + WINDOW_FRAME_MM,
      WINDOW_X_MAX_MM - WINDOW_FRAME_MM,
      WINDOW_SILL_MM + WINDOW_FRAME_MM,
      WINDOW_HEAD_MM - WINDOW_FRAME_MM,
      LAUNDRY_WALL_Y_MM + 3,
      sky
    ),
    planePatch(
      "environment-realism/outdoor-greenery",
      WINDOW_X_MIN_MM + WINDOW_FRAME_MM,
      WINDOW_X_MAX_MM - WINDOW_FRAME_MM,
      WINDOW_SILL_MM + WINDOW_FRAME_MM,
      WINDOW_SILL_MM + WINDOW_HEIGHT_MM * 0.39,
      LAUNDRY_WALL_Y_MM + 2,
      greenery
    )
  );

  root.add(
    frameBox(
      "environment-realism/frame-left",
      WINDOW_FRAME_MM,
      WINDOW_HEIGHT_MM,
      WINDOW_FRAME_DEPTH_MM,
      WINDOW_X_MIN_MM + WINDOW_FRAME_MM / 2,
      WINDOW_CENTER_Z_MM,
      frame
    ),
    frameBox(
      "environment-realism/frame-right",
      WINDOW_FRAME_MM,
      WINDOW_HEIGHT_MM,
      WINDOW_FRAME_DEPTH_MM,
      WINDOW_X_MAX_MM - WINDOW_FRAME_MM / 2,
      WINDOW_CENTER_Z_MM,
      frame
    ),
    frameBox(
      "environment-realism/frame-bottom",
      WINDOW_WIDTH_MM,
      WINDOW_FRAME_MM,
      WINDOW_FRAME_DEPTH_MM,
      WINDOW_CENTER_X_MM,
      WINDOW_SILL_MM + WINDOW_FRAME_MM / 2,
      frame
    ),
    frameBox(
      "environment-realism/frame-top",
      WINDOW_WIDTH_MM,
      WINDOW_FRAME_MM,
      WINDOW_FRAME_DEPTH_MM,
      WINDOW_CENTER_X_MM,
      WINDOW_HEAD_MM - WINDOW_FRAME_MM / 2,
      frame
    ),
    frameBox(
      "environment-realism/frame-mullion",
      30,
      WINDOW_HEIGHT_MM - WINDOW_FRAME_MM * 2,
      WINDOW_FRAME_DEPTH_MM * 0.75,
      WINDOW_CENTER_X_MM,
      WINDOW_CENTER_Z_MM,
      frame
    )
  );

  const glassPlane = planePatch(
    "environment-realism/window-glass",
    WINDOW_X_MIN_MM + WINDOW_FRAME_MM,
    WINDOW_X_MAX_MM - WINDOW_FRAME_MM,
    WINDOW_SILL_MM + WINDOW_FRAME_MM,
    WINDOW_HEAD_MM - WINDOW_FRAME_MM,
    LAUNDRY_WALL_Y_MM - WINDOW_FRAME_DEPTH_MM - 2,
    glass
  );
  glassPlane.castShadow = false;
  root.add(glassPlane);

  const sill = frameBox(
    "environment-realism/window-sill",
    WINDOW_WIDTH_MM + 90,
    24,
    150,
    WINDOW_CENTER_X_MM,
    WINDOW_SILL_MM - 4,
    frame
  );
  root.add(sill);
}

function addDaylight(root: Group, scene: ScenePackage): void {
  const daylight = new RectAreaLight(
    kelvinToColor(6200),
    WINDOW_DAYLIGHT_INTENSITY,
    WINDOW_WIDTH_MM * 0.92,
    WINDOW_HEIGHT_MM * 0.88
  );
  daylight.name = "environment-realism/daylight";
  daylight.position.copy(sceneVectorToThree({
    x: WINDOW_CENTER_X_MM,
    y: LAUNDRY_WALL_Y_MM - WINDOW_LIGHT_OFFSET_MM,
    z: WINDOW_CENTER_Z_MM
  }));
  daylight.lookAt(sceneVectorToThree(scene.camera.targetMm));
  daylight.userData.appearanceOnly = true;
  daylight.userData.colorTemperatureK = 6200;
  daylight.userData.relativePresentationSource = "window";
  root.add(daylight);
}

export interface EnvironmentRealismResult {
  readonly groupName: typeof ROOT_NAME;
  readonly realismId: typeof ENVIRONMENT_REALISM_ID;
  readonly daylightWindow: true;
  readonly inferredPresentationGeometry: true;
  readonly windowWidthMm: number;
  readonly windowHeightMm: number;
  readonly daylightIntensity: number;
}

export function applyEnvironmentRealism(
  adapter: ThreeSceneAdapter,
  scene: ScenePackage
): EnvironmentRealismResult {
  const previous = adapter.scene.getObjectByName(ROOT_NAME);
  if (previous) adapter.scene.remove(previous);

  const root = new Group();
  root.name = ROOT_NAME;
  root.userData.appearanceOnly = true;
  root.userData.presentationInferred = true;
  root.userData.realismId = ENVIRONMENT_REALISM_ID;
  root.userData.sourceRefs = [
    "user-reference:2026-08-31:target-scene-window-and-natural-daylight",
    "presentation-policy:environment-dressing-not-technical-authority"
  ];

  addWallExtension(root);
  addWindowAssembly(root);
  addDaylight(root, scene);
  adapter.scene.add(root);

  return {
    groupName: ROOT_NAME,
    realismId: ENVIRONMENT_REALISM_ID,
    daylightWindow: true,
    inferredPresentationGeometry: true,
    windowWidthMm: WINDOW_WIDTH_MM,
    windowHeightMm: WINDOW_HEIGHT_MM,
    daylightIntensity: WINDOW_DAYLIGHT_INTENSITY
  };
}
