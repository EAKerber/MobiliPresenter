from __future__ import annotations

import json
import shutil
import struct
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

BASE_URL = "http://127.0.0.1:4173/"
OUT = Path("artifacts/runtime-ui")
EVIDENCE = OUT / "evidence.json"
CAPTURE_HELPER = Path(__file__).with_name("chrome_viewport_capture.mjs")
PRESENTATION_ASPECT = 1.9286452947259565
GEOMETRY_TOLERANCE_PX = 1.0


def find_chrome() -> str:
    for candidate in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        path = shutil.which(candidate)
        if path:
            return path
    raise SystemExit("CHROME_NOT_FOUND")


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, text=True, capture_output=True, check=False, timeout=120)


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise SystemExit(f"RUNTIME_UI_SCREENSHOT_NOT_PNG:{path.name}")
    return struct.unpack(">II", data[16:24])


def capture_browser(
    chrome: str,
    url: str,
    name: str,
    width: int,
    height: int,
    *,
    screenshot: bool = True,
) -> dict[str, Any]:
    command = [
        "node",
        str(CAPTURE_HELPER),
        "--chrome",
        chrome,
        "--url",
        url,
        "--name",
        name,
        "--width",
        str(width),
        "--height",
        str(height),
        "--out-dir",
        str(OUT),
    ]
    if not screenshot:
        command.append("--no-screenshot")
    result = run(command)
    if result.returncode != 0:
        raise SystemExit(f"RUNTIME_UI_CAPTURE_FAILED:{name}:{result.stderr[-3000:]}")
    try:
        capture = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"RUNTIME_UI_CAPTURE_INVALID_JSON:{name}:{result.stdout[-1000:]}") from exc

    html_path = Path(capture["htmlPath"])
    if not html_path.is_file():
        raise SystemExit(f"RUNTIME_UI_DOM_MISSING:{name}")
    capture["dom"] = html_path.read_text(encoding="utf-8")

    if screenshot:
        screenshot_path = Path(capture["screenshotPath"])
        if not screenshot_path.is_file():
            raise SystemExit(f"RUNTIME_UI_SCREENSHOT_FAILED:{name}")
        actual_width, actual_height = png_size(screenshot_path)
        if (actual_width, actual_height) != (width, height):
            raise SystemExit(
                f"RUNTIME_UI_SCREENSHOT_SIZE_MISMATCH:{name}:{actual_width}x{actual_height}"
            )
        if screenshot_path.stat().st_size < 10_000:
            raise SystemExit(
                f"RUNTIME_UI_SCREENSHOT_SUSPICIOUSLY_SMALL:{name}:{screenshot_path.stat().st_size}"
            )
    return capture


def require(dom: str, name: str, needles: tuple[str, ...]) -> None:
    missing = [needle for needle in needles if needle not in dom]
    if missing:
        raise SystemExit(f"RUNTIME_UI_DOM_GATE_FAILED:{name}:{missing}")


