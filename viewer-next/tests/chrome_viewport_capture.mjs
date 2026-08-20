import { accessSync, constants, mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { delimiter, join, resolve } from "node:path";
import { spawn } from "node:child_process";
import { tmpdir } from "node:os";

function parseArgs(argv) {
  const options = { screenshot: true };
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (token === "--no-screenshot") {
      options.screenshot = false;
      continue;
    }
    if (!token.startsWith("--")) {
      throw new Error(`unexpected argument: ${token}`);
    }
    const value = argv[index + 1];
    if (value === undefined || value.startsWith("--")) {
      throw new Error(`missing value for ${token}`);
    }
    options[token.slice(2)] = value;
    index += 1;
  }
  for (const key of ["url", "name", "width", "height", "out-dir"]) {
    if (!options[key]) {
      throw new Error(`missing --${key}`);
    }
  }
  options.width = Number.parseInt(options.width, 10);
  options.height = Number.parseInt(options.height, 10);
  if (!Number.isInteger(options.width) || options.width <= 0 || !Number.isInteger(options.height) || options.height <= 0) {
    throw new Error("width and height must be positive integers");
  }
  if (!/^[a-z0-9][a-z0-9-]*$/.test(options.name)) {
    throw new Error("name must contain only lowercase letters, digits, and hyphens");
  }
  return options;
}

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
      // Keep searching PATH.
    }
  }
  return null;
}

function findChrome(explicit) {
  if (explicit) return findExecutable(explicit);
  for (const candidate of ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"]) {
    const executable = findExecutable(candidate);
    if (executable) return executable;
  }
  return null;
}

function delay(milliseconds) {
  return new Promise((resolveDelay) => setTimeout(resolveDelay, milliseconds));
}

async function launchChrome(chrome, profileDirectory) {
  const child = spawn(
    chrome,
    [
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
      "about:blank",
    ],
    { stdio: ["ignore", "ignore", "pipe"] },
  );
  child.stderr.setEncoding("utf8");
  let diagnostics = "";
  const websocketUrl = await new Promise((resolveUrl, reject) => {
    const timeout = setTimeout(() => {
      reject(new Error(`Chrome DevTools endpoint timeout: ${diagnostics.slice(-2000)}`));
    }, 15_000);
    child.stderr.on("data", (chunk) => {
      diagnostics += chunk;
      const match = diagnostics.match(/DevTools listening on (ws:\/\/[^\s]+)/);
      if (match) {
        clearTimeout(timeout);
        resolveUrl(match[1]);
      }
    });
    child.once("exit", (code) => {
      clearTimeout(timeout);
      reject(new Error(`Chrome exited before DevTools was ready (${code}): ${diagnostics.slice(-2000)}`));
    });
    child.once("error", (error) => {
      clearTimeout(timeout);
      reject(error);
    });
  });
  return { child, websocketUrl, diagnostics: () => diagnostics };
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
    this.socket.addEventListener("message", (event) => {
      const message = JSON.parse(String(event.data));
      if (!message.id || !this.pending.has(message.id)) return;
      const { resolveCommand, rejectCommand } = this.pending.get(message.id);
      this.pending.delete(message.id);
      if (message.error) {
        rejectCommand(new Error(`${message.error.code}: ${message.error.message}`));
      } else {
        resolveCommand(message.result ?? {});
      }
    });
    this.socket.addEventListener("close", () => {
      for (const { rejectCommand } of this.pending.values()) {
        rejectCommand(new Error("Chrome DevTools websocket closed"));
      }
      this.pending.clear();
    });
  }

  async send(method, params = {}, sessionId = undefined) {
    await this.ready;
    const id = this.nextId;
    this.nextId += 1;
    const payload = { id, method, params };
    if (sessionId) payload.sessionId = sessionId;
    const response = new Promise((resolveCommand, rejectCommand) => {
      this.pending.set(id, { resolveCommand, rejectCommand });
    });
    this.socket.send(JSON.stringify(payload));
    return response;
  }

  close() {
    this.socket.close();
  }
}

async function evaluate(client, sessionId, expression) {
  const result = await client.send(
    "Runtime.evaluate",
    { expression, returnByValue: true, awaitPromise: true },
    sessionId,
  );
  if (result.exceptionDetails) {
    throw new Error(`Runtime.evaluate failed: ${JSON.stringify(result.exceptionDetails)}`);
  }
  return result.result?.value;
}

const READY_EXPRESSION = `(() => {
  const app = document.querySelector('#app');
  return document.readyState === 'complete'
    && app?.dataset.rendererReady === 'true'
    && app?.dataset.frameRendered === 'true'
    && Boolean(document.querySelector('[data-viewer-runtime-ui="mounted"]'));
})()`;

