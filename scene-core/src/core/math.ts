export interface Vec3 {
  readonly x: number;
  readonly y: number;
  readonly z: number;
}

export interface Quaternion {
  readonly x: number;
  readonly y: number;
  readonly z: number;
  readonly w: number;
}

export interface RigidTransform {
  readonly translationMm: Vec3;
  readonly rotation: Quaternion;
}

export interface Aabb3 {
  readonly min: Vec3;
  readonly max: Vec3;
}

export const EPSILON = 1e-9;

export const vec3 = (x = 0, y = 0, z = 0): Vec3 => ({ x, y, z });
export const quatIdentity = (): Quaternion => ({ x: 0, y: 0, z: 0, w: 1 });

export const add = (a: Vec3, b: Vec3): Vec3 => ({
  x: a.x + b.x,
  y: a.y + b.y,
  z: a.z + b.z
});

export const sub = (a: Vec3, b: Vec3): Vec3 => ({
  x: a.x - b.x,
  y: a.y - b.y,
  z: a.z - b.z
});

export const mul = (a: Vec3, scalar: number): Vec3 => ({
  x: a.x * scalar,
  y: a.y * scalar,
  z: a.z * scalar
});

export const dot = (a: Vec3, b: Vec3): number =>
  a.x * b.x + a.y * b.y + a.z * b.z;

export const cross = (a: Vec3, b: Vec3): Vec3 => ({
  x: a.y * b.z - a.z * b.y,
  y: a.z * b.x - a.x * b.z,
  z: a.x * b.y - a.y * b.x
});

export function norm(a: Vec3): Vec3 {
  const length = Math.hypot(a.x, a.y, a.z);
  if (length < EPSILON) throw new Error("ZERO_LENGTH_VECTOR");
  return mul(a, 1 / length);
}

export function normalizeQuaternion(q: Quaternion): Quaternion {
  const length = Math.hypot(q.x, q.y, q.z, q.w);
  if (length < EPSILON) throw new Error("ZERO_LENGTH_QUATERNION");
  return { x: q.x / length, y: q.y / length, z: q.z / length, w: q.w / length };
}

export const conjugateQuaternion = (q: Quaternion): Quaternion => ({
  x: -q.x,
  y: -q.y,
  z: -q.z,
  w: q.w
});

export function multiplyQuaternion(a: Quaternion, b: Quaternion): Quaternion {
  return {
    x: a.w * b.x + a.x * b.w + a.y * b.z - a.z * b.y,
    y: a.w * b.y - a.x * b.z + a.y * b.w + a.z * b.x,
    z: a.w * b.z + a.x * b.y - a.y * b.x + a.z * b.w,
    w: a.w * b.w - a.x * b.x - a.y * b.y - a.z * b.z
  };
}

export function quaternionFromAxisAngle(axis: Vec3, radians: number): Quaternion {
  const n = norm(axis);
  const half = radians / 2;
  const s = Math.sin(half);
  return normalizeQuaternion({ x: n.x * s, y: n.y * s, z: n.z * s, w: Math.cos(half) });
}

export function rotateVector(qInput: Quaternion, vector: Vec3): Vec3 {
  const q = normalizeQuaternion(qInput);
  const v: Quaternion = { x: vector.x, y: vector.y, z: vector.z, w: 0 };
  const result = multiplyQuaternion(multiplyQuaternion(q, v), conjugateQuaternion(q));
  return { x: result.x, y: result.y, z: result.z };
}

export function applyTransform(transform: RigidTransform, localPoint: Vec3): Vec3 {
  return add(rotateVector(transform.rotation, localPoint), transform.translationMm);
}

export function invertTransform(transform: RigidTransform): RigidTransform {
  const rotation = conjugateQuaternion(normalizeQuaternion(transform.rotation));
  return {
    rotation,
    translationMm: rotateVector(rotation, mul(transform.translationMm, -1))
  };
}

export function composeTransforms(parent: RigidTransform, child: RigidTransform): RigidTransform {
  return {
    rotation: normalizeQuaternion(multiplyQuaternion(parent.rotation, child.rotation)),
    translationMm: applyTransform(parent, child.translationMm)
  };
}

export function aabbFromPoints(points: readonly Vec3[]): Aabb3 {
  if (points.length === 0) throw new Error("AABB_REQUIRES_POINTS");
  let minX = Infinity, minY = Infinity, minZ = Infinity;
  let maxX = -Infinity, maxY = -Infinity, maxZ = -Infinity;
  for (const p of points) {
    minX = Math.min(minX, p.x); minY = Math.min(minY, p.y); minZ = Math.min(minZ, p.z);
    maxX = Math.max(maxX, p.x); maxY = Math.max(maxY, p.y); maxZ = Math.max(maxZ, p.z);
  }
  return { min: vec3(minX, minY, minZ), max: vec3(maxX, maxY, maxZ) };
}

export const aabbSize = (box: Aabb3): Vec3 => sub(box.max, box.min);

export function containsPoint(box: Aabb3, p: Vec3, toleranceMm = 0): boolean {
  return p.x >= box.min.x - toleranceMm && p.x <= box.max.x + toleranceMm &&
    p.y >= box.min.y - toleranceMm && p.y <= box.max.y + toleranceMm &&
    p.z >= box.min.z - toleranceMm && p.z <= box.max.z + toleranceMm;
}
