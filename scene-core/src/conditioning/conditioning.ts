import type { GeometryPrimitive, ScenePackage } from "../contracts/model.js";
import type { RigidTransform, Vec3 } from "../core/math.js";
import { applyTransform, composeTransforms, norm, rotateVector, vec3 } from "../core/math.js";
import { projectPoint } from "../core/camera.js";
import { resolveEffectiveVisibility } from "../state/scene-state.js";

export interface ConditioningBuffers {
  readonly widthPx: number;
  readonly heightPx: number;
  readonly depthMm: Float32Array;
  readonly normalXyz: Float32Array;
  readonly entityMask: Uint16Array;
  readonly materialMask: Uint16Array;
  readonly edgeMask: Uint8Array;
  readonly entityIds: readonly string[];
  readonly materialSlots: readonly string[];
}

interface RasterFace {
  readonly entityId: string;
  readonly materialSlot: string;
  readonly vertices: readonly [Vec3, Vec3, Vec3, Vec3];
  readonly normal: Vec3;
}

const transformPoint = (transform: RigidTransform, point: Vec3): Vec3 => applyTransform(transform, point);

function boxFaces(entityId: string, primitive: Extract<GeometryPrimitive, { primitive: "box" }>, entityTransform: RigidTransform): RasterFace[] {
  const combined = composeTransforms(entityTransform, primitive.localTransform);
  const w = primitive.sizeMm.width;
  const d = primitive.sizeMm.depth;
  const h = primitive.sizeMm.height;
  const p = (x: number, y: number, z: number): Vec3 => transformPoint(combined, vec3(x, y, z));
  const n = (value: Vec3): Vec3 => norm(rotateVector(combined.rotation, value));
  const materialSlot = primitive.materialSlot ?? "__unassigned__";
  return [
    { entityId, materialSlot, vertices: [p(0,0,0), p(w,0,0), p(w,0,h), p(0,0,h)], normal: n(vec3(0,-1,0)) },
    { entityId, materialSlot, vertices: [p(0,d,0), p(0,d,h), p(w,d,h), p(w,d,0)], normal: n(vec3(0,1,0)) },
    { entityId, materialSlot, vertices: [p(0,0,0), p(0,0,h), p(0,d,h), p(0,d,0)], normal: n(vec3(-1,0,0)) },
    { entityId, materialSlot, vertices: [p(w,0,0), p(w,d,0), p(w,d,h), p(w,0,h)], normal: n(vec3(1,0,0)) },
    { entityId, materialSlot, vertices: [p(0,0,0), p(0,d,0), p(w,d,0), p(w,0,0)], normal: n(vec3(0,0,-1)) },
    { entityId, materialSlot, vertices: [p(0,0,h), p(w,0,h), p(w,d,h), p(0,d,h)], normal: n(vec3(0,0,1)) }
  ];
}

function singleFace(entityId: string, primitive: Extract<GeometryPrimitive, { primitive: "face" }>, entityTransform: RigidTransform): RasterFace {
  const combined = composeTransforms(entityTransform, primitive.localTransform);
  const origin = transformPoint(combined, vec3());
  const u = rotateVector(combined.rotation, primitive.uAxis);
  const v = rotateVector(combined.rotation, primitive.vAxis);
  const normal = norm(rotateVector(combined.rotation, primitive.normal));
  const p0 = origin;
  const p1 = { x: origin.x + u.x * primitive.sizeMm[0], y: origin.y + u.y * primitive.sizeMm[0], z: origin.z + u.z * primitive.sizeMm[0] };
  const p3 = { x: origin.x + v.x * primitive.sizeMm[1], y: origin.y + v.y * primitive.sizeMm[1], z: origin.z + v.z * primitive.sizeMm[1] };
  const p2 = { x: p1.x + v.x * primitive.sizeMm[1], y: p1.y + v.y * primitive.sizeMm[1], z: p1.z + v.z * primitive.sizeMm[1] };
  return { entityId, materialSlot: primitive.materialSlot ?? "__unassigned__", vertices: [p0,p1,p2,p3], normal };
}

function collectFaces(scene: ScenePackage): RasterFace[] {
  const visibility = resolveEffectiveVisibility(scene);
  const entities = [...scene.environment, ...scene.modules]
    .filter(entity => visibility.get(entity.id)?.effectiveVisible)
    .sort((a, b) => a.id.localeCompare(b.id));
  const faces: RasterFace[] = [];
  for (const entity of entities) {
    for (const primitive of entity.geometry) {
      if (primitive.primitive === "box") faces.push(...boxFaces(entity.id, primitive, entity.transform));
      else faces.push(singleFace(entity.id, primitive, entity.transform));
    }
  }
  return faces;
}

