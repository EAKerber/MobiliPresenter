import {
  module01,
  module02,
  module03WithSink,
  module04,
  module05,
  module06,
  module07,
  type GeometryPrimitive,
  type RigidTransform
} from "@mobilipresenter/scene-core";

const MODULES = {
  "01": module01,
  "02": module02,
  "03": module03WithSink,
  "04": module04,
  "05": module05,
  "06": module06,
  "07": module07
} as const;

const THUMBNAIL_WOOD = "#A8744D";
const THUMBNAIL_SIZE = 512;
type ThumbnailAlias = keyof typeof MODULES;
type Point3 = { readonly x: number; readonly y: number; readonly z: number };
type Point2 = { readonly x: number; readonly y: number };
type DrawFace = {
  readonly points: readonly Point3[];
  readonly fill: string;
  readonly depth: number;
};

const appElement = document.querySelector<HTMLElement>("#app");
if (!appElement) throw new Error("THUMBNAIL_APP_ROOT_NOT_FOUND");
const app: HTMLElement = appElement;

const query = new URLSearchParams(window.location.search);
const aliasValue = query.get("module");
if (!aliasValue || !(aliasValue in MODULES)) {
  throw new Error(`THUMBNAIL_MODULE_UNKNOWN:${aliasValue ?? "none"}`);
}
const alias = aliasValue as ThumbnailAlias;
const moduleDefinition = MODULES[alias];

const canvas = document.createElement("canvas");
canvas.width = THUMBNAIL_SIZE;
canvas.height = THUMBNAIL_SIZE;
canvas.style.width = "100%";
canvas.style.height = "100%";
canvas.setAttribute("aria-hidden", "true");
app.append(canvas);
const context = canvas.getContext("2d", { alpha: true });
if (!context) throw new Error("THUMBNAIL_CANVAS_CONTEXT_UNAVAILABLE");

function rotate(point: Point3, transform: RigidTransform): Point3 {
  const { x: qx, y: qy, z: qz, w: qw } = transform.rotation;
  const ix = qw * point.x + qy * point.z - qz * point.y;
  const iy = qw * point.y + qz * point.x - qx * point.z;
  const iz = qw * point.z + qx * point.y - qy * point.x;
  const iw = -qx * point.x - qy * point.y - qz * point.z;
  return {
    x: ix * qw + iw * -qx + iy * -qz - iz * -qy + transform.translationMm.x,
    y: iy * qw + iw * -qy + iz * -qx - ix * -qz + transform.translationMm.y,
    z: iz * qw + iw * -qz + ix * -qy - iy * -qx + transform.translationMm.z
  };
}

function project(point: Point3): Point2 {
  return {
    x: point.x - point.y * 0.62,
    y: -point.z + (point.x + point.y) * 0.28
  };
}

function averageDepth(points: readonly Point3[]): number {
  let value = 0;
  for (const point of points) value += point.x * 0.46 - point.y * 0.78 + point.z * 0.43;
  return value / Math.max(1, points.length);
}

function boxFaces(primitive: Extract<GeometryPrimitive, { readonly primitive: "box" }>): readonly DrawFace[] {
  const { width, height, depth } = primitive.sizeMm;
  const local: readonly Point3[] = [
    { x: 0, y: 0, z: 0 },
    { x: width, y: 0, z: 0 },
    { x: width, y: depth, z: 0 },
    { x: 0, y: depth, z: 0 },
    { x: 0, y: 0, z: height },
    { x: width, y: 0, z: height },
    { x: width, y: depth, z: height },
    { x: 0, y: depth, z: height }
  ];
  const p = local.map(point => rotate(point, primitive.localTransform));
  const frontBase = primitive.role === "front" ? "#B57C52" : THUMBNAIL_WOOD;
  const definitions: readonly { readonly indices: readonly number[]; readonly fill: string }[] = [
    { indices: [0, 1, 5, 4], fill: frontBase },
    { indices: [1, 2, 6, 5], fill: "#925F3E" },
    { indices: [2, 3, 7, 6], fill: "#805438" },
    { indices: [3, 0, 4, 7], fill: "#996543" },
    { indices: [4, 5, 6, 7], fill: "#C58C62" },
    { indices: [3, 2, 1, 0], fill: "#744B34" }
  ];
  return definitions.map(definition => {
    const points = definition.indices.map(index => p[index]!);
    return { points, fill: definition.fill, depth: averageDepth(points) };
  });
}

