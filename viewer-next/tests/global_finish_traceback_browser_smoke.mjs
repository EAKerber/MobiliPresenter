import { accessSync, constants, mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { delimiter, join } from "node:path";
import { spawn } from "node:child_process";
import { tmpdir } from "node:os";

const LEGACY_FRONT = "01:neutral-greige,02:neutral-greige,03:neutral-greige,04:neutral-greige,05:neutral-greige,06:neutral-greige,07:neutral-greige";
const BASE_URL = `http://127.0.0.1:4173/?controls=1&front=${encodeURIComponent(LEGACY_FRONT)}`;
const OUT_DIR = "artifacts/global-finish-traceback";
const TRACE_PATH = `${OUT_DIR}/trace.json`;

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
      const timeout = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`CDP_TIMEOUT:${method}`));
      }, 20000);
      this.pending.set(id, {
        resolve: value => { clearTimeout(timeout); resolve(value); },
        reject: error => { clearTimeout(timeout); reject(error); }
      });
    });
    this.socket.send(JSON.stringify(payload));
    return response;
  }

  close() { this.socket.close(); }
}

async function evaluate(client, sessionId, expression) {
  const result = await client.send("Runtime.evaluate", {
    expression,
    returnByValue: true,
    awaitPromise: true
  }, sessionId);
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

async function waitReady(client, sessionId) {
  await waitFor(client, sessionId, `(() => {
    const app = document.querySelector("#app");
    return document.readyState === "complete"
      && app?.dataset.rendererReady === "true"
      && app?.dataset.frameRendered === "true"
      && Boolean(document.querySelector('[data-viewer-runtime-ui="mounted"]'));
  })()`, "RUNTIME_NOT_READY");
}

async function snapshot(client, sessionId, id) {
  return evaluate(client, sessionId, `(() => {
    const app = document.querySelector("#app");
    return {
      id: ${JSON.stringify(id)},
      search: window.location.search,
      finish: app?.dataset.viewerFurnitureFinishPreset ?? null,
      module03: app?.dataset.viewerModule03FrontMaterial ?? null
    };
  })()`);
}

async function openFinishes(client, sessionId) {
  await evaluate(client, sessionId, `document.querySelector('[data-configurator-step="finishes"]')?.click()`);
  await waitFor(
    client,
    sessionId,
    `Boolean(document.querySelector('[data-stage-panel="finishes"] [data-front-preset="warm-wood"]'))`,
    "FINISH_STAGE_NOT_READY"
  );
}

async function clickWarm(client, sessionId) {
  await evaluate(client, sessionId, `document.querySelector('[data-front-preset="warm-wood"]')?.click()`);
  await waitFor(
    client,
    sessionId,
    `document.querySelector("#app")?.dataset.viewerFurnitureFinishPreset === "warm-wood"`,
    "GLOBAL_FINISH_STATE_DID_NOT_CHANGE"
  );
}

async function clickReset(client, sessionId) {
  const clicked = await evaluate(client, sessionId, `(() => {
    const button = [...document.querySelectorAll("button")]
      .find(candidate => candidate.textContent?.trim() === "Restaurar");
    button?.click();
    return Boolean(button);
  })()`);
  if (!clicked) throw new Error("RESET_BUTTON_NOT_FOUND");
  await waitFor(client, sessionId, `(() => {
    const app = document.querySelector("#app");
    return app?.dataset.viewerFurnitureFinishPreset === "neutral-greige"
      && app?.dataset.viewerModule03FrontMaterial === "front-primary";
  })()`, "RESET_DID_NOT_RETURN_DEFAULT_STATE");
}

const profileDirectory = mkdtempSync(join(tmpdir(), "mobilipresenter-finish-traceback-"));
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
  await waitReady(client, sessionId);

  const initial = await snapshot(client, sessionId, "legacy-load");
  if (!initial.search.includes("front=") || initial.finish !== "neutral-greige" || initial.module03 !== "front-primary") {
    throw new Error(`LEGACY_INITIAL_STATE_INVALID:${JSON.stringify(initial)}`);
  }

  await openFinishes(client, sessionId);
  await clickWarm(client, sessionId);
  const firstWarm = await snapshot(client, sessionId, "legacy-first-warm");
  if (firstWarm.finish !== "warm-wood" || firstWarm.module03 !== "front-primary") {
    throw new Error(`TRACE_SIGNATURE_NOT_REPRODUCED_BEFORE_RESET:${JSON.stringify(firstWarm)}`);
  }

  await clickReset(client, sessionId);
  const afterReset = await snapshot(client, sessionId, "after-reset");
  if (!afterReset.search.includes("front=")) {
    throw new Error(`RESET_UNEXPECTEDLY_MIGRATED_LEGACY_URL:${JSON.stringify(afterReset)}`);
  }

  await openFinishes(client, sessionId);
  await clickWarm(client, sessionId);
  await waitFor(
    client,
    sessionId,
    `document.querySelector("#app")?.dataset.viewerModule03FrontMaterial === "front-wood"`,
    "GLOBAL_FINISH_DID_NOT_APPLY_AFTER_RESET"
  );
  const warmAfterReset = await snapshot(client, sessionId, "warm-after-reset");

  await client.send("Page.reload", {}, sessionId);
  await waitReady(client, sessionId);
  const reloaded = await snapshot(client, sessionId, "reload-from-legacy-url");
  await openFinishes(client, sessionId);
  await clickWarm(client, sessionId);
  const warmAfterReload = await snapshot(client, sessionId, "warm-after-reload");
  if (warmAfterReload.finish !== "warm-wood" || warmAfterReload.module03 !== "front-primary") {
    throw new Error(`TRACE_SIGNATURE_NOT_REPRODUCED_AFTER_RELOAD:${JSON.stringify(warmAfterReload)}`);
  }

  const trace = {
    status: "PASS",
    classification: "KNOWN_BUG_REPRODUCED",
    hypothesis: "legacy-front-query-local-overrides-shadow-global-finish",
    legacyFront: LEGACY_FRONT,
    initial,
    firstWarm,
    afterReset,
    warmAfterReset,
    reloaded,
    warmAfterReload,
    signature: {
      firstClickChangesGlobalStateButNotModule03: true,
      resetClearsInMemoryShadowing: true,
      legacyUrlSurvivesReset: true,
      reloadRestoresShadowing: true
    }
  };

  mkdirSync(OUT_DIR, { recursive: true });
  writeFileSync(TRACE_PATH, JSON.stringify(trace, null, 2) + "\n", "utf8");
  process.stdout.write(JSON.stringify(trace, null, 2) + "\n");
} finally {
  try { client?.close(); } catch {}
  await terminateChrome(launched?.child);
  rmSync(profileDirectory, { recursive: true, force: true });
}