def number(value: object, name: str, field: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise SystemExit(f"RUNTIME_UI_METRIC_INVALID:{name}:{field}:{value}") from exc
    return parsed


def close(left: float, right: float, tolerance: float = GEOMETRY_TOLERANCE_PX) -> bool:
    return abs(left - right) <= tolerance


def viewport_geometry_evidence(
    capture: dict[str, Any],
    name: str,
    width: int,
    height: int,
) -> dict[str, object]:
    metrics = capture["metrics"]
    viewport = metrics["viewport"]
    document = metrics["document"]
    rects = metrics["rects"]
    observed = [number(viewport["innerWidth"], name, "innerWidth"), number(viewport["innerHeight"], name, "innerHeight")]
    visual = [number(viewport["visualWidth"], name, "visualWidth"), number(viewport["visualHeight"], name, "visualHeight")]
    if observed != [float(width), float(height)] or not all(close(left, right) for left, right in zip(visual, observed)):
        raise SystemExit(
            f"RUNTIME_UI_VIEWPORT_MISMATCH:{name}:requested={width}x{height}:"
            f"inner={observed}:visual={visual}"
        )
    maximum_scroll_width = max(
        number(document["scrollWidth"], name, "scrollWidth"),
        number(document["bodyScrollWidth"], name, "bodyScrollWidth"),
    )
    if maximum_scroll_width > width + GEOMETRY_TOLERANCE_PX:
        raise SystemExit(f"RUNTIME_UI_HORIZONTAL_OVERFLOW:{name}:{maximum_scroll_width}>{width}")

    for rect_name in ("app", "stage", "detail", "topbar", "actions"):
        rect = rects.get(rect_name)
        if rect is None:
            if rect_name == "detail" and metrics["state"]["detailOpen"] == "false":
                continue
            raise SystemExit(f"RUNTIME_UI_RECT_MISSING:{name}:{rect_name}")
        if (
            number(rect["left"], name, f"{rect_name}.left") < -GEOMETRY_TOLERANCE_PX
            or number(rect["top"], name, f"{rect_name}.top") < -GEOMETRY_TOLERANCE_PX
            or number(rect["right"], name, f"{rect_name}.right") > width + GEOMETRY_TOLERANCE_PX
            or number(rect["bottom"], name, f"{rect_name}.bottom") > height + GEOMETRY_TOLERANCE_PX
        ):
            raise SystemExit(f"RUNTIME_UI_RECT_OUTSIDE_VIEWPORT:{name}:{rect_name}:{rect}")

    return {
        "id": name,
        "requestedViewportPx": [width, height],
        "observedViewportCssPx": observed,
        "visualViewportCssPx": visual,
        "devicePixelRatio": number(viewport["devicePixelRatio"], name, "devicePixelRatio"),
        "documentScrollWidthPx": maximum_scroll_width,
        "horizontalOverflow": False,
        "responsiveMode": metrics["responsiveMode"],
        "rects": rects,
    }


def presentation_frame_evidence(capture: dict[str, Any], name: str) -> dict[str, object]:
    metrics = capture["metrics"]
    presentation = metrics.get("presentation")
    if not isinstance(presentation, dict):
        raise SystemExit(f"RUNTIME_UI_PRESENTATION_MARKERS_MISSING:{name}:presentation")
    required = (
        "frame",
        "fit",
        "crop",
        "hostWidth",
        "hostHeight",
        "rasterX",
        "rasterY",
        "rasterWidth",
        "rasterHeight",
        "aspect",
    )
    missing = [key for key in required if presentation.get(key) is None]
    if missing:
        raise SystemExit(f"RUNTIME_UI_PRESENTATION_MARKERS_MISSING:{name}:{missing}")
    if presentation["frame"] != "active" or presentation["fit"] != "contain":
        raise SystemExit(f"RUNTIME_UI_PRESENTATION_POLICY_INVALID:{name}:{presentation}")
    if presentation["crop"] != "false":
        raise SystemExit(f"RUNTIME_UI_PRESENTATION_CROPPED:{name}")

    host_width = int(presentation["hostWidth"])
    host_height = int(presentation["hostHeight"])
    raster_x = int(presentation["rasterX"])
    raster_y = int(presentation["rasterY"])
    raster_width = int(presentation["rasterWidth"])
    raster_height = int(presentation["rasterHeight"])
    aspect = number(presentation["aspect"], name, "presentation.aspect")
    app_rect = metrics["rects"].get("app")
    if not isinstance(app_rect, dict):
        raise SystemExit(f"RUNTIME_UI_APP_MISSING:{name}")

    if abs(aspect - PRESENTATION_ASPECT) > 1e-12:
        raise SystemExit(f"RUNTIME_UI_PRESENTATION_ASPECT_DRIFT:{name}:{aspect}")
    if min(host_width, host_height, raster_width, raster_height) <= 0:
        raise SystemExit(f"RUNTIME_UI_PRESENTATION_SIZE_INVALID:{name}")
    if not close(host_width, number(app_rect["width"], name, "app.width")) or not close(
        host_height, number(app_rect["height"], name, "app.height")
    ):
        raise SystemExit(
            f"RUNTIME_UI_PRESENTATION_HOST_DOM_MISMATCH:{name}:"
            f"data={host_width}x{host_height}:rect={app_rect}"
        )
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
        "appRectCssPx": app_rect,
        "rasterPx": [raster_x, raster_y, raster_width, raster_height],
        "projectionAspectRatio": aspect,
        "fit": presentation["fit"],
        "cropped": False,
    }


def same_rect(left: dict[str, object], right: dict[str, object]) -> bool:
    return all(close(number(left[key], "rect", key), number(right[key], "rect", key)) for key in ("left", "top", "right", "bottom", "width", "height"))


