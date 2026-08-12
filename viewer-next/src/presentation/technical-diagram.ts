import type {
  CompiledTechnicalViewGeometry,
  TechnicalAxis,
  TechnicalPresentationPackage,
  TechnicalViewCoverage,
  TechnicalViewFidelity,
  TechnicalViewOmission,
  TechnicalViewPlane,
  TechnicalViewRequest
} from "./contracts.js";

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

function svgShell(label: string, body: string, fidelity: TechnicalViewFidelity, source: TechnicalViewRequest["source"]): string {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${WIDTH} ${HEIGHT}" role="img" aria-label="${escapeXml(label)}" data-technical-fidelity="${fidelity}" data-technical-source="${source}">` +
    `<g fill="none" stroke="currentColor" stroke-width="1.5" vector-effect="non-scaling-stroke">${body}</g></svg>`;
}

function text(x: number, y: number, value: string, anchor: "start" | "middle" | "end" = "middle"): string {
  return `<text x="${x.toFixed(2)}" y="${y.toFixed(2)}" fill="currentColor" stroke="none" font-size="12" text-anchor="${anchor}" font-family="sans-serif">${escapeXml(value)}</text>`;
}

function dimensionLine(x1: number, y1: number, x2: number, y2: number, label: string): string {
  const mx = (x1 + x2) / 2;
  const my = (y1 + y2) / 2;
  return `<line x1="${x1.toFixed(2)}" y1="${y1.toFixed(2)}" x2="${x2.toFixed(2)}" y2="${y2.toFixed(2)}"/>` +
    `<line x1="${(x1 - 4).toFixed(2)}" y1="${(y1 - 4).toFixed(2)}" x2="${(x1 + 4).toFixed(2)}" y2="${(y1 + 4).toFixed(2)}"/>` +
    `<line x1="${(x2 - 4).toFixed(2)}" y1="${(y2 - 4).toFixed(2)}" x2="${(x2 + 4).toFixed(2)}" y2="${(y2 + 4).toFixed(2)}"/>` +
    text(mx, my - 6, label);
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
        body += `<line x1="${px.toFixed(2)}" y1="${y.toFixed(2)}" x2="${px.toFixed(2)}" y2="${(y + h).toFixed(2)}"/>`;
      } else if (axisIsVertical && index < layout.segments.length - 1) {
        const py = y + h - cursorMm * scale;
        body += `<line x1="${x.toFixed(2)}" y1="${py.toFixed(2)}" x2="${(x + w).toFixed(2)}" y2="${py.toFixed(2)}"/>`;
      }
      if (axisIsHorizontal) {
        body += text(x + (startMm + segment.spanMm / 2) * scale, y + h + 22, fmt(segment.spanMm));
      } else if (axisIsVertical) {
        body += text(x - 8, y + h - (startMm + segment.spanMm / 2) * scale, fmt(segment.spanMm), "end");
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
          body += `<line x1="${sx.toFixed(2)}" y1="${py.toFixed(2)}" x2="${(sx + sw).toFixed(2)}" y2="${py.toFixed(2)}"/>`;
        }
      }
    }
  }

  body += dimensionLine(x, y + h + 36, x + w, y + h + 36, `${fmt(horizontalMm)} mm`);
  body += dimensionLine(x - 30, y + h, x - 30, y, `${fmt(verticalMm)} mm`);
  return svgShell(`${pkg.identity.title} — ${view.label}`, body, "schematic", view.source);
}

function geometryDerivedSvg(
  pkg: TechnicalPresentationPackage,
  view: TechnicalViewRequest,
  geometry: CompiledTechnicalViewGeometry
): string {
  const dimensions = pkg.dimensions;
  if (!dimensions || view.plane !== "width-height") throw new Error(`TECHNICAL_VIEW_DIMENSIONS_REQUIRED:${view.id}`);
  const drawWidth = WIDTH - MARGIN * 2;
  const drawHeight = HEIGHT - MARGIN * 2;
  const scale = Math.min(
    drawWidth / Math.max(1, geometry.boundsMm.horizontal),
    drawHeight / Math.max(1, geometry.boundsMm.vertical)
  );
  const w = geometry.boundsMm.horizontal * scale;
  const h = geometry.boundsMm.vertical * scale;
  const x = (WIDTH - w) / 2;
  const y = (HEIGHT - h) / 2;
  const pointString = (points: readonly { readonly horizontalMm: number; readonly verticalMm: number }[]): string =>
    points.map(point => `${(x + point.horizontalMm * scale).toFixed(2)},${(y + h - point.verticalMm * scale).toFixed(2)}`).join(" ");

  let body = `<rect data-role="geometry-envelope" x="${x.toFixed(2)}" y="${y.toFixed(2)}" width="${w.toFixed(2)}" height="${h.toFixed(2)}" stroke-dasharray="4 4"/>`;
  for (const primitive of geometry.primitives) {
    body += `<polygon data-primitive-id="${escapeXml(primitive.id)}" data-role="${escapeXml(primitive.role)}" points="${pointString(primitive.pointsMm)}"/>`;
  }
  for (const opening of geometry.openings) {
    body += `<polygon data-opening-id="${escapeXml(opening.id)}" data-slot-id="${escapeXml(opening.slotId)}" data-role="${escapeXml(opening.role)}" points="${pointString(opening.pointsMm)}" stroke-dasharray="6 3"/>`;
  }

  body += dimensionLine(x, y + h + 36, x + w, y + h + 36, `${fmt(dimensions.primaryMm.width)} mm`);
  body += dimensionLine(x - 30, y + h, x - 30, y, `${fmt(dimensions.primaryMm.height)} mm`);
  return svgShell(`${pkg.identity.title} — ${view.label}`, body, "geometry-derived", view.source);
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
    body += `<line x1="${pa[0].toFixed(2)}" y1="${pa[1].toFixed(2)}" x2="${pb[0].toFixed(2)}" y2="${pb[1].toFixed(2)}"/>`;
  }
  body += text(WIDTH / 2, HEIGHT - 12, `${fmt(w)} × ${fmt(h)} × ${fmt(d)} mm`);
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

  if (view.source === "scene-geometry") {
    const geometry = pkg.technicalViewGeometry.find(candidate => candidate.viewId === view.id);
    if (!geometry) throw new Error(`TECHNICAL_VIEW_GEOMETRY_REQUIRED:${view.id}`);
    return {
      viewId,
      status: "ready",
      fidelity: "geometry-derived",
      source: view.source,
      coverage: geometry.coverage,
      omitted: geometry.omitted,
      mediaType: "image/svg+xml",
      svg: geometryDerivedSvg(pkg, view, geometry)
    };
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
