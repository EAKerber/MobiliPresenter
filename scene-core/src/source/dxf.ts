import type { BoxGeometry, GeometryRole, ModuleGeometry, SourceBinding } from "../contracts/model.js";
import { MODULE_GEOMETRY_SCHEMA_VERSION, SOURCE_BINDING_SCHEMA_VERSION, identityTransform } from "../contracts/model.js";
import type { ApplianceSlot, DimensionTripleMm } from "../contracts/model.js";

export interface DxfLayerInventory {
  readonly count: number;
  readonly entityTypes: readonly ("LINE" | "3DFACE")[];
  readonly min: readonly [number, number, number];
  readonly max: readonly [number, number, number];
  readonly size: readonly [number, number, number];
}

export interface DxfInventory {
  readonly schemaVersion: "DxfInventory 0.1.0";
  readonly source: {
    readonly name: string;
    readonly bytes: number;
    readonly sha256: string;
  };
  readonly entityCount: number;
  readonly layers: Readonly<Record<string, DxfLayerInventory>>;
}

export interface DxfBoxBindingSpec {
  readonly id: string;
  readonly layer: string;
  readonly role: GeometryRole;
  readonly materialSlot?: string;
  readonly structural: boolean;
}

export interface DxfModuleCompileSpec {
  readonly id: string;
  readonly worldOriginMm: readonly [number, number, number];
  readonly nominalMm?: DimensionTripleMm;
  readonly expectedSourceSha256: string;
  readonly bindings: readonly DxfBoxBindingSpec[];
  readonly applianceSlots?: readonly ApplianceSlot[];
}

export interface CompiledModuleFromDxf {
  readonly module: ModuleGeometry;
  readonly sourceBindings: readonly SourceBinding[];
}

function layerOrThrow(inventory: DxfInventory, layer: string): DxfLayerInventory {
  const value = inventory.layers[layer];
  if (!value) throw new Error(`DXF_LAYER_NOT_FOUND:${layer}`);
  return value;
}

function localFromAbsolute(value: readonly [number, number, number], origin: readonly [number, number, number]): readonly [number, number, number] {
  return [value[0] - origin[0], value[1] - origin[1], value[2] - origin[2]];
}

function envelopeFromLayers(layers: readonly DxfLayerInventory[], origin: readonly [number, number, number]) {
  if (layers.length === 0) throw new Error("DXF_STRUCTURAL_BINDINGS_REQUIRED");
  const absoluteMin: [number, number, number] = [Infinity, Infinity, Infinity];
  const absoluteMax: [number, number, number] = [-Infinity, -Infinity, -Infinity];
  for (const layer of layers) {
    for (let axis = 0; axis < 3; axis++) {
      absoluteMin[axis] = Math.min(absoluteMin[axis], layer.min[axis]!);
      absoluteMax[axis] = Math.max(absoluteMax[axis], layer.max[axis]!);
    }
  }
  const min = localFromAbsolute(absoluteMin, origin);
  const max = localFromAbsolute(absoluteMax, origin);
  return {
    min: { x: min[0], y: min[1], z: min[2] },
    max: { x: max[0], y: max[1], z: max[2] }
  };
}

export function compileModuleFromDxfInventory(
  inventory: DxfInventory,
  spec: DxfModuleCompileSpec
): CompiledModuleFromDxf {
  if (inventory.source.sha256 !== spec.expectedSourceSha256) {
    throw new Error(`DXF_SOURCE_FINGERPRINT_MISMATCH:${inventory.source.sha256}`);
  }
  const fingerprint = `sha256:${inventory.source.sha256}`;
  const geometry: BoxGeometry[] = [];
  const sourceBindings: SourceBinding[] = [];
  const structuralLayers: DxfLayerInventory[] = [];
  const allLayers: DxfLayerInventory[] = [];

  for (const binding of spec.bindings) {
    const layer = layerOrThrow(inventory, binding.layer);
    if (!layer.entityTypes.includes("LINE") && !layer.entityTypes.includes("3DFACE")) {
      throw new Error(`DXF_LAYER_ENTITY_UNSUPPORTED:${binding.layer}`);
    }
    const local = localFromAbsolute(layer.min, spec.worldOriginMm);
    geometry.push({
      id: `${spec.id}/geometry/${binding.id}`,
      primitive: "box",
      role: binding.role,
      localTransform: {
        translationMm: { x: local[0], y: local[1], z: local[2] },
        rotation: { x: 0, y: 0, z: 0, w: 1 }
      },
      sizeMm: { width: layer.size[0], height: layer.size[2], depth: layer.size[1] },
      sourceBindingIds: [`${spec.id}/binding/${binding.id}`],
      ...(binding.materialSlot ? { materialSlot: binding.materialSlot } : {})
    });
    sourceBindings.push({
      schemaVersion: SOURCE_BINDING_SCHEMA_VERSION,
      id: `${spec.id}/binding/${binding.id}`,
      sourceFingerprint: fingerprint,
      sourceSelector: { layer: binding.layer },
      targetEntityId: spec.id,
      targetRole: binding.role
    });
    allLayers.push(layer);
    if (binding.structural) structuralLayers.push(layer);
  }

  const structuralEnvelope = envelopeFromLayers(structuralLayers, spec.worldOriginMm);
  const renderEnvelope = envelopeFromLayers(allLayers, spec.worldOriginMm);
  const size = {
    width: structuralEnvelope.max.x - structuralEnvelope.min.x,
    height: structuralEnvelope.max.z - structuralEnvelope.min.z,
    depth: structuralEnvelope.max.y - structuralEnvelope.min.y
  };

  return {
    module: {
      id: spec.id,
      kind: "module",
      schemaVersion: MODULE_GEOMETRY_SCHEMA_VERSION,
      transform: {
        translationMm: { x: spec.worldOriginMm[0], y: spec.worldOriginMm[1], z: spec.worldOriginMm[2] },
        rotation: identityTransform().rotation
      },
      visibilityIntent: "auto",
      defaultVisible: true,
      controllable: true,
      mountPolicy: "standalone",
      dimensions: {
        ...(spec.nominalMm ? { nominalMm: spec.nominalMm } : {}),
        geometryMm: size,
        conflictPolicy: "geometry-wins-for-assembly-preserve-nominal",
        evidence: [{ source: "promob-dxf", status: "confirmed", reference: fingerprint }]
      },
      structuralEnvelope,
      renderEnvelope,
      geometry,
      applianceSlots: spec.applianceSlots ?? []
    },
    sourceBindings
  };
}
