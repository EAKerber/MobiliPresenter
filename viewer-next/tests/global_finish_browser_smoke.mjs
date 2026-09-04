import { accessSync, constants, mkdtempSync, rmSync } from "node:fs";
import { delimiter, join } from "node:path";
import { spawn } from "node:child_process";
import { tmpdir } from "node:os";

const BASE_URL = "http://127.0.0.1:4173/?controls=1";
const ALL_NEUTRAL = "01:neutral-greige,02:neutral-greige,03:neutral-greige,04:neutral-greige,05:neutral-greige,06:neutral-greige,07:neutral-greige";

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

async function waitRuntime(client, sessionId, extraExpression = "true", code = "RUNTIME_NOT_READY") {
  await waitFor(client, sessionId, `(() => {
    const app = document.querySelector("#app");
    return document.readyState === "complete"
      && app?.dataset.rendererReady === "true"
      && app?.dataset.frameRendered === "true"
      && Boolean(document.querySelector('[data-viewer-runtime-ui="mounted"]'))
      && (${extraExpression});
  })()`, code);
}

async function navigate(client, sessionId, url, extraExpression = "true", code = "NAVIGATION_NOT_READY") {
  await client.send("Page.navigate", { url }, sessionId);
  await waitRuntime(client, sessionId, extraExpression, code);
}

