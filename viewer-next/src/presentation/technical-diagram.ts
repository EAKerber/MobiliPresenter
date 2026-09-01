import type {
  CompiledTechnicalViewGeometry,
  TechnicalAxis,
  TechnicalPoint2Mm,
  TechnicalPresentationPackage,
  TechnicalViewCoverage,
  TechnicalViewFidelity,
  TechnicalViewOmission,
  TechnicalViewPlane,
  TechnicalViewRequest
} from "./contracts.js";
import {
  planIsometricDimensions,
  type TechnicalCompositionPoint,
  type TechnicalDimensionPlacement
} from "./technical-composition.js";

export interface TechnicalDiagramAsset {
  readonly viewId: string;
  readonly status: "ready" | "external-required";
  readonly fidelity: TechnicalViewFidelity | null;
  readonly source: TechnicalViewRequest["source"];
  readonly coverage: readonly TechnicalViewCoverage[];
  readonly omitted: readonly TechnicalViewOmission[];
  readonly mediaType: "image/svg+xml";
  readonly svg: string | null;
}

const WIDTH = 420;
const HEIGHT = 300;
const MARGIN = 48;
const DEFAULT_OMISSIONS: readonly TechnicalViewOmission[] = ["hardware", "hidden-geometry"];

function escapeXml(value: string): string {
  return value.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");
}

function fmt(value: number): string {
  return Number.isInteger(value) ? String(value) : String(Number(value.toFixed(3)));
}

function planeAxes(plane: TechnicalViewPlane): readonly [TechnicalAxis, TechnicalAxis] {
  switch (plane) {
    case "width-height": return ["width", "height"];
    case "depth-height": return ["depth", "height"];
    case "width-depth": return ["width", "depth"];
  }
}

function svgShell(
  label: string,
  body: string,
  fidelity: TechnicalViewFidelity,
  source: TechnicalViewRequest["source"],
  extraAttributes = ""
): string {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${WIDTH} ${HEIGHT}" role="img" aria-label="${escapeXml(label)}" data-technical-fidelity="${fidelity}" data-technical-source="${source}"${extraAttributes}>` +
    `<g fill="none" stroke="currentColor" stroke-width="1.5" vector-effect="non-scaling-stroke">${body}</g></svg>`;
}

function text(
  x: number,
  y: number,
  value: string,
  anchor: "start" | "middle" | "end" = "middle",
  role?: string,
  extraAttributes = ""
): string {
  const semantic = role ? ` data-role="${role}"` : "";
  return `<text${semantic}${extraAttributes} x="${x.toFixed(2)}" y="${y.toFixed(2)}" fill="currentColor" stroke="none" font-size="12" text-anchor="${anchor}" font-family="sans-serif">${escapeXml(value)}</text>`;
}

function horizontalDimension(
  x1: number,
  x2: number,
  geometryY: number,
  dimensionY: number,
  label: string
): string {
  const mid = (x1 + x2) / 2;
  return `<line data-role="extension-line" x1="${x1.toFixed(2)}" y1="${geometryY.toFixed(2)}" x2="${x1.toFixed(2)}" y2="${dimensionY.toFixed(2)}"/>` +
    `<line data-role="extension-line" x1="${x2.toFixed(2)}" y1="${geometryY.toFixed(2)}" x2="${x2.toFixed(2)}" y2="${dimensionY.toFixed(2)}"/>` +
    `<line data-role="dimension-line" x1="${x1.toFixed(2)}" y1="${dimensionY.toFixed(2)}" x2="${x2.toFixed(2)}" y2="${dimensionY.toFixed(2)}"/>` +
    `<line data-role="tick" x1="${(x1 - 4).toFixed(2)}" y1="${(dimensionY - 4).toFixed(2)}" x2="${(x1 + 4).toFixed(2)}" y2="${(dimensionY + 4).toFixed(2)}"/>` +
    `<line data-role="tick" x1="${(x2 - 4).toFixed(2)}" y1="${(dimensionY - 4).toFixed(2)}" x2="${(x2 + 4).toFixed(2)}" y2="${(dimensionY + 4).toFixed(2)}"/>` +
    text(mid, dimensionY - 6, label, "middle", "dimension-label");
}

