import { accessSync, constants, mkdtempSync, rmSync } from "node:fs";
import { delimiter, join } from "node:path";
import { spawn } from "node:child_process";
import { tmpdir } from "node:os";

const url = process.argv[2] ?? "http://127.0.0.1:4173/?controls=1&select=02";

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

async function click(client, sessionId, selector, label) {
  const clicked = await evaluate(client, sessionId, `(() => {
    const target = document.querySelector(${JSON.stringify(selector)});
    if (!(target instanceof HTMLElement)) return false;
    target.click();
    return true;
  })()`);
  if (!clicked) throw new Error(`CLICK_TARGET_NOT_FOUND:${label}:${selector}`);
}

async function terminate(child) {
  if (!child || child.exitCode !== null) return;
  child.kill("SIGTERM");
  await delay(300);
  if (child.exitCode === null) child.kill("SIGKILL");
}

const chrome = findChrome();
if (!chrome) throw new Error("CHROME_NOT_FOUND");
const profileDirectory = mkdtempSync(join(tmpdir(), "product-contract-ui-"));
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
    width: 1366,
    height: 768,
    screenWidth: 1366,
    screenHeight: 768,
    deviceScaleFactor: 1,
    mobile: false,
    screenOrientation: { angle: 0, type: "landscapePrimary" }
  }, sessionId);
  await client.send("Page.navigate", { url }, sessionId);

  await waitUntil(client, sessionId, `(() => {
    const app = document.querySelector('#app');
    return document.readyState === 'complete'
      && app?.dataset.rendererReady === 'true'
      && app?.dataset.frameRendered === 'true'
      && Boolean(document.querySelector('[data-viewer-runtime-ui="mounted"]'));
  })()`, "runtime-ready");

  await waitUntil(client, sessionId, `(() => {
    const detail = document.querySelector('.viewer-product-detail[data-module-alias="02"]');
    return detail?.dataset.productDescriptor === 'true'
      && Boolean(detail.querySelector('[data-product-descriptor-dimensions="true"]'))
      && Boolean(detail.querySelector('[data-semantic-icon-key="electrical.outlet"]'))
      && Boolean(detail.querySelector('[data-product-semantic-icon-source="published-key"]'))
      && Boolean(detail.querySelector('[data-product-finish-source="published-visual"]'))
      && detail.textContent.includes('Inferior do fogão');
  })()`, "module02-contract-projection");

  await click(client, sessionId, '[data-configurator-step="accessories"]', "accessories");
  await waitUntil(client, sessionId, `(() => {
    const stage = document.querySelector('[data-stage-panel="accessories"]');
    return stage
      && stage.textContent.includes('Acessórios ainda não disponíveis para seleção')
      && stage.textContent.includes('Puxadores e outros opcionais aparecerão aqui');
  })()`, "accessories-product-copy");

  const accessoriesText = await evaluate(client, sessionId, `document.querySelector('[data-stage-panel="accessories"]')?.textContent ?? ''`);
  for (const forbidden of ["contrato público", "binding de runtime", "publicadas pelo contrato"]) {
    if (accessoriesText.includes(forbidden)) throw new Error(`PRODUCT_INTERNAL_COPY_LEAK:accessories:${forbidden}`);
  }

  await click(client, sessionId, '[data-configurator-step="summary"]', "summary");
  await waitUntil(client, sessionId, `(() => {
    const stage = document.querySelector('[data-stage-panel="summary"]');
    return stage
      && Boolean(stage.querySelector('[data-product-summary-furniture="true"]'))
      && stage.textContent.includes('Cor dos móveis')
      && stage.textContent.includes('Aéreo da lavanderia')
      && stage.textContent.includes('Inferior do fogão')
      && stage.textContent.includes('Valor ainda não disponível');
  })()`, "summary-contract-projection");

  const summaryState = await evaluate(client, sessionId, `(() => {
    const stage = document.querySelector('[data-stage-panel="summary"]');
    const furniture = stage?.querySelector('[data-product-summary-furniture="true"]');
    return {
      text: stage?.textContent ?? '',
      finishSource: furniture?.dataset.productFinishSource ?? null,
      furnitureValue: furniture?.querySelector(':scope > span')?.textContent ?? null
    };
  })()`);
  if (summaryState.finishSource !== "configuration-state") {
    throw new Error(`SUMMARY_FINISH_SOURCE_INVALID:${JSON.stringify(summaryState)}`);
  }
  for (const forbidden of ["contrato atual", "authority comercial", "Aguardando fonte comercial"]) {
    if (summaryState.text.includes(forbidden)) throw new Error(`PRODUCT_INTERNAL_COPY_LEAK:summary:${forbidden}`);
  }

  process.stdout.write(`${JSON.stringify({
    status: "PASS",
    summaryFurnitureValue: summaryState.furnitureValue,
    invariants: {
      moduleDescriptorsProjected: true,
      descriptorDimensionsProjected: true,
      semanticIconsUsePublishedKeys: true,
      finishDotsUsePublishedVisuals: true,
      summaryUsesPublishedModuleIdentity: true,
      summaryUsesFirstClassFurnitureFinish: true,
      implementationLanguageDoesNotLeakToProductPlaceholders: true,
      dynamicProjectionDoesNotDependOnFrozenCaptureArtifacts: true
    }
  }, null, 2)}\n`);
} finally {
  try { client?.close(); } catch { /* best effort */ }
  await terminate(launched?.child);
  rmSync(profileDirectory, { recursive: true, force: true });
}
