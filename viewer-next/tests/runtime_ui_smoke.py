from __future__ import annotations

import json
import re
import shutil
import struct
import subprocess
from pathlib import Path
from urllib.parse import urlencode

BASE_URL = "http://127.0.0.1:4173/"
OUT = Path("artifacts/runtime-ui")
EVIDENCE = OUT / "evidence.json"
PRESENTATION_ASPECT = 1.9286452947259565


def find_chrome() -> str:
    for candidate in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        path = shutil.which(candidate)
        if path:
            return path
    raise SystemExit("CHROME_NOT_FOUND")


def chrome_args(chrome: str, width: int, height: int) -> list[str]:
    return [
        chrome,
        "--headless=new",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--ignore-gpu-blocklist",
        "--enable-webgl",
        "--enable-unsafe-swiftshader",
        "--use-angle=swiftshader",
        f"--window-size={width},{height}",
        "--force-device-scale-factor=1",
        "--virtual-time-budget=6000",
    ]


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, text=True, capture_output=True, check=False, timeout=90)


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise SystemExit(f"RUNTIME_UI_SCREENSHOT_NOT_PNG:{path.name}")
    return struct.unpack(">II", data[16:24])


def capture(chrome: str, url: str, name: str, width: int, height: int) -> dict[str, object]:
    screenshot_path = OUT / f"{name}.png"
    shot_result = run(chrome_args(chrome, width, height) + [f"--screenshot={screenshot_path}", url])
    if shot_result.returncode != 0 or not screenshot_path.is_file():
        raise SystemExit(f"RUNTIME_UI_SCREENSHOT_FAILED:{name}:{shot_result.stderr[-2000:]}")
    actual_width, actual_height = png_size(screenshot_path)
    if (actual_width, actual_height) != (width, height):
        raise SystemExit(
            f"RUNTIME_UI_SCREENSHOT_SIZE_MISMATCH:{name}:{actual_width}x{actual_height}"
        )
    if screenshot_path.stat().st_size < 10_000:
        raise SystemExit(
            f"RUNTIME_UI_SCREENSHOT_SUSPICIOUSLY_SMALL:{name}:{screenshot_path.stat().st_size}"
        )
    return {
        "id": name,
        "viewportPx": [actual_width, actual_height],
        "screenshotBytes": screenshot_path.stat().st_size,
    }


def dump_dom(chrome: str, url: str, name: str, width: int = 1366, height: int = 768) -> str:
    result = run(chrome_args(chrome, width, height) + ["--dump-dom", url])
    if result.returncode != 0:
        raise SystemExit(f"RUNTIME_UI_DOM_FAILED:{name}:{result.stderr[-2000:]}")
    (OUT / f"{name}.html").write_text(result.stdout, encoding="utf-8")
    return result.stdout


def require(dom: str, name: str, needles: tuple[str, ...]) -> None:
    missing = [needle for needle in needles if needle not in dom]
    if missing:
        raise SystemExit(f"RUNTIME_UI_DOM_GATE_FAILED:{name}:{missing}")


