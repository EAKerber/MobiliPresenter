import { mkdirSync, readFileSync, rmSync, statSync } from "node:fs";
import { join, resolve } from "node:path";
import { spawnSync } from "node:child_process";

const MODULES = ["01", "02", "03", "04", "05", "06", "07"];
const OUT = resolve("artifacts/module-thumbnails");
const BASE_URL = process.argv[2] ?? "http://127.0.0.1:4174/";
const CAPTURE_SCRIPT = resolve("tests/chrome_viewport_capture.mjs");

mkdirSync(OUT, { recursive: true });

for (const alias of MODULES) {
  const url = new URL("thumbnail.html", BASE_URL);
  url.searchParams.set("module", alias);
  const name = `module-${alias}`;

  const result = spawnSync(process.execPath, [
    CAPTURE_SCRIPT,
    "--url", url.toString(),
    "--name", name,
    "--width", "512",
    "--height", "512",
    "--out-dir", OUT,
    "--canvas-png"
  ], { encoding: "utf8", timeout: 45_000 });

  if (result.status !== 0) {
    throw new Error(`THUMBNAIL_CAPTURE_FAILED:${alias}:${result.stderr.slice(-3000)}`);
  }

  const htmlPath = join(OUT, `${name}.html`);
  const html = readFileSync(htmlPath, "utf8");
  const errorMatch = html.match(/data-thumbnail-error="([^"]*)"/);
  if (!errorMatch || errorMatch[1] !== "none") {
    throw new Error(`THUMBNAIL_PAGE_ERROR:${alias}:${errorMatch?.[1] ?? "missing-error-marker"}`);
  }
  for (const marker of [
    'data-thumbnail-renderer="viewer-composition-three-webgl2"',
    'data-thumbnail-scene-policy="current-scene-isolated-entity-visibility-v2"',
    'data-thumbnail-camera-policy="current-fixed-camera-aspect-then-crop-v1"',
    'data-thumbnail-mask-policy="same-renderer-geometry-mask-v1"',
    'data-thumbnail-background="transparent"'
  ]) {
    if (!html.includes(marker)) throw new Error(`THUMBNAIL_POLICY_MISSING:${alias}:${marker}`);
  }

  const output = join(OUT, `${name}.png`);
  const size = statSync(output).size;
  if (size < 5_000) throw new Error(`THUMBNAIL_CAPTURE_SUSPICIOUSLY_SMALL:${alias}:${size}`);

  rmSync(htmlPath, { force: true });
  rmSync(join(OUT, `${name}.metrics.json`), { force: true });
  process.stdout.write(`${name}.png ${size} bytes\n`);
}