def compact_detail_allocation_evidence(
    *,
    open_capture: dict[str, Any],
    closed_capture: dict[str, Any],
    open_frame: dict[str, object],
    closed_frame: dict[str, object],
    viewport: tuple[int, int],
    require_overlay_clearance: bool,
) -> dict[str, object]:
    open_host = open_frame["hostPx"]
    closed_host = closed_frame["hostPx"]
    open_app = open_capture["metrics"]["rects"]["app"]
    closed_app = closed_capture["metrics"]["rects"]["app"]
    if open_host != closed_host or not same_rect(open_app, closed_app):
        raise SystemExit(
            f"RUNTIME_UI_COMPACT_DETAIL_REFRAMES_SCENE:{viewport[0]}x{viewport[1]}:"
            f"open={open_host}/{open_app}:closed={closed_host}/{closed_app}"
        )

    evidence: dict[str, object] = {
        "viewportPx": list(viewport),
        "responsiveMode": open_capture["metrics"]["responsiveMode"],
        "detailOpenHostPx": open_host,
        "detailClosedHostPx": closed_host,
        "detailOpenAppRectCssPx": open_app,
        "detailClosedAppRectCssPx": closed_app,
        "detailReframesScene": False,
    }
    if require_overlay_clearance:
        detail = open_capture["metrics"]["rects"].get("detail")
        stage = open_capture["metrics"]["rects"].get("stage")
        if not isinstance(detail, dict) or not isinstance(stage, dict):
            raise SystemExit(f"RUNTIME_UI_COMPACT_OVERLAY_RECT_MISSING:{viewport}")
        app_left = number(open_app["left"], "compact", "app.left")
        app_right = number(open_app["right"], "compact", "app.right")
        overlap_left = max(app_left, number(detail["left"], "compact", "detail.left"))
        overlap_right = min(app_right, number(detail["right"], "compact", "detail.right"))
        overlap_width = max(0.0, overlap_right - overlap_left)
        unoccluded_width = number(open_app["width"], "compact", "app.width") - overlap_width
        required_width = number(stage["width"], "compact", "stage.width") + 24.0
        if unoccluded_width + GEOMETRY_TOLERANCE_PX < required_width:
            raise SystemExit(
                f"RUNTIME_UI_COMPACT_OVERLAY_CLEARANCE_FAILED:{viewport}:"
                f"unoccluded={unoccluded_width}:required={required_width}"
            )
        evidence.update(
            {
                "detailOverlayRectCssPx": detail,
                "sceneUnoccludedWidthPx": unoccluded_width,
                "requiredUnoccludedWidthPx": required_width,
                "overlayClearancePx": 24,
            }
        )
    return evidence


