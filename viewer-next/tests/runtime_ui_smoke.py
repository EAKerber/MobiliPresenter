from __future__ import annotations

import json
import shutil
import struct
import subprocess
from pathlib import Path
from urllib.parse import urlencode

BASE_URL = "http://127.0.0.1:4173/"
OUT = Path("artifacts/runtime-ui")
EVIDENCE = OUT / "evidence.json"


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
        "--window-size=1366,768",
        "--force-device-scale-factor=1",
        "--virtual-time-budget=6000",
    ]


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, text=True, capture_output=True, check=False, timeout=90)


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise SystemExit("RUNTIME_UI_SCREENSHOT_NOT_PNG")
    return struct.unpack(">II", data[16:24])


def main() -> None:
    chrome = find_chrome()
    OUT.mkdir(parents=True, exist_ok=True)
    params = {
        "controls": "1",
        "select": "02",
        "hide": "02",
        "front": "02:neutral-greige",
        "stone": "graphite-speckled",
        "light": "warm-worktop",
    }
    url = BASE_URL + "?" + urlencode(params)
    dom_path = OUT / "runtime-ui.html"
    screenshot_path = OUT / "runtime-ui.png"

    dom_result = run(chrome_args(chrome) + ["--dump-dom", url])
    if dom_result.returncode != 0:
        raise SystemExit(f"RUNTIME_UI_DOM_FAILED:{dom_result.stderr[-2000:]}")
    dom_path.write_text(dom_result.stdout, encoding="utf-8")

    required = (
        'data-renderer-ready="true"',
        'data-frame-rendered="true"',
        'data-viewer-controls="true"',
        'data-viewer-runtime-ui="mounted"',
        'data-viewer-module02-visible="false"',
        'data-viewer-range-visible="true"',
        'data-viewer-stone-preset="graphite-speckled"',
        'data-viewer-lighting-preset="warm-worktop"',
        'data-module-alias="02"',
        'aria-pressed="true"',
        'data-front-preset="neutral-greige"',
        'data-stone-preset="graphite-speckled"',
        'data-lighting-preset="warm-worktop"',
        'Módulo 02',
        'oculto',
        'Mostrar módulo',
    )
    missing = [needle for needle in required if needle not in dom_result.stdout]
    if missing:
        raise SystemExit(f"RUNTIME_UI_DOM_GATE_FAILED:{missing}")

    shot_result = run(chrome_args(chrome) + [f"--screenshot={screenshot_path}", url])
    if shot_result.returncode != 0 or not screenshot_path.is_file():
        raise SystemExit(f"RUNTIME_UI_SCREENSHOT_FAILED:{shot_result.stderr[-2000:]}")
    width, height = png_size(screenshot_path)
    if (width, height) != (1366, 768):
        raise SystemExit(f"RUNTIME_UI_SCREENSHOT_SIZE_MISMATCH:{width}x{height}")
    if screenshot_path.stat().st_size < 10_000:
        raise SystemExit(f"RUNTIME_UI_SCREENSHOT_SUSPICIOUSLY_SMALL:{screenshot_path.stat().st_size}")

    evidence = {
        "schemaVersion": "ViewerRuntimeUiEvidence 0.1.0",
        "status": "PASS",
        "url": url,
        "viewportPx": [width, height],
        "screenshotBytes": screenshot_path.stat().st_size,
        "requiredDomMarkers": list(required),
        "invariants": {
            "canonicalBaselineControlsRemainOptIn": True,
            "moduleSelectionProjected": True,
            "hiddenModuleRestorationControlProjected": True,
            "frontPresetProjected": True,
            "stonePresetProjected": True,
            "lightingPresetProjected": True,
        },
    }
    EVIDENCE.write_text(json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(evidence, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
