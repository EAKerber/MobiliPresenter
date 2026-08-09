import type { ScenePackage } from "../contracts/model.js";

function canonical(value: unknown): string {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  const object = value as Record<string, unknown>;
  const keys = Object.keys(object).sort();
  return `{${keys.map(key => `${JSON.stringify(key)}:${canonical(object[key])}`).join(",")}}`;
}

function fnv1a64(text: string): string {
  let hash = 0xcbf29ce484222325n;
  const prime = 0x100000001b3n;
  const mask = 0xffffffffffffffffn;
  const bytes = new TextEncoder().encode(text);
  for (const byte of bytes) {
    hash ^= BigInt(byte);
    hash = (hash * prime) & mask;
  }
  return hash.toString(16).padStart(16, "0");
}

export function sceneGeometryDigest(scene: ScenePackage): string {
  const geometryOnly = {
    coordinateSystem: scene.coordinateSystem,
    environment: scene.environment.map(entity => ({
      id: entity.id,
      transform: entity.transform,
      structuralEnvelope: entity.structuralEnvelope,
      geometry: entity.geometry
    })),
    items: scene.items.map(entity => ({
      id: entity.id,
      kind: entity.kind,
      transform: entity.transform,
      hostId: entity.hostId ?? null,
      slotId: entity.slotId ?? null,
      definitionId: entity.definitionId
    })),
    modules: scene.modules.map(entity => ({
      id: entity.id,
      transform: entity.transform,
      dimensions: entity.dimensions,
      structuralEnvelope: entity.structuralEnvelope,
      renderEnvelope: entity.renderEnvelope,
      geometry: entity.geometry,
      applianceSlots: entity.applianceSlots
    }))
  };
  return `fnv1a64:${fnv1a64(canonical(geometryOnly))}`;
}