interface ScreenVertex { readonly x: number; readonly y: number; readonly depth: number; }

function edgeFunction(ax: number, ay: number, bx: number, by: number, px: number, py: number): number {
  return (px - ax) * (by - ay) - (py - ay) * (bx - ax);
}

function rasterTriangle(
  vertices: readonly [ScreenVertex, ScreenVertex, ScreenVertex],
  normal: Vec3,
  entityIndex: number,
  materialIndex: number,
  output: ConditioningBuffers
): void {
  const [a,b,c] = vertices;
  if (a.depth <= 0 || b.depth <= 0 || c.depth <= 0) return;
  const minX = Math.max(0, Math.floor(Math.min(a.x,b.x,c.x)));
  const maxX = Math.min(output.widthPx - 1, Math.ceil(Math.max(a.x,b.x,c.x)));
  const minY = Math.max(0, Math.floor(Math.min(a.y,b.y,c.y)));
  const maxY = Math.min(output.heightPx - 1, Math.ceil(Math.max(a.y,b.y,c.y)));
  const area = edgeFunction(a.x,a.y,b.x,b.y,c.x,c.y);
  if (Math.abs(area) < 1e-12) return;

  for (let y=minY; y<=maxY; y++) {
    for (let x=minX; x<=maxX; x++) {
      const px=x+0.5, py=y+0.5;
      const w0=edgeFunction(b.x,b.y,c.x,c.y,px,py)/area;
      const w1=edgeFunction(c.x,c.y,a.x,a.y,px,py)/area;
      const w2=1-w0-w1;
      if (w0 < -1e-9 || w1 < -1e-9 || w2 < -1e-9) continue;
      const invDepth = w0/a.depth + w1/b.depth + w2/c.depth;
      if (!(invDepth > 0)) continue;
      const depth = 1/invDepth;
      const index=y*output.widthPx+x;
      if (depth >= output.depthMm[index]!) continue;
      output.depthMm[index]=depth;
      output.entityMask[index]=entityIndex;
      output.materialMask[index]=materialIndex;
      const n=index*3;
      output.normalXyz[n]=normal.x;
      output.normalXyz[n+1]=normal.y;
      output.normalXyz[n+2]=normal.z;
    }
  }
}

function deriveEdges(output: ConditioningBuffers): void {
  const w=output.widthPx,h=output.heightPx;
  for(let y=0;y<h;y++) for(let x=0;x<w;x++) {
    const i=y*w+x,current=output.entityMask[i]!;
    if(current===0) continue;
    const neighbors=[x>0?i-1:-1,x+1<w?i+1:-1,y>0?i-w:-1,y+1<h?i+w:-1];
    if(neighbors.some(n=>n>=0 && output.entityMask[n]!==current)) output.edgeMask[i]=255;
  }
}

export function renderConditioning(scene: ScenePackage, widthPx: number, heightPx: number): ConditioningBuffers {
  if (!Number.isInteger(widthPx) || !Number.isInteger(heightPx) || widthPx <= 0 || heightPx <= 0) throw new Error("CONDITIONING_VIEWPORT_INVALID");
  const faces=collectFaces(scene);
  const entityIds=[...new Set(faces.map(face=>face.entityId))].sort();
  const materialSlots=[...new Set(faces.map(face=>face.materialSlot))].sort();
  const entityIndex=new Map(entityIds.map((id,index)=>[id,index+1] as const));
  const materialIndex=new Map(materialSlots.map((id,index)=>[id,index+1] as const));
  const pixelCount=widthPx*heightPx;
  const output:ConditioningBuffers={
    widthPx,heightPx,
    depthMm:new Float32Array(pixelCount).fill(Infinity),
    normalXyz:new Float32Array(pixelCount*3),
    entityMask:new Uint16Array(pixelCount),
    materialMask:new Uint16Array(pixelCount),
    edgeMask:new Uint8Array(pixelCount),
    entityIds,materialSlots
  };
  const viewport={widthPx,heightPx};
  for(const face of faces){
    const projected=face.vertices.map(vertex=>{const p=projectPoint(scene.camera,viewport,vertex);return{x:p.xPx,y:p.yPx,depth:p.depthMm};}) as unknown as readonly [ScreenVertex,ScreenVertex,ScreenVertex,ScreenVertex];
    const e=entityIndex.get(face.entityId)!;const m=materialIndex.get(face.materialSlot)!;
    rasterTriangle([projected[0],projected[1],projected[2]],face.normal,e,m,output);
    rasterTriangle([projected[0],projected[2],projected[3]],face.normal,e,m,output);
  }
  deriveEdges(output);
  return output;
}
