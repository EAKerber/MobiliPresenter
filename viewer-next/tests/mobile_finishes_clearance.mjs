import { accessSync, constants, mkdtempSync, rmSync } from "node:fs";
import { delimiter, join } from "node:path";
import { spawn } from "node:child_process";
import { tmpdir } from "node:os";

const url = process.argv[2] ?? "http://127.0.0.1:4173/?controls=1";

function delay(milliseconds) {
  return new Promise(resolve => setTimeout(resolve, milliseconds));
}

function findExecutable(name) {
  for (const directory of (process.env.PATH ?? "").split(delimiter)) {
    if (!directory) continue;
    const candidate = join(directory, name);
    try {
      accessSync(candidate, constants.X_OK);
      return candidate;
    } catch {
      // Keep searching.
    }
  }
  return null;
}

function findChrome() {
  for (const candidate of ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"]) {
    const executable = findExecutable(candidate);
    if (executable) return executable;
  }
  return null;
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
  const websocketUrl = await new Promise((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error(`CHROME_ENDPOINT_TIMEOUT:${diagnostics.slice(-1500)}`)), 15_000);
    child.stderr.on("data", chunk => {
      diagnostics += chunk;
      const match = diagnostics.match(/DevTools listening on (ws:\/\/[^\s]+)/);
      if (!match) return;
      clearTimeout(timeout);
      resolve(match[1]);
    });
    child.once("exit", code => {
      clearTimeout(timeout);
      reject(new Error(`CHROME_EXITED:${code}:${diagnostics.slice(-1500)}`));
    });
    child.once("error", reject);
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
    const response = new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`CDP_TIMEOUT:${method}`));
      }, 20_000);
      this.pending.set(id, {
        resolve: value => {
          clearTimeout(timeout);
          resolve(value);
        },
        reject: error => {
          clearTimeout(timeout);
          reject(error);
        }
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

async function waitUntil(client, sessionId, expression, label, timeoutMs = 20_000) {
  const deadline = Date.now() + timeoutMs;
  while (!(await evaluate(client, sessionId, expression))) {
    if (Date.now() >= deadline) throw new Error(`WAIT_TIMEOUT:${label}`);
    await delay(100);
  }
}

async function terminate(child) {
  if (!child || child.exitCode !== null) return;
  child.kill("SIGTERM");
  await delay(300);
  if (child.exitCode === null) child.kill("SIGKILL");
}

const chrome = findChrome();
if (!chrome) throw new Error("CHROME_NOT_FOUND");
const profileDirectory = mkdtempSync(join(tmpdir(), "finishes-clearance-"));
let launched;
let client;

try {
  launched = await launchChrome(chrome, profileDirectory);
  client = new CdpClient(launched.websocketUrl);
  const { targetId } = await client.send("Target.createTarget", { url: "about:blank" });
  const { sessionId } = await client.send("Target.attachToTarget", { targetId, flatten: true });
  await client.send("Page.enable", {}, sessionId);
  await client.send("Runtime.enable", {}, sessionId);
  await client.send("Emulation.setDeviceMetricsOverride", {
    width: 390,
    height: 844,
    screenWidth: 390,
    screenHeight: 844,
    deviceScaleFactor: 1,
    mobile: true,
    screenOrientation: { angle: 0, type: "portraitPrimary" }
  }, sessionId);
  await client.send("Page.navigate", { url }, sessionId);

  await waitUntil(client, sessionId, `(() => {
    const app = document.querySelector('#app');
    return document.readyState === 'complete'
      && app?.dataset.rendererReady === 'true'
      && app?.dataset.frameRendered === 'true'
      && Boolean(document.querySelector('[data-viewer-runtime-ui="mounted"]'));
  })()`, "runtime-ready");

  const clicked = await evaluate(client, sessionId, `(() => {
    const button = document.querySelector('[data-configurator-step="finishes"]');
    if (!(button instanceof HTMLElement)) return false;
    button.click();
    return true;
  })()`);
  if (!clicked) throw new Error("FINISHES_NAV_NOT_FOUND");

  await waitUntil(client, sessionId, `(() => {
    const ui = document.querySelector('[data-viewer-runtime-ui="mounted"]');
    return ui?.dataset.currentStep === 'finishes'
      && Boolean(document.querySelector('[data-stage-panel="finishes"]'))
      && Boolean(document.querySelector('[data-stone-preset="graphite-speckled"][data-product-stone-enhanced="true"]'));
  })()`, "finishes-ready");

  await evaluate(client, sessionId, `(() => {
    const scroller = document.querySelector('.viewer-configurator__stage-content');
    if (!(scroller instanceof HTMLElement)) return false;
    scroller.scrollTop = scroller.scrollHeight;
    return true;
  })()`);
  await delay(150);

  const metrics = await evaluate(client, sessionId, `(() => {
    const rect = element => {
      const value = element.getBoundingClientRect();
      return { top: value.top, bottom: value.bottom, height: value.height };
    };
    const scroller = document.querySelector('.viewer-configurator__stage-content');
    const target = document.querySelector('[data-stone-preset="graphite-speckled"]');
    const actions = document.querySelector('.viewer-configurator__actions');
    const stage = document.querySelector('.viewer-configurator__stage');
    if (!(scroller instanceof HTMLElement) || !(target instanceof HTMLElement) || !(actions instanceof HTMLElement) || !(stage instanceof HTMLElement)) {
      return null;
    }
    const targetRect = rect(target);
    const actionsRect = rect(actions);
    const stageRect = rect(stage);
    return {
      target: targetRect,
      actions: actionsRect,
      stage: stageRect,
      scrollTop: scroller.scrollTop,
      scrollHeight: scroller.scrollHeight,
      clientHeight: scroller.clientHeight,
      maxScrollTop: Math.max(0, scroller.scrollHeight - scroller.clientHeight),
      clearancePx: actionsRect.top - targetRect.bottom,
      stageActionGapPx: actionsRect.top - stageRect.bottom,
      actionVariable: getComputedStyle(document.documentElement).getPropertyValue('--ui-actions-height').trim()
    };
  })()`);

  if (!metrics) throw new Error("FINISHES_CLEARANCE_METRICS_UNAVAILABLE");
  if (Math.abs(metrics.scrollTop - metrics.maxScrollTop) > 1) {
    throw new Error(`FINISHES_DID_NOT_REACH_SCROLL_END:${JSON.stringify(metrics)}`);
  }
  if (metrics.clearancePx < 12) {
    throw new Error(`FINISHES_CONTENT_OBSCURED_BY_ACTIONS:${JSON.stringify(metrics)}`);
  }
  if (Math.abs(metrics.stageActionGapPx) > 1) {
    throw new Error(`FINISHES_STAGE_ACTION_GEOMETRY_MISMATCH:${JSON.stringify(metrics)}`);
  }
  if (metrics.actions.height < 63 || metrics.actionVariable !== "64px") {
    throw new Error(`FINISHES_ACTION_RESERVATION_MISMATCH:${JSON.stringify(metrics)}`);
  }

  process.stdout.write(`${JSON.stringify({ status: "PASS", ...metrics }, null, 2)}\n`);
} finally {
  try { client?.close(); } catch { /* best effort */ }
  await terminate(launched?.child);
  rmSync(profileDirectory, { recursive: true, force: true });
}