async function snapshot(client, sessionId) {
  return evaluate(client, sessionId, `(() => {
    const app = document.querySelector("#app");
    const params = new URLSearchParams(window.location.search);
    return {
      search: window.location.search,
      finishQuery: params.get("finish"),
      frontQuery: params.get("front"),
      finish: app?.dataset.viewerFurnitureFinishPreset ?? null,
      module03: app?.dataset.viewerModule03FrontMaterial ?? null,
      migration: app?.dataset.viewerQueryMigration ?? null
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

async function chooseFinish(client, sessionId, presetId, expectedModule03) {
  await openFinishes(client, sessionId);
  const enabled = await evaluate(
    client,
    sessionId,
    `document.querySelector('[data-front-preset="${presetId}"]')?.disabled === false`
  );
  if (!enabled) throw new Error(`FINISH_DISABLED:${presetId}`);
  await evaluate(client, sessionId, `document.querySelector('[data-front-preset="${presetId}"]')?.click()`);
  await waitFor(client, sessionId, `(() => {
    const app = document.querySelector("#app");
    return app?.dataset.viewerFurnitureFinishPreset === "${presetId}"
      && app?.dataset.viewerModule03FrontMaterial === "${expectedModule03}";
  })()`, `FINISH_DID_NOT_APPLY:${presetId}:${expectedModule03}`);
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

  await navigate(
    client,
    sessionId,
    BASE_URL,
    `window.location.search === "?controls=1"`,
    "CLEAN_RUNTIME_NOT_READY"
  );
  const cleanInitial = await snapshot(client, sessionId);
  if (cleanInitial.finish !== "neutral-greige" || cleanInitial.module03 !== "front-primary") {
    throw new Error(`INITIAL_FINISH_INVALID:${JSON.stringify(cleanInitial)}`);
  }
  if (cleanInitial.migration !== "none") throw new Error(`CLEAN_QUERY_MIGRATED:${JSON.stringify(cleanInitial)}`);
  await chooseFinish(client, sessionId, "warm-wood", "front-wood");
  await chooseFinish(client, sessionId, "neutral-greige", "front-primary");

  const legacyUrl = `${BASE_URL}&front=${encodeURIComponent(ALL_NEUTRAL)}`;
  await navigate(
    client,
    sessionId,
    legacyUrl,
    `(() => {
      const params = new URLSearchParams(window.location.search);
      return params.get("finish") === "neutral-greige" && !params.has("front");
    })()`,
    "LEGACY_UNIFORM_QUERY_NOT_MIGRATED"
  );
  const migratedInitial = await snapshot(client, sessionId);
  if (
    migratedInitial.migration !== "legacy-uniform-front-to-finish"
    || migratedInitial.finishQuery !== "neutral-greige"
    || migratedInitial.frontQuery !== null
    || migratedInitial.finish !== "neutral-greige"
    || migratedInitial.module03 !== "front-primary"
  ) {
    throw new Error(`LEGACY_MIGRATION_INVALID:${JSON.stringify(migratedInitial)}`);
  }

  await chooseFinish(client, sessionId, "warm-wood", "front-wood");
  const migratedWarm = await snapshot(client, sessionId);

  await evaluate(client, sessionId, `window.__MOBILIPRESENTER_VIEWER__?.resetConfiguration()`);
  await waitFor(client, sessionId, `(() => {
    const app = document.querySelector("#app");
    const params = new URLSearchParams(window.location.search);
    return app?.dataset.viewerFurnitureFinishPreset === "neutral-greige"
      && app?.dataset.viewerModule03FrontMaterial === "front-primary"
      && params.get("finish") === "neutral-greige"
      && !params.has("front");
  })()`, "RESET_AFTER_MIGRATION_INVALID");
  const afterReset = await snapshot(client, sessionId);
  await chooseFinish(client, sessionId, "warm-wood", "front-wood");

  await client.send("Page.reload", {}, sessionId);
  await waitRuntime(client, sessionId, `(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get("finish") === "neutral-greige" && !params.has("front");
  })()`, "MIGRATED_RELOAD_NOT_READY");
  const afterReload = await snapshot(client, sessionId);
  await chooseFinish(client, sessionId, "warm-wood", "front-wood");
  const warmAfterReload = await snapshot(client, sessionId);

  await navigate(
    client,
    sessionId,
    `${BASE_URL}&front=03%3Aneutral-greige`,
    `new URLSearchParams(window.location.search).get("front") === "03:neutral-greige"`,
    "PARTIAL_OVERRIDE_NOT_READY"
  );
  const partialInitial = await snapshot(client, sessionId);
  if (partialInitial.migration !== "none" || partialInitial.finishQuery !== null) {
    throw new Error(`PARTIAL_OVERRIDE_MIGRATED:${JSON.stringify(partialInitial)}`);
  }
  await chooseFinish(client, sessionId, "warm-wood", "front-primary");
  const partialWarm = await snapshot(client, sessionId);

  const mixed = "01:warm-wood,02:warm-wood,03:neutral-greige,04:warm-wood,05:warm-wood,06:warm-wood,07:warm-wood";
  await navigate(
    client,
    sessionId,
    `${BASE_URL}&finish=warm-wood&front=${encodeURIComponent(mixed)}`,
    `(() => {
      const params = new URLSearchParams(window.location.search);
      return params.get("finish") === "warm-wood" && params.has("front");
    })()`,
    "MIXED_OVERRIDE_NOT_READY"
  );
  const mixedInitial = await snapshot(client, sessionId);
  if (
    mixedInitial.migration !== "none"
    || mixedInitial.finish !== "warm-wood"
    || mixedInitial.module03 !== "front-primary"
  ) {
    throw new Error(`MIXED_OVERRIDE_SEMANTICS_INVALID:${JSON.stringify(mixedInitial)}`);
  }

  process.stdout.write(JSON.stringify({
    status: "PASS",
    cleanInitial,
    migratedInitial,
    migratedWarm,
    afterReset,
    afterReload,
    warmAfterReload,
    partialInitial,
    partialWarm,
    mixedInitial,
    invariants: {
      cleanGlobalPathStillWorks: true,
      uniformLegacyStateMigratesToCanonicalFinish: true,
      migratedUrlDropsFrontOverrides: true,
      firstGlobalChoiceWorksAfterMigration: true,
      resetCannotRestoreLegacyFrontOverrides: true,
      reloadCannotRestoreLegacyFrontOverrides: true,
      partialOverrideRemainsLocal: true,
      mixedOverrideRemainsLocal: true
    }
  }) + "\n");
} finally {
  try { client?.close(); } catch {}
  await terminateChrome(launched?.child);
  rmSync(profileDirectory, { recursive: true, force: true });
}