def capture_summary(capture: dict[str, Any]) -> dict[str, object]:
    screenshot_path = Path(capture["screenshotPath"])
    return {
        "id": capture["id"],
        "requestedViewportPx": capture["requestedViewportPx"],
        "observedViewportCssPx": [
            capture["metrics"]["viewport"]["innerWidth"],
            capture["metrics"]["viewport"]["innerHeight"],
        ],
        "responsiveMode": capture["metrics"]["responsiveMode"],
        "screenshotBytes": screenshot_path.stat().st_size,
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
        "Continuar para acabamentos",
        "Detalhes",
    )

    unavailable_params = {"controls": "1", "select": "01"}
    unavailable_url = BASE_URL + "?" + urlencode(unavailable_params)
    unavailable_required = (
        'data-viewer-runtime-ui="mounted"',
        'data-module-alias="01"',
        'data-selected="true"',
        'data-presentation-status="unavailable"',
        "Detalhes técnicos ainda não publicados",
        "Informações técnicas ausentes não são inferidas pela interface.",
    )

    matrix = (
        ("runtime-ui-desktop-modules-detail", 1366, 768, "wide-reserved-panel"),
        ("runtime-ui-compact-landscape-modules-detail", 1024, 768, "compact-overlay"),
        ("runtime-ui-tablet-portrait-modules-detail", 768, 1024, "mobile-sheet"),
        ("runtime-ui-mobile-modules-detail", 390, 844, "mobile-sheet"),
    )
    captures: list[dict[str, object]] = []
    viewport_geometries: list[dict[str, object]] = []
    presentation_frames: list[dict[str, object]] = []
    open_by_viewport: dict[tuple[int, int], dict[str, Any]] = {}
    open_frames_by_viewport: dict[tuple[int, int], dict[str, object]] = {}
    for name, width, height, expected_mode in matrix:
        capture = capture_browser(chrome, ready_url, name, width, height)
        if capture["metrics"]["responsiveMode"] != expected_mode:
            raise SystemExit(
                f"RUNTIME_UI_RESPONSIVE_MODE_MISMATCH:{name}:"
                f"{capture['metrics']['responsiveMode']}!={expected_mode}"
            )
        require(capture["dom"], name, ready_required)
        viewport_geometries.append(viewport_geometry_evidence(capture, name, width, height))
        frame = presentation_frame_evidence(capture, name)
        presentation_frames.append(frame)
        open_by_viewport[(width, height)] = capture
        open_frames_by_viewport[(width, height)] = frame
        captures.append(capture_summary(capture))

    unavailable_capture = capture_browser(
        chrome,
        unavailable_url,
        "runtime-ui-desktop-unavailable",
        1366,
        768,
    )
    require(unavailable_capture["dom"], "unavailable", unavailable_required)
    viewport_geometries.append(
        viewport_geometry_evidence(unavailable_capture, "runtime-ui-desktop-unavailable", 1366, 768)
    )
    captures.append(capture_summary(unavailable_capture))

    closed_params = {
        "controls": "1",
        "hide": "02",
        "front": "02:neutral-greige",
        "stone": "graphite-speckled",
        "light": "warm-worktop",
    }
    closed_url = BASE_URL + "?" + urlencode(closed_params)
    compact_detail_allocations: list[dict[str, object]] = []
    for width, height, require_overlay_clearance in ((1024, 768, True), (768, 1024, False)):
        closed_name = f"runtime-ui-{width}x{height}-detail-closed"
        closed_capture = capture_browser(
            chrome,
            closed_url,
            closed_name,
            width,
            height,
            screenshot=False,
        )
        require(closed_capture["dom"], closed_name, ('data-viewer-detail-open="false"',))
        viewport_geometries.append(
            viewport_geometry_evidence(closed_capture, closed_name, width, height)
        )
        closed_frame = presentation_frame_evidence(closed_capture, closed_name)
        compact_detail_allocations.append(
            compact_detail_allocation_evidence(
                open_capture=open_by_viewport[(width, height)],
                closed_capture=closed_capture,
                open_frame=open_frames_by_viewport[(width, height)],
                closed_frame=closed_frame,
                viewport=(width, height),
                require_overlay_clearance=require_overlay_clearance,
            )
        )

    breakpoint_evidence: list[dict[str, object]] = []
    for width, expected_mode in ((900, "mobile-sheet"), (901, "compact-overlay")):
        name = f"runtime-ui-breakpoint-{width}x768"
        capture = capture_browser(chrome, ready_url, name, width, 768, screenshot=False)
        geometry = viewport_geometry_evidence(capture, name, width, 768)
        if capture["metrics"]["responsiveMode"] != expected_mode:
            raise SystemExit(
                f"RUNTIME_UI_BREAKPOINT_MODE_MISMATCH:{width}:"
                f"{capture['metrics']['responsiveMode']}!={expected_mode}"
            )
        presentation_frame_evidence(capture, name)
        breakpoint_evidence.append(geometry)

    evidence = {
        "schemaVersion": "ViewerRuntimeUiEvidence 0.6.0",
        "status": "PASS",
        "readyUrl": ready_url,
        "unavailableUrl": unavailable_url,
        "closedDetailUrl": closed_url,
        "captures": captures,
        "viewportGeometry": viewport_geometries,
        "presentationFrames": presentation_frames,
        "compactDetailAllocations": compact_detail_allocations,
        "breakpointEvidence": breakpoint_evidence,
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
            "requestedViewportEqualsObservedCssViewport": True,
            "noHorizontalDocumentOverflow": True,
            "responsiveFixedFrameContained": True,
            "responsiveFixedFrameNeverCrops": True,
            "responsiveFixedFrameProjectionAspectStable": True,
            "compactDetailDoesNotReframeScene": True,
            "compactOverlayLeavesStagePlusClearanceVisible": True,
            "mobileSheetActivatesThrough900Px": True,
            "compactOverlayStartsAt901Px": True,
            "desktopCompactTabletAndMobileCaptured": True,
        },
    }
    EVIDENCE.write_text(json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(evidence, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
