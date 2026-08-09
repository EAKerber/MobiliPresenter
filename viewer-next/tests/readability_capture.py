from __future__ import annotations

import json
import math
import shutil
import struct
import subprocess
import sys
from pathlib import Path

SPEC_PATH = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/mobilipresenter-readability-spec.json")
OUTPUT_DIR = Path(sys.argv[2] if len(sys.argv) > 2 else "/tmp/mobilipresenter-readability-crops")
MANIFEST_PATH = Path(sys.argv[3] if len(sys.argv) > 3 else "/tmp/mobilipresenter-readability-crops.json")
LOCAL_PREVIEW = "http://127.0.0.1:4173/"
MIN_CROP_PX = 256
EXTRA_MARGIN_PX = 24


def find_chrome() -> str:
    for candidate in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        path = shutil.which(candidate)
        if path:
            return path
    raise SystemExit("READABILITY_CHROME_NOT_FOUND")


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise SystemExit(f"READABILITY_CAPTURE_NOT_PNG:{path}")
    return struct.unpack(">II", data[16:24])


def safe_id(value: str) -> str:
    return "".join(char if char.isalnum() or char in "-_" else "_" for char in value)


def expand(start: int, end: int, minimum: int, limit: int) -> tuple[int, int]:
    if end - start < minimum:
        extra = minimum - (end - start)
        start -= extra // 2
        end += extra - extra // 2
    if start < 0:
        end -= start
        start = 0
    if end > limit:
        start -= end - limit
        end = limit
    return max(0, start), min(limit, end)


def crop_for_probe(probe: dict, full_width: int, full_height: int) -> dict[str, int]:
    ax, ay = probe["aPx4x"]
    bx, by = probe["bPx4x"]
    margin = int(math.ceil(float(probe["searchBandPx4x"]) + EXTRA_MARGIN_PX))
    x0 = math.floor(min(ax, bx) - margin)
    x1 = math.ceil(max(ax, bx) + margin)
    y0 = math.floor(min(ay, by) - margin)
    y1 = math.ceil(max(ay, by) + margin)
    x0, x1 = expand(x0, x1, MIN_CROP_PX, full_width)
    y0, y1 = expand(y0, y1, MIN_CROP_PX, full_height)
    return {"xPx": x0, "yPx": y0, "widthPx": x1 - x0, "heightPx": y1 - y0}


def capture(chrome: str, crop: dict[str, int], output: Path) -> None:
    crop_value = f"{crop['xPx']},{crop['yPx']},{crop['widthPx']},{crop['heightPx']}"
    url = f"{LOCAL_PREVIEW}?fidelity=1&crop={crop_value}"
    args = [
        chrome,
        "--headless=new",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--ignore-gpu-blocklist",
        "--enable-webgl",
        "--enable-unsafe-swiftshader",
        "--use-angle=swiftshader",
        f"--window-size={crop['widthPx']},{crop['heightPx']}",
        "--force-device-scale-factor=1",
        "--virtual-time-budget=6000",
        f"--screenshot={output}",
        url,
    ]
    result = subprocess.run(args, text=True, capture_output=True, check=False, timeout=90)
    if result.returncode != 0 or not output.is_file():
        raise SystemExit(f"READABILITY_CAPTURE_FAILED:{crop_value}:{result.stderr[-1000:]}")
    if png_size(output) != (crop["widthPx"], crop["heightPx"]):
        raise SystemExit(f"READABILITY_CAPTURE_SIZE_MISMATCH:{output}")


def main() -> None:
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    factor = int(spec["supersampleFactor"])
    if factor != 4:
        raise SystemExit(f"READABILITY_EXPECTED_4X:{factor}")
    full_width, full_height = [int(value) * factor for value in spec["canonicalViewportPx"]]
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    chrome = find_chrome()
    entries = []
    for probe in spec["probes"]:
        crop = crop_for_probe(probe, full_width, full_height)
        filename = f"{safe_id(probe['id'])}.png"
        output = OUTPUT_DIR / filename
        capture(chrome, crop, output)
        entries.append({"probeId": probe["id"], "crop4x": crop, "png": filename, "bytes": output.stat().st_size})
    manifest = {
        "schemaVersion": "ReadabilityCropManifest 1.0",
        "virtualViewportPx": [full_width, full_height],
        "supersampleFactor": factor,
        "policy": "targeted-off-axis-crops-from-fixed-camera",
        "entries": entries,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "captures": len(entries), "manifest": str(MANIFEST_PATH)}, indent=2))


if __name__ == "__main__":
    main()
