import type { FidelityLine3 } from "@mobilipresenter/scene-core";
import {
  BufferGeometry,
  Float32BufferAttribute,
  Group,
  LineBasicMaterial,
  LineSegments
} from "three";
import { sceneVectorToThree } from "./coordinates.js";

export interface FidelityOverlayStyle {
  readonly xray?: boolean;
  readonly opacity?: number;
}

const ROLE_COLORS: Record<FidelityLine3["role"], number> = {
  "grid-minor": 0x8b8b8b,
  "grid-major": 0x4f4f4f,
  "aabb": 0xc79a2b,
  "axis-x": 0xd94a4a,
  "axis-y": 0x55a868,
  "axis-z": 0x4c78a8,
  "wireframe": 0xc79a2b,
  "dimension": 0xf0c75e,
  "landmark": 0x4bc0d9
};

function createRoleSegments(
  role: FidelityLine3["role"],
  lines: readonly FidelityLine3[],
  style: FidelityOverlayStyle
): LineSegments | null {
  const selected = lines.filter(line => line.role === role);
  if (selected.length === 0) return null;

  const positions: number[] = [];
  for (const line of selected) {
    const a = sceneVectorToThree(line.aMm);
    const b = sceneVectorToThree(line.bMm);
    positions.push(a.x, a.y, a.z, b.x, b.y, b.z);
  }

  const geometry = new BufferGeometry();
  geometry.setAttribute("position", new Float32BufferAttribute(positions, 3));
  geometry.computeBoundingBox();
  geometry.computeBoundingSphere();

  const material = new LineBasicMaterial({
    color: ROLE_COLORS[role],
    transparent: true,
    opacity: style.opacity ?? (role === "grid-minor" ? 0.3 : 0.75),
    depthTest: !(style.xray ?? false),
    depthWrite: false
  });

  const segments = new LineSegments(geometry, material);
  segments.name = `fidelity-overlay/${role}`;
  segments.userData.fidelityRole = role;
  segments.userData.lineCount = selected.length;
  return segments;
}

export function buildFidelityOverlay(
  lines: readonly FidelityLine3[],
  style: FidelityOverlayStyle = {}
): Group {
  const group = new Group();
  group.name = "fidelity-overlay";
  group.userData.debugOnly = true;
  group.userData.lineCount = lines.length;

  const roles = Object.keys(ROLE_COLORS) as FidelityLine3["role"][];
  for (const role of roles) {
    const segments = createRoleSegments(role, lines, style);
    if (segments) group.add(segments);
  }
  return group;
}
