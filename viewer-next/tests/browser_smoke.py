from __future__ import annotations

import json
import shutil
import struct
import subprocess
from pathlib import Path

from runtime_controls_smoke import main as runtime_controls_smoke

URL = "http://127.0.0.1:4173/"
DOM = Path("/tmp/mobilipresenter-viewer-dom.html")
SCREENSHOT = Path("/tmp/mobilipresenter-viewer.png")
EVIDENCE = Path("/tmp/mobilipresenter-browser-evidence.json")


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
        "--window-size=1865,967",
        "--force-device-scale-factor=1",
        "--virtual-time-budget=6000",
    ]


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, text=True, capture_output=True, check=False, timeout=90)


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise SystemExit("SCREENSHOT_NOT_PNG")
    return struct.unpack(">II", data[16:24])


def main() -> None:
    chrome = find_chrome()
    dom_result = run(chrome_args(chrome) + ["--dump-dom", URL])
    if dom_result.returncode != 0:
        raise SystemExit(f"CHROME_DOM_FAILED:{dom_result.stderr[-2000:]}")
    DOM.write_text(dom_result.stdout, encoding="utf-8")
    required = (
        'data-renderer-backend="three-webgl2"',
        'data-renderer-ready="true"',
        'data-frame-rendered="true"',
        'data-scene-id="traditional-complete"',
        'data-color-treatment="fh06-s10-neutral-warm-v1"',
        'data-occlusion="gtao-mm-v1"',
        'data-occlusion-radius-mm="72"',
        'data-occlusion-blend="0.38"',
        'data-cooktop-contact="fh06-s10-cooktop-stone-contact-v1"',
        'data-cooktop-gap-mm="1.000"',
        'data-front-readability="module03-drawer-bevel-recess-v1"',
        'data-front-physical-gap-mm="2,2,2"',
        'data-oven-readability="fh06-s10-oven-physical-reveal-v1"',
        'data-oven-physical-clearance-mm="2,2,2,2"',
        'data-wall-tile-coverage="full-wall"',
        'data-wall-tile-surface-count="4"',
        'data-sink-refinement="SINK-UNDERMOUNT-40X34-01"',
        'data-sink-stone-hole="extruded-shape-with-rounded-hole"',
        'data-sink-continuous-bowl="true"',
        'data-faucet-refinement="FAUCET-HIGH-ARC-01"',
        'data-faucet-host="scene/traditional/accessory/stone-03"',
        'data-under-cab-profile="rear-corner-18mm-45deg"',
        'data-under-cab-kelvin="3000"',
        'data-under-cab-host="scene/traditional/module/upper-sink-microwave"',
        'data-under-cab-area-light="true"',
        'data-render-ownership="pass"',
    )
    missing = [needle for needle in required if needle not in dom_result.stdout]
    if missing:
        raise SystemExit(f"RENDERER_DOM_GATE_FAILED:{missing}\n{dom_result.stderr[-2000:]}")

    shot_result = run(chrome_args(chrome) + [f"--screenshot={SCREENSHOT}", URL])
    if shot_result.returncode != 0 or not SCREENSHOT.is_file():
        raise SystemExit(f"CHROME_SCREENSHOT_FAILED:{shot_result.stderr[-2000:]}")
    width, height = png_size(SCREENSHOT)
    if (width, height) != (1865, 967):
        raise SystemExit(f"SCREENSHOT_SIZE_MISMATCH:{width}x{height}")
    if SCREENSHOT.stat().st_size < 10_000:
        raise SystemExit(f"SCREENSHOT_SUSPICIOUSLY_SMALL:{SCREENSHOT.stat().st_size}")

    evidence = {
        "status": "PASS",
        "browser": chrome,
        "url": URL,
        "viewportPx": [width, height],
        "screenshotBytes": SCREENSHOT.stat().st_size,
        "requiredDomMarkers": list(required),
    }
    EVIDENCE.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2))

    runtime_controls_smoke()


if __name__ == "__main__":
    main()