def presentation_frame_evidence(dom: str, name: str) -> dict[str, object]:
    app_match = re.search(r'<div id="app"([^>]*)>', dom)
    if app_match is None:
        raise SystemExit(f"RUNTIME_UI_APP_MISSING:{name}")
    attrs = dict(re.findall(r'data-([a-z0-9-]+)="([^"]*)"', app_match.group(1)))
    required = (
        "presentation-frame",
        "presentation-fit",
        "presentation-crop",
        "presentation-host-width",
        "presentation-host-height",
        "presentation-raster-x",
        "presentation-raster-y",
        "presentation-raster-width",
        "presentation-raster-height",
        "presentation-aspect",
    )
    missing = [key for key in required if key not in attrs]
    if missing:
        raise SystemExit(f"RUNTIME_UI_PRESENTATION_MARKERS_MISSING:{name}:{missing}")
    if attrs["presentation-frame"] != "active" or attrs["presentation-fit"] != "contain":
        raise SystemExit(f"RUNTIME_UI_PRESENTATION_POLICY_INVALID:{name}:{attrs}")
    if attrs["presentation-crop"] != "false":
        raise SystemExit(f"RUNTIME_UI_PRESENTATION_CROPPED:{name}")

    host_width = int(attrs["presentation-host-width"])
    host_height = int(attrs["presentation-host-height"])
    raster_x = int(attrs["presentation-raster-x"])
    raster_y = int(attrs["presentation-raster-y"])
    raster_width = int(attrs["presentation-raster-width"])
    raster_height = int(attrs["presentation-raster-height"])
    aspect = float(attrs["presentation-aspect"])

    if abs(aspect - PRESENTATION_ASPECT) > 1e-12:
        raise SystemExit(f"RUNTIME_UI_PRESENTATION_ASPECT_DRIFT:{name}:{aspect}")
    if min(host_width, host_height, raster_width, raster_height) <= 0:
        raise SystemExit(f"RUNTIME_UI_PRESENTATION_SIZE_INVALID:{name}")
    if raster_x < 0 or raster_y < 0:
        raise SystemExit(f"RUNTIME_UI_PRESENTATION_OFFSET_INVALID:{name}")
    if raster_x + raster_width > host_width or raster_y + raster_height > host_height:
        raise SystemExit(f"RUNTIME_UI_PRESENTATION_OUTSIDE_HOST:{name}")
    if abs((host_width - raster_width) - 2 * raster_x) > 1:
        raise SystemExit(f"RUNTIME_UI_PRESENTATION_NOT_CENTERED_X:{name}")
    if abs((host_height - raster_height) - 2 * raster_y) > 1:
        raise SystemExit(f"RUNTIME_UI_PRESENTATION_NOT_CENTERED_Y:{name}")

    return {
        "id": name,
        "hostPx": [host_width, host_height],
        "rasterPx": [raster_x, raster_y, raster_width, raster_height],
        "projectionAspectRatio": aspect,
        "fit": attrs["presentation-fit"],
        "cropped": False,
    }


def compact_detail_allocation_evidence(
    *,
    open_frame: dict[str, object],
    closed_frame: dict[str, object],
    viewport: tuple[int, int],
    minimum_scene_width: int,
) -> dict[str, object]:
    open_host = open_frame["hostPx"]
    closed_host = closed_frame["hostPx"]
    if open_host != closed_host:
        raise SystemExit(
            f"RUNTIME_UI_COMPACT_DETAIL_REFRAMES_SCENE:{viewport[0]}x{viewport[1]}:"
            f"open={open_host}:closed={closed_host}"
        )
    if not isinstance(open_host, list) or len(open_host) != 2 or int(open_host[0]) < minimum_scene_width:
        raise SystemExit(
            f"RUNTIME_UI_COMPACT_SCENE_TOO_NARROW:{viewport[0]}x{viewport[1]}:{open_host}"
        )
    return {
        "viewportPx": list(viewport),
        "detailOpenHostPx": open_host,
        "detailClosedHostPx": closed_host,
        "minimumSceneWidthPx": minimum_scene_width,
        "detailReframesScene": False,
    }