function verticalDimension(
  y1: number,
  y2: number,
  geometryX: number,
  dimensionX: number,
  label: string
): string {
  const mid = (y1 + y2) / 2;
  return `<line data-role="extension-line" x1="${geometryX.toFixed(2)}" y1="${y1.toFixed(2)}" x2="${dimensionX.toFixed(2)}" y2="${y1.toFixed(2)}"/>` +
    `<line data-role="extension-line" x1="${geometryX.toFixed(2)}" y1="${y2.toFixed(2)}" x2="${dimensionX.toFixed(2)}" y2="${y2.toFixed(2)}"/>` +
    `<line data-role="dimension-line" x1="${dimensionX.toFixed(2)}" y1="${y1.toFixed(2)}" x2="${dimensionX.toFixed(2)}" y2="${y2.toFixed(2)}"/>` +
    `<line data-role="tick" x1="${(dimensionX - 4).toFixed(2)}" y1="${(y1 - 4).toFixed(2)}" x2="${(dimensionX + 4).toFixed(2)}" y2="${(y1 + 4).toFixed(2)}"/>` +
    `<line data-role="tick" x1="${(dimensionX - 4).toFixed(2)}" y1="${(y2 - 4).toFixed(2)}" x2="${(dimensionX + 4).toFixed(2)}" y2="${(y2 + 4).toFixed(2)}"/>` +
    text(dimensionX - 8, mid + 4, label, "end", "dimension-label");
}

function schematicOrthographicSvg(pkg: TechnicalPresentationPackage, view: TechnicalViewRequest): string {
  const dimensions = pkg.dimensions;
  if (!dimensions || !view.plane) throw new Error(`TECHNICAL_VIEW_DIMENSIONS_REQUIRED:${view.id}`);
  const [horizontalAxis, verticalAxis] = planeAxes(view.plane);
  const horizontalMm = dimensions.primaryMm[horizontalAxis];
  const verticalMm = dimensions.primaryMm[verticalAxis];
  const drawWidth = WIDTH - MARGIN * 2;
  const drawHeight = HEIGHT - MARGIN * 2;
  const scale = Math.min(drawWidth / horizontalMm, drawHeight / verticalMm);
  const w = horizontalMm * scale;
  const h = verticalMm * scale;
  const x = (WIDTH - w) / 2;
  const y = (HEIGHT - h) / 2;
  let body = `<rect data-role="envelope" x="${x.toFixed(2)}" y="${y.toFixed(2)}" width="${w.toFixed(2)}" height="${h.toFixed(2)}"/>`;

  if (view.internalLayout) {
    const layout = view.internalLayout;
    const layoutAxis = layout.axis;
    const axisIsHorizontal = layoutAxis === horizontalAxis;
    const axisIsVertical = layoutAxis === verticalAxis;
    let cursorMm = 0;
    for (let index = 0; index < layout.segments.length; index += 1) {
      const segment = layout.segments[index]!;
      const startMm = cursorMm;
      cursorMm += segment.spanMm;
      if (axisIsHorizontal && index < layout.segments.length - 1) {
        const px = x + cursorMm * scale;
        body += `<line data-role="internal-division" x1="${px.toFixed(2)}" y1="${y.toFixed(2)}" x2="${px.toFixed(2)}" y2="${(y + h).toFixed(2)}"/>`;
      } else if (axisIsVertical && index < layout.segments.length - 1) {
        const py = y + h - cursorMm * scale;
        body += `<line data-role="internal-division" x1="${x.toFixed(2)}" y1="${py.toFixed(2)}" x2="${(x + w).toFixed(2)}" y2="${py.toFixed(2)}"/>`;
      }
      if (axisIsHorizontal) {
        body += text(x + (startMm + segment.spanMm / 2) * scale, y + h + 22, fmt(segment.spanMm), "middle", "authored-dimension-label");
      } else if (axisIsVertical) {
        body += text(x - 8, y + h - (startMm + segment.spanMm / 2) * scale, fmt(segment.spanMm), "end", "authored-dimension-label");
      }
    }

    for (const subdivision of layout.subdivisions ?? []) {
      const segment = layout.segments[subdivision.segmentIndex]!;
      const segmentStart = layout.segments.slice(0, subdivision.segmentIndex).reduce((sum, item) => sum + item.spanMm, 0);
      if (layoutAxis === "width" && horizontalAxis === "width") {
        const sx = x + segmentStart * scale;
        const sw = segment.spanMm * scale;
        for (let part = 1; part < subdivision.count; part += 1) {
          const py = y + (h * part) / subdivision.count;
          body += `<line data-role="internal-division" x1="${sx.toFixed(2)}" y1="${py.toFixed(2)}" x2="${(sx + sw).toFixed(2)}" y2="${py.toFixed(2)}"/>`;
        }
      }
    }
  }

  body += horizontalDimension(x, x + w, y + h, y + h + 36, `${fmt(horizontalMm)} mm`);
  body += verticalDimension(y + h, y, x, x - 30, `${fmt(verticalMm)} mm`);
  return svgShell(`${pkg.identity.title} — ${view.label}`, body, "schematic", view.source);
}

