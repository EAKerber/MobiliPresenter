import { accessSync, constants, mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { delimiter, join, resolve } from "node:path";
import { spawn } from "node:child_process";
import { tmpdir } from "node:os";

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

function delay(milliseconds) {
  return new Promise(resolveDelay => setTimeout(resolveDelay, milliseconds));
}

async function launchChrome(chrome, profileDirectory) {
  const child = spawn(chrome, [
    "--headless=new",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-background-networking",
    "--ignore-gpu-blocklist",
    "--enable-webgl",
    "--enable-unsafe-swiftshader",
    "--use-angle=swiftshader",
    "--force-device-scale-factor=1",
    "--remote-debugging-port=0",
    `--user-data-dir=${profileDirectory}`,
    "about:blank"
  ], { stdio: ["ignore", "ignore", "pipe"] });
  child.stderr.setEncoding("utf8");
  let diagnostics = "";
  const websocketUrl = await new Promise((resolveUrl, reject) => {
    const timeout = setTimeout(() => reject(new Error(`CHROME_DEBUG_TIMEOUT:${diagnostics.slice(-1500)}`)), 15_000);
    child.stderr.on("data", chunk => {
      diagnostics += chunk;
      const match = diagnostics.match(/DevTools listening on (ws:\/\/[^\s]+)/);
      if (!match) return;
      clearTimeout(timeout);
      resolveUrl(match[1]);
    });
    child.once("exit", code => {
      clearTimeout(timeout);
      reject(new Error(`CHROME_EXITED:${code}:${diagnostics.slice(-1500)}`));
    });
  });
  return { child, websocketUrl };
}

class CdpClient {
  constructor(websocketUrl) {
    this.nextId = 1;
    this.pending = new Map();
    this.socket = new WebSocket(websocketUrl);
    this.ready = new Promise((resolveReady, rejectReady) => {
      this.socket.addEventListener("open", resolveReady, { once: true });
      this.socket.addEventListener("error", rejectReady, { once: true });
    });
    this.socket.addEventListener("message", event => {
      const message = JSON.parse(String(event.data));
      if (!message.id || !this.pending.has(message.id)) return;
      const pending = this.pending.get(message.id);
      this.pending.delete(message.id);
      if (message.error) pending.reject(new Error(`${message.error.code}:${message.error.message}`));
      else pending.resolve(message.result ?? {});
    });
  }

  async send(method, params = {}, sessionId = undefined) {
    await this.ready;
    const id = this.nextId++;
    const payload = { id, method, params };
    if (sessionId) payload.sessionId = sessionId;
    const response = new Promise((resolveCommand, rejectCommand) => {
      const timeout = setTimeout(() => {
        this.pending.delete(id);
        rejectCommand(new Error(`CDP_TIMEOUT:${method}`));
      }, 20_000);
      this.pending.set(id, {
        resolve: value => { clearTimeout(timeout); resolveCommand(value); },
        reject: error => { clearTimeout(timeout); rejectCommand(error); }
      });
    });
    this.socket.send(JSON.stringify(payload));
    return response;
  }

  close() {
    this.socket.close();
  }
}

async function evaluate(client, sessionId, expression) {
  const result = await client.send("Runtime.evaluate", {
    expression,
    returnByValue: true,
    awaitPromise: true
  }, sessionId);
  if (result.exceptionDetails) throw new Error(`RUNTIME_EVALUATE_FAILED:${JSON.stringify(result.exceptionDetails)}`);
  return result.result?.value;
}

async function captureModule(chrome, alias) {
  const profile = mkdtempSync(join(tmpdir(), `module-thumb-${alias}-`));
  let launched;
  let client;
  try {
    launched = await launchChrome(chrome, profile);
    client = new CdpClient(launched.websocketUrl);
    const { targetId } = await client.send("Target.createTarget", { url: "about:blank" });
    const { sessionId } = await client.send("Target.attachToTarget", { targetId, flatten: true });
    await client.send("Page.enable", {}, sessionId);
    await client.send("Runtime.enable", {}, sessionId);
    await client.send("Emulation.setDeviceMetricsOverride", {
      width: 512,
      height: 512,
      screenWidth: 512,
      screenHeight: 512,
      deviceScaleFactor: 1,
      mobile: false
    }, sessionId);

    const url = new URL("thumbnail.html", BASE_URL);
    url.searchParams.set("module", alias);
    await client.send("Page.navigate", { url: url.toString() }, sessionId);

    const deadline = Date.now() + 20_000;
    while (true) {
      const ready = await evaluate(client, sessionId, `(() => {
        const app = document.querySelector('#app');
        return document.readyState === 'complete'
          && app?.dataset.rendererReady === 'true'
          && app?.dataset.frameRendered === 'true'
          && Boolean(app?.querySelector('canvas'));
      })()`);
      if (ready) break;
      if (Date.now() >= deadline) {
        const html = await evaluate(client, sessionId, "document.documentElement.outerHTML");
        throw new Error(`THUMBNAIL_RENDER_TIMEOUT:${alias}:${String(html).slice(-1500)}`);
      }
      await delay(100);
    }

    await delay(100);
    const dataUrl = await evaluate(client, sessionId, `document.querySelector('#app canvas').toDataURL('image/png')`);
    if (typeof dataUrl !== "string" || !dataUrl.startsWith("data:image/png;base64,")) {
      throw new Error(`THUMBNAIL_DATA_URL_INVALID:${alias}`);
    }
    const png = Buffer.from(dataUrl.slice("data:image/png;base64,".length), "base64");
    if (png.byteLength < 1_000) throw new Error(`THUMBNAIL_CAPTURE_SUSPICIOUSLY_SMALL:${alias}:${png.byteLength}`);
    writeFileSync(join(OUT, `module-${alias}.png`), png);
    process.stdout.write(`module-${alias}.png ${png.byteLength} bytes\n`);
  } finally {
    try { client?.close(); } catch {}
    if (launched?.child && launched.child.exitCode === null) launched.child.kill("SIGTERM");
    await delay(100);
    rmSync(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 100 });
  }
}

mkdirSync(OUT, { recursive: true });
const chrome = findChrome();
for (const alias of MODULES) await captureModule(chrome, alias);