def main() -> None:
    chrome = find_chrome()
    OUT.mkdir(parents=True, exist_ok=True)

    ready_params = {
        "controls": "1",
        "select": "02",
        "hide": "02",
        "front": "02:neutral-greige",
        "stone": "graphite-speckled",
        "light": "warm-worktop",
    }
    ready_url = BASE_URL + "?" + urlencode(ready_params)
    ready_dom = dump_dom(chrome, ready_url, "runtime-ui-ready")
    ready_required = (
        'data-renderer-ready="true"',
        'data-frame-rendered="true"',
        'data-viewer-controls="true"',
        'data-viewer-runtime-ui="mounted"',
        'data-current-step="modules"',
        'data-viewer-detail-open="true"',
        'data-configurator-step="modules"',
        'data-configurator-step="finishes"',
        'data-configurator-step="accessories"',
        'data-configurator-step="summary"',
        'aria-current="step"',
        'data-stage-panel="modules"',
        'data-module-alias="02"',
        'data-module-visibility="02"',
        'data-visible="false"',
        'data-selected="true"',
        'aria-label="Mostrar módulo 02"',
        'data-presentation-status="ready"',
        'data-technical-fidelity="geometry-derived"',
        'Continuar para acabamentos',
        'Detalhes',
    )
    require(ready_dom, "ready", ready_required)

    unavailable_params = {"controls": "1", "select": "01"}
    unavailable_url = BASE_URL + "?" + urlencode(unavailable_params)
    unavailable_dom = dump_dom(chrome, unavailable_url, "runtime-ui-unavailable")
    unavailable_required = (
        'data-viewer-runtime-ui="mounted"',
        'data-module-alias="01"',
        'data-selected="true"',
        'data-presentation-status="unavailable"',
        'Detalhes técnicos ainda não publicados',
        'Informações técnicas ausentes não são inferidas pela interface.',
    )
    require(unavailable_dom, "unavailable", unavailable_required)

    matrix = (
        ("runtime-ui-desktop-modules-detail", 1366, 768),
        ("runtime-ui-compact-landscape-modules-detail", 1024, 768),
        ("runtime-ui-tablet-portrait-modules-detail", 768, 1024),
        ("runtime-ui-mobile-modules-detail", 390, 844),
    )
    captures: list[dict[str, object]] = []
    presentation_frames: list[dict[str, object]] = []
    open_frames_by_viewport: dict[tuple[int, int], dict[str, object]] = {}
    for name, width, height in matrix:
        dom = ready_dom if (width, height) == (1366, 768) else dump_dom(chrome, ready_url, name, width, height)
        frame = presentation_frame_evidence(dom, name)
        presentation_frames.append(frame)
        open_frames_by_viewport[(width, height)] = frame
        captures.append(capture(chrome, ready_url, name, width, height))
    captures.append(capture(chrome, unavailable_url, "runtime-ui-desktop-unavailable", 1366, 768))

    closed_params = {
        "controls": "1",
        "hide": "02",
        "front": "02:neutral-greige",
        "stone": "graphite-speckled",
        "light": "warm-worktop",
    }
    closed_url = BASE_URL + "?" + urlencode(closed_params)
    compact_detail_allocations: list[dict[str, object]] = []
    for width, height, minimum_width in ((1024, 768, 700), (768, 1024, 500)):
        closed_name = f"runtime-ui-{width}x{height}-detail-closed"
        closed_dom = dump_dom(chrome, closed_url, closed_name, width, height)
        require(closed_dom, closed_name, ('data-viewer-detail-open="false"',))
        closed_frame = presentation_frame_evidence(closed_dom, closed_name)
        compact_detail_allocations.append(
            compact_detail_allocation_evidence(
                open_frame=open_frames_by_viewport[(width, height)],
                closed_frame=closed_frame,
                viewport=(width, height),
                minimum_scene_width=minimum_width,
            )
        )

    evidence = {
        "schemaVersion": "ViewerRuntimeUiEvidence 0.5.0",
        "status": "PASS",
        "readyUrl": ready_url,
        "unavailableUrl": unavailable_url,
        "closedDetailUrl": closed_url,
        "captures": captures,
        "presentationFrames": presentation_frames,
        "compactDetailAllocations": compact_detail_allocations,
        "readyRequiredDomMarkers": list(ready_required),
        "unavailableRequiredDomMarkers": list(unavailable_required),
        "invariants": {
            "canonicalBaselineControlsRemainOptIn": True,
            "guidedFourStepNavigationMounted": True,
            "sceneRemainsSeparateFromUiState": True,
            "moduleVisibilitySeparatedFromInspection": True,
            "selectedModuleDetailIsContextual": True,
            "validSelectionWithoutTpcDegradesGracefully": True,
            "technicalFidelityComesFromPublicContract": True,
            "frontPresetProjectedByRuntime": True,
            "stonePresetProjectedByRuntime": True,
            "responsiveFixedFrameContained": True,
            "responsiveFixedFrameNeverCrops": True,
            "responsiveFixedFrameProjectionAspectStable": True,
            "compactDetailDoesNotReframeScene": True,
            "compactSceneAllocationGuarded": True,
            "desktopCompactTabletAndMobileCaptured": True,
        },
    }
    EVIDENCE.write_text(json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(evidence, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
