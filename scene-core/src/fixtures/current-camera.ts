import type { FixedPerspectiveCamera, PresentationFrame } from "../contracts/model.js";

export const currentFixedCamera: FixedPerspectiveCamera = {
  id: "scene/traditional/camera/main",
  mode: "fixed",
  projection: "perspective",
  positionMm: {
    x: 4195.34622668872,
    y: 3994.363841842559,
    z: 1126.2401832635298
  },
  targetMm: {
    x: 4195.34622668872,
    y: 4994.363841842559,
    z: 1126.2401832635298
  },
  up: { x: 0, y: 0, z: 1 },
  fovYDeg: 43.2783582964253,
  principalPointNormalized: [
    0.46282390128454026,
    0.4876673063702466
  ],
  nearMm: 1,
  farMm: 20000,
  status: "calibrated",
  evidenceRefs: [
    "sha256:a78628ae5088d243888b7e23ea4b80d1f54659c41097a837c882a73b5e915049",
    "scene-source/current/fixed-camera-calibration.json"
  ]
};

export const currentPresentationFrame: PresentationFrame = {
  preferredAspectRatio: 1.9286452947259565,
  fit: "contain",
  cropAllowed: false,
  safeAreaNormalized: [0, 0, 1, 1]
};