function pointExtent(
  primitives: CompiledTechnicalViewGeometry["primitives"],
  predicate: (role: string) => boolean
): readonly [number, number] | null {
  const points = primitives
    .filter(primitive => predicate(primitive.role))
    .flatMap(primitive => primitive.pointsMm);
  if (points.length === 0) return null;
  return [
    Math.min(...points.map(point => point.horizontalMm)),
    Math.max(...points.map(point => point.horizontalMm))
  ];
}

function screenPoint(point: TechnicalPoint2Mm, x: number, y: number, h: number, scale: number): TechnicalCompositionPoint {
  return {
    x: x + point.horizontalMm * scale,
    y: y + h - point.verticalMm * scale
  };
}

function normalizeVector(vector: TechnicalCompositionPoint): TechnicalCompositionPoint {
  const length = Math.hypot(vector.x, vector.y);
  if (length < 1e-9) return { x: 0, y: 0 };
  return { x: vector.x / length, y: vector.y / length };
}

function renderIsometricDimension(placement: TechnicalDimensionPlacement): string {
  const tangent = normalizeVector({
    x: placement.shiftedEnd.x - placement.shiftedStart.x,
    y: placement.shiftedEnd.y - placement.shiftedStart.y
  });
  const tick = { x: -tangent.y * 4, y: tangent.x * 4 };
  const attrs = ` data-axis="${placement.axis}" data-semantic-key="${placement.semanticKey}" data-source="${placement.source}" data-scope="${placement.scope}" data-region="${placement.region}" data-lane="${placement.lane}" data-lane-offset="${placement.offset.toFixed(2)}"`;
  return `<g data-role="isometric-dimension"${attrs}>` +
    `<line data-role="extension-line"${attrs} x1="${placement.start.x.toFixed(2)}" y1="${placement.start.y.toFixed(2)}" x2="${placement.shiftedStart.x.toFixed(2)}" y2="${placement.shiftedStart.y.toFixed(2)}"/>` +
    `<line data-role="extension-line"${attrs} x1="${placement.end.x.toFixed(2)}" y1="${placement.end.y.toFixed(2)}" x2="${placement.shiftedEnd.x.toFixed(2)}" y2="${placement.shiftedEnd.y.toFixed(2)}"/>` +
    `<line data-role="dimension-line"${attrs} x1="${placement.shiftedStart.x.toFixed(2)}" y1="${placement.shiftedStart.y.toFixed(2)}" x2="${placement.shiftedEnd.x.toFixed(2)}" y2="${placement.shiftedEnd.y.toFixed(2)}"/>` +
    `<line data-role="tick"${attrs} x1="${(placement.shiftedStart.x - tick.x).toFixed(2)}" y1="${(placement.shiftedStart.y - tick.y).toFixed(2)}" x2="${(placement.shiftedStart.x + tick.x).toFixed(2)}" y2="${(placement.shiftedStart.y + tick.y).toFixed(2)}"/>` +
    `<line data-role="tick"${attrs} x1="${(placement.shiftedEnd.x - tick.x).toFixed(2)}" y1="${(placement.shiftedEnd.y - tick.y).toFixed(2)}" x2="${(placement.shiftedEnd.x + tick.x).toFixed(2)}" y2="${(placement.shiftedEnd.y + tick.y).toFixed(2)}"/>` +
    text(
      placement.labelCenter.x,
      placement.labelCenter.y + 4,
      `${fmt(placement.valueMm)} mm`,
      "middle",
      "dimension-label",
      attrs + ` data-label-left="${placement.labelBox.left.toFixed(2)}" data-label-top="${placement.labelBox.top.toFixed(2)}" data-label-right="${placement.labelBox.right.toFixed(2)}" data-label-bottom="${placement.labelBox.bottom.toFixed(2)}"`
    ) +
    `</g>`;
}

