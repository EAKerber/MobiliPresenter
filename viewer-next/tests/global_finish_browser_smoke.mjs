import { accessSync, constants, mkdtempSync, rmSync } from "node:fs";
import { delimiter, join } from "node:path";
import { spawn } from "node:child_process";
import { tmpdir } from "node:os";

const BASE_URL = "http://127.0.0.1:4173/?controls=1";

function findExecutable(name) {
  for (const directory of (process.env.PATH ?? "").split(delimiter)) {
    if (!directory) continue;
    const candidate = join(directory, name);
    try { accessSync(candidate, constants.X_OK); return candidate; } catch {}
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

const delay = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));

async function terminateChrome(child) {
  if (!child || child.exitCode !== null) return;
  child.kill("SIGTERM");
  await delay(300);
  if (child.exitCode === null) child.kill("SIGKILL");
}

async function launchChrome(profileDirectory) {
  const child = spawn(findChrome(), [
    "--headless=new", "--no-sandbox", "--disable-dev-shm-usage", "--disable-background-networking",
    "--ignore-gpu-blocklist", "--enable-webgl", "--enable-unsafe-swiftshader", "--use-angle=swiftshader",
    "--remote-debugging-port=0", `--user-data-dir=${profileDirectory}`, "about:blank"
  ], { stdio: ["ignore", "ignore", "pipe"] });
  child.stderr.setEncoding("utf8");
  let diagnostics = "";
  const websocketUrl = await new Promise((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error(`CDP_READY_TIMEOUT:${diagnostics.slice(-1000)}`)), 15000);
    child.stderr.on("data", chunk => {
      diagnostics += chunk;
      const match = diagnostics.match(/DevTools listening on (ws:\/\/[^\s]+)/);
      if (!match) return;
      clearTimeout(timeout);
      resolve(match[1]);
    });
    child.once("exit", code => reject(new Error(`CHROME_EXITED:${code}:${diagnostics.slice(-1000)}`)));
  });
  return { child, websocketUrl };
}

class CdpClient {
  constructor(websocketUrl) {
    this.nextId = 1;
    this.pending = new Map();
    this.socket = new WebSocket(websocketUrl);
    this.ready = new Promise((resolve, reject) => {
      this.socket.addEventListener("open", resolve, { once: true });
      this.socket.addEventListener("error", reject, { once: true });
    });
    this.socket.addEventListener("message", event => {
      const message = JSON.parse(String(event.data));
      const pending = this.pending.get(message.id);
      if (!pending) return;
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
    const response = new Promise((resolve, reject) => {
      const timeout = setTimeout(() => { this.pending.delete(id); reject(new Error(`CDP_TIMEOUT:${method}`)); }, 20000);
      this.pending.set(id, {
        resolve: value => { clearTimeout(timeout); resolve(value); },
        reject: error => { clearTimeout(timeout); reject(error); },
      });
    });
    this.socket.send(JSON.stringify(payload));
    return response;
  }
  close() { this.socket.close(); }
}

async function evaluate(client, sessionId, expression) {
  const result = await client.send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true }, sessionId);
  if (result.exceptionDetails) throw new Error(`EVALUATE_FAILED:${JSON.stringify(result.exceptionDetails)}`);
  return result.result?.value;
}

async function waitFor(client, sessionId, expression, code) {
  const deadline = Date.now() + 12000;
  while (!(await evaluate(client, sessionId, expression))) {
    if (Date.now() >= deadline) throw new Error(code);
    await delay(75);
  }
}

const profileDirectory = mkdtempSync(join(tmpdir(), "mobilipresenter-finish-smoke-"));
let launched;
let client;
try {
  launched = await launchChrome(profileDirectory);
  client = new CdpClient(launched.websocketUrl);
  const { targetId } = await client.send("Target.createTarget", { url: "about:blank" });
  const { sessionId } = await client.send("Target.attachToTarget", { targetId, flatten: true });
  await client.send("Page.enable", {}, sessionId);
  await client.send("Runtime.enable", {}, sessionId);
  await client.send("Page.navigate", { url: BASE_URL }, sessionId);

  await waitFor(client, sessionId, `(() => {
    const app = document.querySelector("#app");
    return document.readyState === "complete" && app?.dataset.rendererReady === "true"
      && app?.dataset.frameRendered === "true" && Boolean(document.querySelector('[data-viewer-runtime-ui="mounted"]'));
  })()`, "RUNTIME_NOT_READY");

  const initial = await evaluate(client, sessionId, `(() => {
    const app = document.querySelector("#app");
    return { finish: app?.dataset.viewerFurnitureFinishPreset ?? null, module03: app?.dataset.viewerModule03FrontMaterial ?? null };
  })()`);
  if (initial.finish !== "neutral-greige" || initial.module03 !== "front-primary") {
    throw new Error(`INITIAL_FINISH_INVALID:${JSON.stringify(initial)}`);
  }

  await evaluate(client, sessionId, `document.querySelector('[data-configurator-step="finishes"]')?.click()`);
  await waitFor(client, sessionId,
    `Boolean(document.querySelector('[data-stage-panel="finishes"] [data-front-preset="warm-wood"]'))`,
    "FINISH_STAGE_NOT_READY");
  const enabled = await evaluate(client, sessionId, `document.querySelector('[data-front-preset="warm-wood"]')?.disabled === false`);
  if (!enabled) throw new Error("WARM_WOOD_DISABLED_BEFORE_FIRST_CLICK");

  await evaluate(client, sessionId, `document.querySelector('[data-front-preset="warm-wood"]')?.click()`);
  await waitFor(client, sessionId, `(() => {
    const app = document.querySelector("#app");
    return app?.dataset.viewerFurnitureFinishPreset === "warm-wood" && app?.dataset.viewerModule03FrontMaterial === "front-wood";
  })()`, "FIRST_GLOBAL_FINISH_CLICK_DID_NOT_APPLY");

  await evaluate(client, sessionId, `document.querySelector('[data-front-preset="neutral-greige"]')?.click()`);
  await waitFor(client, sessionId, `(() => {
    const app = document.querySelector("#app");
    return app?.dataset.viewerFurnitureFinishPreset === "neutral-greige" && app?.dataset.viewerModule03FrontMaterial === "front-primary";
  })()`, "SECOND_GLOBAL_FINISH_CLICK_DID_NOT_APPLY");

  process.stdout.write(JSON.stringify({ status: "PASS", initial, warmWoodApplied: true, neutralRestored: true }) + "\n");
} finally {
  try { client?.close(); } catch {}
  await terminateChrome(launched?.child);
  rmSync(profileDirectory, { recursive: true, force: true });
}
