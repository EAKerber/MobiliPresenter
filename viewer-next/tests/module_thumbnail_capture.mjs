import { accessSync, constants, mkdirSync, statSync } from "node:fs";
import { delimiter, join, resolve } from "node:path";
import { spawnSync } from "node:child_process";

const MODULES = ["01", "02", "03", "04", "05", "06", "07"];
const OUT = resolve("artifacts/module-thumbnails");
const BASE_URL = process.argv[2] ?? "http://127.0.0.1:4174/";

function findExecutable(name) {
  if (name.includes("/")) {
    accessSync(name, constants.X_OK);
    return name;
  }
  for (const directory of (process.env.PATH ?? "").split(delimiter)) {
    if (!directory) continue;
    const candidate = join(directory, name);
    try {
      accessSync(candidate, constants.X_OK);
      return candidate;
    } catch {
      // Continue searching PATH.
    }
  }
  return null;
}

function findChrome() {
  for (const candidate of ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"]) {
    const executable = findExecutable(candidate);
    if (executable) return executable;
  }
  throw new Error("CHROME_NOT_FOUND");
}

mkdirSync(OUT, { recursive: true });
const chrome = findChrome();
const suspicious = [];

for (const alias of MODULES) {
  const output = join(OUT, `module-${alias}.png`);
  const url = new URL("thumbnail.html", BASE_URL);
  url.searchParams.set("module", alias);
  const result = spawnSync(chrome, [
    "--headless=new",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-background-networking",
    "--ignore-gpu-blocklist",
    "--enable-webgl",
    "--enable-unsafe-swiftshader",
    "--use-angle=swiftshader",
    "--force-device-scale-factor=1",
    "--window-size=512,512",
    "--default-background-color=00000000",
    "--run-all-compositor-stages-before-draw",
    "--virtual-time-budget=2500",
    `--screenshot=${output}`,
    url.toString()
  ], { encoding: "utf8", timeout: 30_000 });

  if (result.status !== 0) {
    throw new Error(`THUMBNAIL_CAPTURE_FAILED:${alias}:${result.stderr.slice(-2000)}`);
  }
  const size = statSync(output).size;
  if (size < 1_000) suspicious.push(`${alias}:${size}`);
  process.stdout.write(`module-${alias}.png ${size} bytes\n`);
}

if (suspicious.length > 0) {
  throw new Error(`THUMBNAIL_CAPTURE_SUSPICIOUSLY_SMALL:${suspicious.join(",")}`);
}