function isometricDimensions(
  geometry: CompiledTechnicalViewGeometry,
  dimensions: NonNullable<TechnicalPresentationPackage["dimensions"]>,
  x: number,
  y: number,
  h: number,
  scale: number,
  w: number
): string {
  const plan = planIsometricDimensions({
    guides: geometry.dimensionGuides.map(guide => ({
      axis: guide.axis,
      start: screenPoint(guide.startMm, x, y, h, scale),
      end: screenPoint(guide.endMm, x, y, h, scale)
    })),
    valuesMm: dimensions.primaryMm,
    geometryBox: { left: x, top: y, right: x + w, bottom: y + h },
    viewBox: { width: WIDTH, height: HEIGHT }
  });
  return plan.dimensions.map(renderIsometricDimension).join("");
}

function geometryDerivedSvg(
  pkg: TechnicalPresentationPackage,
  view: TechnicalViewRequest,
  geometry: CompiledTechnicalViewGeometry
): string {
  const dimensions = pkg.dimensions;
  if (!dimensions) throw new Error(`TECHNICAL_VIEW_DIMENSIONS_REQUIRED:${view.id}`);
  const isometric = geometry.projection === "isometric";
  const layout = isometric
    ? { left: 88, right: 88, top: 38, bottom: 82 }
    : { left: MARGIN, right: MARGIN, top: MARGIN, bottom: MARGIN };
  const drawWidth = WIDTH - layout.left - layout.right;
  const drawHeight = HEIGHT - layout.top - layout.bottom;
  const scale = Math.min(
    drawWidth / Math.max(1, geometry.boundsMm.horizontal),
    drawHeight / Math.max(1, geometry.boundsMm.vertical)
  );
  const w = geometry.boundsMm.horizontal * scale;
  const h = geometry.boundsMm.vertical * scale;
  const x = layout.left + (drawWidth - w) / 2;
  const y = layout.top + (drawHeight - h) / 2;
  const pointString = (points: readonly TechnicalPoint2Mm[]): string =>
    points.map(point => {
      const screen = screenPoint(point, x, y, h, scale);
      return `${screen.x.toFixed(2)},${screen.y.toFixed(2)}`;
    }).join(" ");

  let body = "";
  for (const primitive of geometry.primitives) {
    body += `<polygon data-role="primary-geometry" data-primitive-role="${escapeXml(primitive.role)}" data-primitive-id="${escapeXml(primitive.id)}" points="${pointString(primitive.pointsMm)}"/>`;
  }
  for (const opening of geometry.openings) {
    body += `<polygon data-role="opening" data-opening-role="${escapeXml(opening.role)}" data-opening-id="${escapeXml(opening.id)}" data-slot-id="${escapeXml(opening.slotId)}" points="${pointString(opening.pointsMm)}" stroke-dasharray="6 3"/>`;
  }

  if (isometric) {
    body += isometricDimensions(geometry, dimensions, x, y, h, scale, w);
  } else {
    const plane = geometry.projection;
    const [horizontalAxis, verticalAxis] = planeAxes(plane);
    const horizontalMm = dimensions.primaryMm[horizontalAxis];
    const verticalMm = dimensions.primaryMm[verticalAxis];
    const horizontalExtent = plane === "depth-height"
      ? pointExtent(geometry.primitives, role => role !== "front") ?? [0, geometry.boundsMm.horizontal]
      : [0, geometry.boundsMm.horizontal] as const;
    body += horizontalDimension(
      x + horizontalExtent[0] * scale,
      x + horizontalExtent[1] * scale,
      y + h,
      y + h + 36,
      `${fmt(horizontalMm)} mm`
    );
    body += verticalDimension(y + h, y, x, x - 30, `${fmt(verticalMm)} mm`);
  }

  const ownership = isometric
    ? ' data-product-dimensions="true" data-technical-composition="technical-composition/v0.3"'
    : "";
  return svgShell(`${pkg.identity.title} — ${view.label}`, body, "geometry-derived", "scene-geometry", ownership);
}

