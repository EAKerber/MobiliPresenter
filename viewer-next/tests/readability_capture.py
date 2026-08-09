from __future__ import annotations

import json
import math
import shutil
import struct
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

SPEC_PATH = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/mobilipresenter-readability-spec.json")
OUTPUT_DIR = Path(sys.argv[2] if len(sys.argv) > 2 else "/tmp/mobilipresenter-readability-crops")
MANIFEST_PATH = Path(sys.argv[3] if len(sys.argv) > 3 else "/tmp/mobilipresenter-readability-crops.json")
LOCAL_PREVIEW = "http://127.0.0.1:4173/"
MIN_CROP_PX = 256
EXTRA_MARGIN_PX = 32


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


def group_id(probe_id: str) -> str:
    return probe_id.split("/", 1)[0]


def crop_for_group(probes: list[dict], full_width: int, full_height: int) -> dict[str, int]:
    band = max(int(math.ceil(float(probe["searchBandPx4x"]))) for probe in probes)
    margin = band + EXTRA_MARGIN_PX
    xs = [coordinate for probe in probes for coordinate in (probe["aPx4x"][0], probe["bPx4x"][0])]
    ys = [coordinate for probe in probes for coordinate in (probe["aPx4x"][1], probe["bPx4x"][1])]
    x0 = math.floor(min(xs) - margin)
    x1 = math.ceil(max(xs) + margin)
    y0 = math.floor(min(ys) - margin)
    y1 = math.ceil(max(ys) + margin)
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
        "--virtual-time-budget=4000",
        f"--screenshot={output}",
        url,
    ]
    result = subprocess.run(args, text=True, capture_output=True, check=False, timeout=60)
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

    grouped: dict[str, list[dict]] = defaultdict(list)
    for probe in spec["probes"]:
        grouped[group_id(probe["id"])].append(probe)

    captures: dict[str, dict] = {}
    for group, probes in sorted(grouped.items()):
        crop = crop_for_group(probes, full_width, full_height)
        filename = f"{safe_id(group)}.png"
        output = OUTPUT_DIR / filename
        capture(chrome, crop, output)
        captures[group] = {"groupId": group, "crop4x": crop, "png": filename, "bytes": output.stat().st_size}

    entries = []
    for probe in spec["probes"]:
        capture_entry = captures[group_id(probe["id"])]
        entries.append({
            "probeId": probe["id"],
            "groupId": capture_entry["groupId"],
            "crop4x": capture_entry["crop4x"],
            "png": capture_entry["png"],
        })

    manifest = {
        "schemaVersion": "ReadabilityCropManifest 1.0",
        "virtualViewportPx": [full_width, full_height],
        "supersampleFactor": factor,
        "policy": "grouped-targeted-off-axis-crops-from-fixed-camera",
        "captureCount": len(captures),
        "probeCount": len(entries),
        "captures": list(captures.values()),
        "entries": entries,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "captures": len(captures), "probes": len(entries), "manifest": str(MANIFEST_PATH)}, indent=2))


if __name__ == "__main__":
    main()
