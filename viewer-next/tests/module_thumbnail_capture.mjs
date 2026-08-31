import { mkdirSync, rmSync, statSync } from "node:fs";
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
    "--out-dir", OUT
  ], { encoding: "utf8", timeout: 45_000 });

  if (result.status !== 0) {
    throw new Error(`THUMBNAIL_CAPTURE_FAILED:${alias}:${result.stderr.slice(-3000)}`);
  }

  const output = join(OUT, `${name}.png`);
  const size = statSync(output).size;
  if (size < 5_000) throw new Error(`THUMBNAIL_CAPTURE_SUSPICIOUSLY_SMALL:${alias}:${size}`);

  rmSync(join(OUT, `${name}.html`), { force: true });
  rmSync(join(OUT, `${name}.metrics.json`), { force: true });
  process.stdout.write(`${name}.png ${size} bytes\n`);
}