const METRICS_EXPRESSION = `(() => {
  const rect = (element) => {
    if (!element) return null;
    const value = element.getBoundingClientRect();
    return {
      x: value.x,
      y: value.y,
      top: value.top,
      right: value.right,
      bottom: value.bottom,
      left: value.left,
      width: value.width,
      height: value.height,
    };
  };
  const visibleRect = (selector) => {
    const element = document.querySelector(selector);
    if (!element || element.hidden || getComputedStyle(element).display === 'none') return null;
    return rect(element);
  };
  const app = document.querySelector('#app');
  const runtimeUi = document.querySelector('[data-viewer-runtime-ui="mounted"]');
  const root = document.documentElement;
  const body = document.body;
  return {
    viewport: {
      innerWidth: window.innerWidth,
      innerHeight: window.innerHeight,
      visualWidth: window.visualViewport?.width ?? window.innerWidth,
      visualHeight: window.visualViewport?.height ?? window.innerHeight,
      visualScale: window.visualViewport?.scale ?? 1,
      devicePixelRatio: window.devicePixelRatio,
    },
    document: {
      clientWidth: root.clientWidth,
      clientHeight: root.clientHeight,
      scrollWidth: root.scrollWidth,
      scrollHeight: root.scrollHeight,
      bodyScrollWidth: body?.scrollWidth ?? 0,
      bodyScrollHeight: body?.scrollHeight ?? 0,
    },
    rects: {
      app: rect(app),
      stage: visibleRect('.viewer-configurator__stage'),
      detail: visibleRect('.viewer-product-detail'),
      topbar: visibleRect('.viewer-configurator__topbar'),
      actions: visibleRect('.viewer-configurator__actions'),
    },
    presentation: app ? {
      frame: app.dataset.presentationFrame ?? null,
      fit: app.dataset.presentationFit ?? null,
      crop: app.dataset.presentationCrop ?? null,
      hostWidth: app.dataset.presentationHostWidth ?? null,
      hostHeight: app.dataset.presentationHostHeight ?? null,
      rasterX: app.dataset.presentationRasterX ?? null,
      rasterY: app.dataset.presentationRasterY ?? null,
      rasterWidth: app.dataset.presentationRasterWidth ?? null,
      rasterHeight: app.dataset.presentationRasterHeight ?? null,
      aspect: app.dataset.presentationAspect ?? null,
    } : null,
    state: {
      rendererReady: app?.dataset.rendererReady ?? null,
      frameRendered: app?.dataset.frameRendered ?? null,
      runtimeUi: runtimeUi?.dataset.viewerRuntimeUi ?? null,
      detailOpen: body?.dataset.viewerDetailOpen ?? null,
    },
    responsiveMode: matchMedia('(max-width: 900px)').matches
      ? 'mobile-sheet'
      : matchMedia('(max-width: 1240px)').matches
        ? 'compact-overlay'
        : 'wide-reserved-panel',
  };
})()`;

async function capture(options) {
  const chrome = findChrome(options.chrome);
  if (!chrome) throw new Error("CHROME_NOT_FOUND");
  const outputDirectory = resolve(options["out-dir"]);
  mkdirSync(outputDirectory, { recursive: true });
  const profileDirectory = mkdtempSync(join(tmpdir(), "mobilipresenter-cdp-"));
  let launched = null;
  let client = null;
  try {
    launched = await launchChrome(chrome, profileDirectory);
    client = new CdpClient(launched.websocketUrl);
    const { targetId } = await client.send("Target.createTarget", { url: "about:blank" });
    const { sessionId } = await client.send("Target.attachToTarget", { targetId, flatten: true });
    await client.send("Page.enable", {}, sessionId);
    await client.send("Runtime.enable", {}, sessionId);
    await client.send(
      "Emulation.setDeviceMetricsOverride",
      {
        width: options.width,
        height: options.height,
        screenWidth: options.width,
        screenHeight: options.height,
        deviceScaleFactor: 1,
        mobile: options.width <= 900,
        screenOrientation: {
          angle: 0,
          type: options.width > options.height ? "landscapePrimary" : "portraitPrimary",
        },
      },
      sessionId,
    );
    await client.send("Page.navigate", { url: options.url }, sessionId);
    const deadline = Date.now() + 20_000;
    while (!(await evaluate(client, sessionId, READY_EXPRESSION))) {
      if (Date.now() >= deadline) {
        throw new Error(`RUNTIME_UI_READY_TIMEOUT:${options.name}`);
      }
      await delay(100);
    }
    await client.send("Animation.setPlaybackRate", { playbackRate: 0 }, sessionId).catch(() => {});
    await delay(100);

    const metrics = await evaluate(client, sessionId, METRICS_EXPRESSION);
    const html = await evaluate(client, sessionId, "document.documentElement.outerHTML");
    const htmlPath = join(outputDirectory, `${options.name}.html`);
    const metricsPath = join(outputDirectory, `${options.name}.metrics.json`);
    writeFileSync(htmlPath, `${html}\n`, "utf8");
    writeFileSync(metricsPath, `${JSON.stringify(metrics, null, 2)}\n`, "utf8");

    let screenshotPath = null;
    let screenshotBytes = null;
    if (options.screenshot) {
      const screenshot = await client.send(
        "Page.captureScreenshot",
        { format: "png", fromSurface: true, captureBeyondViewport: false },
        sessionId,
      );
      screenshotPath = join(outputDirectory, `${options.name}.png`);
      writeFileSync(screenshotPath, Buffer.from(screenshot.data, "base64"));
      screenshotBytes = readFileSync(screenshotPath).byteLength;
    }

    return {
      id: options.name,
      requestedViewportPx: [options.width, options.height],
      metrics,
      htmlPath,
      metricsPath,
      screenshotPath,
      screenshotBytes,
    };
  } finally {
    try {
      client?.close();
    } catch {
      // Best-effort cleanup after evidence capture.
    }
    if (launched?.child && !launched.child.killed) launched.child.kill("SIGTERM");
    rmSync(profileDirectory, { recursive: true, force: true });
  }
}

try {
  const result = await capture(parseArgs(process.argv.slice(2)));
  process.stdout.write(`${JSON.stringify(result)}\n`);
} catch (error) {
  process.stderr.write(`${error?.stack ?? error}\n`);
  process.exitCode = 1;
}