function facePrimitive(
  primitive: Extract<GeometryPrimitive, { readonly primitive: "face" }>
): DrawFace {
  const u: Point3 = {
    x: primitive.uAxis.x * primitive.sizeMm[0],
    y: primitive.uAxis.y * primitive.sizeMm[0],
    z: primitive.uAxis.z * primitive.sizeMm[0]
  };
  const v: Point3 = {
    x: primitive.vAxis.x * primitive.sizeMm[1],
    y: primitive.vAxis.y * primitive.sizeMm[1],
    z: primitive.vAxis.z * primitive.sizeMm[1]
  };
  const points = [
    { x: 0, y: 0, z: 0 },
    u,
    { x: u.x + v.x, y: u.y + v.y, z: u.z + v.z },
    v
  ].map(point => rotate(point, primitive.localTransform));
  return { points, fill: THUMBNAIL_WOOD, depth: averageDepth(points) };
}

function collectFaces(): readonly DrawFace[] {
  const faces: DrawFace[] = [];
  for (const primitive of moduleDefinition.geometry ?? []) {
    if (primitive.primitive === "box") faces.push(...boxFaces(primitive));
    else faces.push(facePrimitive(primitive));
  }
  return faces.sort((a, b) => a.depth - b.depth);
}

function render(): void {
  const faces = collectFaces();
  if (faces.length === 0) throw new Error(`THUMBNAIL_MODULE_GEOMETRY_EMPTY:${alias}`);
  const projected = faces.flatMap(face => face.points.map(project));
  const minX = Math.min(...projected.map(point => point.x));
  const maxX = Math.max(...projected.map(point => point.x));
  const minY = Math.min(...projected.map(point => point.y));
  const maxY = Math.max(...projected.map(point => point.y));
  const width = Math.max(1, maxX - minX);
  const height = Math.max(1, maxY - minY);
  const padding = 54;
  const scale = Math.min(
    (THUMBNAIL_SIZE - padding * 2) / width,
    (THUMBNAIL_SIZE - padding * 2) / height
  );
  const offsetX = (THUMBNAIL_SIZE - width * scale) / 2 - minX * scale;
  const offsetY = (THUMBNAIL_SIZE - height * scale) / 2 - minY * scale;

  context.clearRect(0, 0, THUMBNAIL_SIZE, THUMBNAIL_SIZE);
  context.lineJoin = "round";
  context.lineCap = "round";
  context.lineWidth = 1.25;
  context.strokeStyle = "rgba(72, 46, 31, 0.38)";

  for (const face of faces) {
    const points = face.points.map(project);
    context.beginPath();
    context.moveTo(points[0]!.x * scale + offsetX, points[0]!.y * scale + offsetY);
    for (const point of points.slice(1)) {
      context.lineTo(point.x * scale + offsetX, point.y * scale + offsetY);
    }
    context.closePath();
    context.fillStyle = face.fill;
    context.fill();
    context.stroke();
  }

  const pixels = context.getImageData(0, 0, THUMBNAIL_SIZE, THUMBNAIL_SIZE).data;
  let opaquePixels = 0;
  for (let index = 3; index < pixels.length; index += 4) {
    if (pixels[index]! > 8) opaquePixels += 1;
  }
  if (opaquePixels < 2_000) throw new Error(`THUMBNAIL_EMPTY_FRAME:${alias}:${opaquePixels}`);

  app.dataset.rendererReady = "true";
  app.dataset.frameRendered = "true";
  app.dataset.thumbnailModule = alias;
  app.dataset.thumbnailBackground = "transparent";
  app.dataset.thumbnailCameraPolicy = "isolated-product-isometric-canvas-v1";
  app.dataset.thumbnailMaterial = "warm-wood-preview";
  app.dataset.thumbnailOpaquePixels = String(opaquePixels);
  app.dataset.thumbnailPrimitiveCount = String(moduleDefinition.geometry?.length ?? 0);
}

render();
