from __future__ import annotations

import json
import re
import shutil
import struct
import subprocess
from pathlib import Path
from urllib.parse import urlencode

BASE_URL = "http://127.0.0.1:4173/"
OUT = Path("artifacts/runtime-controls")
EVIDENCE = OUT / "evidence.json"

MODULE03 = "scene/traditional/module/lower-sink"


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
        raise SystemExit(f"RUNTIME_SCREENSHOT_NOT_PNG:{path.name}")
    return struct.unpack(">II", data[16:24])


def marker(name: str, value: str) -> str:
    return f'data-{name}="{value}"'


def data_attr(dom: str, name: str) -> str | None:
    match = re.search(rf'data-{re.escape(name)}="([^"]*)"', dom)
    return match.group(1) if match else None


BASE_MARKERS = (
    marker("renderer-ready", "true"),
    marker("frame-rendered", "true"),
    marker("render-ownership", "pass"),
    marker("scene-id", "traditional-complete"),
)

CASES = (
    {
        "id": "baseline",
        "params": {},
        "markers": (
            marker("viewer-module02-visible", "true"),
            marker("viewer-oven-visible", "true"),
            marker("viewer-cooktop-visible", "true"),
            marker("viewer-range-visible", "false"),
            marker("viewer-module06-visible", "true"),
            marker("viewer-microwave-visible", "true"),
            marker("viewer-under-cab-visible", "true"),
            marker("viewer-lighting-preset", "canonical"),
        ),
    },
    {
        "id": "hide-module02",
        "params": {"hide": "02"},
        "markers": (
            marker("viewer-module02-visible", "false"),
            marker("viewer-oven-visible", "false"),
            marker("viewer-cooktop-visible", "false"),
            marker("viewer-range-visible", "true"),
        ),
    },
    {
        "id": "hide-module06",
        "params": {"hide": "06"},
        "markers": (
            marker("viewer-module06-visible", "false"),
            marker("viewer-microwave-visible", "false"),
            marker("viewer-under-cab-visible", "false"),
        ),
    },
    {
        "id": "appearance",
        "params": {"front": "03:neutral-greige", "stone": "graphite-speckled"},
        "markers": (
            marker("viewer-module03-front-material", "front-primary"),
            marker("viewer-stone03-material", "stone-speckled-graphite"),
            marker("viewer-stone-preset", "graphite-speckled"),
        ),
    },
    {
        "id": "lighting",
        "params": {"light": "warm-worktop"},
        "markers": (
            marker("viewer-lighting-preset", "warm-worktop"),
            marker("viewer-lighting-policy", "LIGHT-CANONICAL-01/warm-worktop"),
        ),
    },
    {
        "id": "selection",
        "params": {"select": "03"},
        "markers": (
            marker("viewer-selected-module", MODULE03),
            marker("viewer-selection-overlay-count", "1"),
        ),
    },
    *(
        {
            "id": f"lifecycle-{family}",
            "params": {"exercise": f"lifecycle-{family}"},
            "screenshot": False,
            "lifecycle": True,
            "markers": (
                marker("viewer-lifecycle-status", "pass"),
                marker("viewer-lifecycle-family", family),
                marker("viewer-module02-visible", "true"),
                marker("viewer-range-visible", "false"),
                marker("viewer-lighting-preset", "canonical"),
            ),
        }
        for family in ("visibility", "appearance", "lighting", "selection")
    ),
)


def main() -> None:
    chrome = find_chrome()
    OUT.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, object]] = []

    for case in CASES:
        case_id = str(case["id"])
        params = case["params"]
        query = urlencode(params)
        url = BASE_URL + (f"?{query}" if query else "")
        dom_path = OUT / f"{case_id}.html"
        screenshot_path = OUT / f"{case_id}.png"

        dom_result = run(chrome_args(chrome) + ["--dump-dom", url])
        if dom_result.returncode != 0:
            raise SystemExit(f"RUNTIME_DOM_FAILED:{case_id}:{dom_result.stderr[-2000:]}")
        dom_path.write_text(dom_result.stdout, encoding="utf-8")

        required = BASE_MARKERS + tuple(case["markers"])
        missing = [needle for needle in required if needle not in dom_result.stdout]
        if missing:
            raise SystemExit(f"RUNTIME_DOM_GATE_FAILED:{case_id}:{missing}")

        result: dict[str, object] = {
            "id": case_id,
            "url": url,
            "markers": list(required),
        }

        if bool(case.get("screenshot", True)):
            shot_result = run(chrome_args(chrome) + [f"--screenshot={screenshot_path}", url])
            if shot_result.returncode != 0 or not screenshot_path.is_file():
                raise SystemExit(f"RUNTIME_SCREENSHOT_FAILED:{case_id}:{shot_result.stderr[-2000:]}")
            width, height = png_size(screenshot_path)
            if (width, height) != (1865, 967):
                raise SystemExit(f"RUNTIME_SCREENSHOT_SIZE_MISMATCH:{case_id}:{width}x{height}")
            if screenshot_path.stat().st_size < 10_000:
                raise SystemExit(f"RUNTIME_SCREENSHOT_SUSPICIOUSLY_SMALL:{case_id}:{screenshot_path.stat().st_size}")
            result["viewportPx"] = [width, height]
            result["screenshotBytes"] = screenshot_path.stat().st_size
        else:
            result["screenshot"] = "skipped-nonvisual-gate"

        if bool(case.get("lifecycle", False)):
            before = data_attr(dom_result.stdout, "viewer-lifecycle-before")
            after = data_attr(dom_result.stdout, "viewer-lifecycle-after")
            duration = data_attr(dom_result.stdout, "viewer-lifecycle-duration-ms")
            if before is None or after is None or duration is None:
                raise SystemExit(f"RUNTIME_LIFECYCLE_EVIDENCE_MISSING:{case_id}")
            result["lifecycle"] = {
                "before": before,
                "after": after,
                "durationMs": float(duration),
            }

        results.append(result)

    evidence = {
        "schemaVersion": "ViewerRuntimeControlsEvidence 0.1.0",
        "status": "PASS",
        "browser": chrome,
        "caseCount": len(results),
        "cases": results,
        "invariants": {
            "module02ReplacementObserved": True,
            "module06HostedVisibilityObserved": True,
            "resolvedMaterialsObserved": True,
            "lightingPolicyObserved": True,
            "selectionOverlayObserved": True,
            "boundedLifecycleFamiliesObserved": ["visibility", "appearance", "lighting", "selection"],
        },
    }
    EVIDENCE.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()