function isometricSvg(pkg: TechnicalPresentationPackage, view: TechnicalViewRequest): string {
  const dimensions = pkg.dimensions;
  if (!dimensions) throw new Error(`TECHNICAL_VIEW_DIMENSIONS_REQUIRED:${view.id}`);
  const { width: w, height: h, depth: d } = dimensions.primaryMm;
  const points3d: readonly [number, number, number][] = [
    [0, 0, 0], [w, 0, 0], [w, d, 0], [0, d, 0],
    [0, 0, h], [w, 0, h], [w, d, h], [0, d, h]
  ];
  const raw = points3d.map(([px, py, pz]) => [px - py * 0.62, -pz + (px + py) * 0.28] as const);
  const xs = raw.map(point => point[0]);
  const ys = raw.map(point => point[1]);
  const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
  const scale = Math.min((WIDTH - MARGIN * 2) / Math.max(1, maxX - minX), (HEIGHT - MARGIN * 2) / Math.max(1, maxY - minY));
  const project = (index: number): readonly [number, number] => {
    const point = raw[index]!;
    return [MARGIN + (point[0] - minX) * scale, MARGIN + (point[1] - minY) * scale];
  };
  const edges: readonly [number, number][] = [
    [0,1],[1,2],[2,3],[3,0],[4,5],[5,6],[6,7],[7,4],[0,4],[1,5],[2,6],[3,7]
  ];
  let body = "";
  for (const [a, b] of edges) {
    const pa = project(a), pb = project(b);
    body += `<line data-role="envelope-edge" x1="${pa[0].toFixed(2)}" y1="${pa[1].toFixed(2)}" x2="${pb[0].toFixed(2)}" y2="${pb[1].toFixed(2)}"/>`;
  }
  body += text(WIDTH / 2, HEIGHT - 12, `${fmt(w)} × ${fmt(h)} × ${fmt(d)} mm`, "middle", "dimension-summary");
  return svgShell(`${pkg.identity.title} — ${view.label}`, body, "schematic", view.source);
}

function schematicCoverage(view: TechnicalViewRequest): readonly TechnicalViewCoverage[] {
  return view.internalLayout ? ["envelope", "authored-layout"] : ["envelope"];
}

export function renderTechnicalViewSvg(pkg: TechnicalPresentationPackage, viewId: string): TechnicalDiagramAsset {
  const view = pkg.technicalViews.find(candidate => candidate.id === viewId);
  if (!view) throw new Error(`TECHNICAL_VIEW_NOT_FOUND:${viewId}`);
  if (!pkg.dimensions || view.kind === "detail") {
    return {
      viewId,
      status: "external-required",
      fidelity: null,
      source: view.source,
      coverage: [],
      omitted: [],
      mediaType: "image/svg+xml",
      svg: null
    };
  }

  const geometry = pkg.technicalViewGeometry.find(candidate => candidate.viewId === view.id);
  if (geometry) {
    return {
      viewId,
      status: "ready",
      fidelity: "geometry-derived",
      source: "scene-geometry",
      coverage: geometry.coverage,
      omitted: geometry.omitted,
      mediaType: "image/svg+xml",
      svg: geometryDerivedSvg(pkg, view, geometry)
    };
  }
  if (view.source === "scene-geometry") {
    throw new Error(`TECHNICAL_VIEW_GEOMETRY_REQUIRED:${view.id}`);
  }

  if (view.kind === "isometric") {
    return {
      viewId,
      status: "ready",
      fidelity: "schematic",
      source: view.source,
      coverage: ["envelope"],
      omitted: DEFAULT_OMISSIONS,
      mediaType: "image/svg+xml",
      svg: isometricSvg(pkg, view)
    };
  }
  if (!view.plane) throw new Error(`TECHNICAL_VIEW_PLANE_REQUIRED:${viewId}`);
  return {
    viewId,
    status: "ready",
    fidelity: "schematic",
    source: view.source,
    coverage: schematicCoverage(view),
    omitted: DEFAULT_OMISSIONS,
    mediaType: "image/svg+xml",
    svg: schematicOrthographicSvg(pkg, view)
  };
}

export function renderAllTechnicalViews(pkg: TechnicalPresentationPackage): readonly TechnicalDiagramAsset[] {
  return pkg.technicalViews.map(view => renderTechnicalViewSvg(pkg, view.id));
}
