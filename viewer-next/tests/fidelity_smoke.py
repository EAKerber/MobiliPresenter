from __future__ import annotations

import json
import shutil
import struct
import subprocess
from pathlib import Path

BASE = "http://127.0.0.1:4173/"
CLEAN_URL = f"{BASE}?fidelity=1"
OVERLAY_URL = f"{BASE}?fidelity=1&overlay=1"
DOM = Path("/tmp/mobilipresenter-fidelity-dom.html")
CLEAN_SCREENSHOT = Path("/tmp/mobilipresenter-fidelity-clean-4x.png")
OVERLAY_SCREENSHOT = Path("/tmp/mobilipresenter-fidelity-overlay-4x.png")
EVIDENCE = Path("/tmp/mobilipresenter-fidelity-evidence.json")
CANONICAL = (1865, 967)
SUPERSAMPLE = 4
EXPECTED = (CANONICAL[0] * SUPERSAMPLE, CANONICAL[1] * SUPERSAMPLE)


def find_chrome() -> str:
    for candidate in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        path = shutil.which(candidate)
        if path:
            return path
    raise SystemExit("CHROME_NOT_FOUND")


def chrome_args(chrome: str) -> list[str]:
    return [
        chrome,
        "--headless=new",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--ignore-gpu-blocklist",
        "--enable-webgl",
        "--enable-unsafe-swiftshader",
        "--use-angle=swiftshader",
        f"--window-size={CANONICAL[0]},{CANONICAL[1]}",
        f"--force-device-scale-factor={SUPERSAMPLE}",
        "--virtual-time-budget=8000",
    ]


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, text=True, capture_output=True, check=False, timeout=120)


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise SystemExit(f"FIDELITY_SCREENSHOT_NOT_PNG:{path}")
    return struct.unpack(">II", data[16:24])


def capture(chrome: str, url: str, output: Path) -> tuple[int, int]:
    result = run(chrome_args(chrome) + [f"--screenshot={output}", url])
    if result.returncode != 0 or not output.is_file():
        raise SystemExit(f"FIDELITY_CHROME_SCREENSHOT_FAILED:{url}:{result.stderr[-2000:]}")
    size = png_size(output)
    if size != EXPECTED:
        raise SystemExit(f"FIDELITY_SCREENSHOT_SIZE_MISMATCH:{output}:{size[0]}x{size[1]}:expected={EXPECTED[0]}x{EXPECTED[1]}")
    if output.stat().st_size < 25_000:
        raise SystemExit(f"FIDELITY_SCREENSHOT_SUSPICIOUSLY_SMALL:{output}:{output.stat().st_size}")
    return size


def main() -> None:
    chrome = find_chrome()
    dom_result = run(chrome_args(chrome) + ["--dump-dom", OVERLAY_URL])
    if dom_result.returncode != 0:
        raise SystemExit(f"FIDELITY_CHROME_DOM_FAILED:{dom_result.stderr[-2000:]}")
    DOM.write_text(dom_result.stdout, encoding="utf-8")
    required = (
        'data-renderer-backend="three-webgl2"',
        'data-renderer-ready="true"',
        'data-frame-rendered="true"',
        'data-scene-id="traditional-complete"',
        'data-fidelity-mode="true"',
        'data-fidelity-overlay="true"',
        'data-fidelity-line-count=',
    )
    missing = [needle for needle in required if needle not in dom_result.stdout]
    if missing:
        raise SystemExit(f"FIDELITY_DOM_GATE_FAILED:{missing}\n{dom_result.stderr[-2000:]}")

    clean_size = capture(chrome, CLEAN_URL, CLEAN_SCREENSHOT)
    overlay_size = capture(chrome, OVERLAY_URL, OVERLAY_SCREENSHOT)
    evidence = {
        "status": "PASS",
        "browser": chrome,
        "canonicalViewportPx": list(CANONICAL),
        "supersampleFactor": SUPERSAMPLE,
        "renderedScreenshotPx": list(clean_size),
        "cleanScreenshot": {"path": str(CLEAN_SCREENSHOT), "bytes": CLEAN_SCREENSHOT.stat().st_size},
        "overlayScreenshot": {"path": str(OVERLAY_SCREENSHOT), "bytes": OVERLAY_SCREENSHOT.stat().st_size, "size": list(overlay_size)},
        "requiredDomMarkers": list(required),
    }
    EVIDENCE.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
