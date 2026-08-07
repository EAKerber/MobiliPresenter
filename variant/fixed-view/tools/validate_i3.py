from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA_I3 = ROOT / "prototype" / "i3-data"
I2_VALIDATOR_PATH = ROOT / "tools" / "validate_i2.py"


class ValidationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def load_json(name: str) -> dict[str, Any]:
    return json.loads((DATA_I3 / name).read_text(encoding="utf-8"))


def load_i2_validator():
    spec = importlib.util.spec_from_file_location("validate_i2", I2_VALIDATOR_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate() -> list[str]:
    i2 = load_i2_validator()
    i2_messages = i2.validate()

    calibration = load_json("calibration.json")
    layers = load_json("visual-layers.json")

    require(calibration["status"] == "presentation-calibrated-not-fabrication-ready", "I3 status must make presentation-only calibration explicit")
    require(calibration["camera"]["mode"] == "fixed", "I3 requires a fixed camera")
    require(calibration["camera"]["metricCalibration"] is False, "camera must not claim metric calibration")
    require(calibration["evidenceSpace"]["kind"] == "reference-image-pixels", "evidence space must remain pixel based")
    require(calibration["evidenceSpace"]["metricMeaning"] == "none", "pixel coordinates must have no implicit metric meaning")
    require(calibration["metricEnvelope"]["wallWidthMm"] == 3550, "wall envelope must remain 3550 mm")
    require(calibration["metricEnvelope"]["policy"] == "global-envelope-only", "3550 mm must not be treated as per-object calibration")
    require(calibration["metricEnvelope"]["pixelToMmConversionAllowed"] is False, "pixel-to-mm derivation is forbidden")
    require(calibration["policies"]["fabricationUseAllowed"] is False, "presentation calibration must not be fabrication ready")
    require(calibration["policies"]["deriveMissingDimensionsFromPixels"] is False, "missing dimensions must not be synthesized from pixels")
    require(calibration["policies"]["unknownValuesRemainUnknown"] is True, "unknown values must remain explicit")

    module_ids = {item["moduleId"] for item in calibration["placements"]}
    expected_ids = {
        "upper-laundry", "lower-stove", "lower-sink", "refrigerator-side-panel",
        "upper-stove", "upper-sink", "upper-refrigerator", "lighting",
    }
    require(module_ids == expected_ids, "calibration must cover all eight modules")

    width = calibration["evidenceSpace"]["width"]
    height = calibration["evidenceSpace"]["height"]
    for item in calibration["placements"]:
        rect = item["rect"]
        require(item["confidence"] in {"low", "medium", "high"}, f"invalid confidence for {item['moduleId']}")
        require(bool(item["basis"]), f"missing evidence basis for {item['moduleId']}")
        require(rect["width"] > 0 and rect["height"] > 0, f"invalid visual rect for {item['moduleId']}")
        require(0 <= rect["x"] < width and 0 <= rect["y"] < height, f"visual rect starts outside evidence space: {item['moduleId']}")
        require(rect["x"] + rect["width"] <= width, f"visual rect exceeds evidence width: {item['moduleId']}")
        require(rect["y"] + rect["height"] <= height, f"visual rect exceeds evidence height: {item['moduleId']}")
        require(not any(key.lower().endswith("mm") for key in rect), f"metric coordinate leaked into visual rect: {item['moduleId']}")

    fallback = next(item for item in calibration["fallbacks"] if item["id"] == "freestanding-stove")
    require(fallback["when"]["moduleDisabled"] == "lower-stove", "freestanding stove calibration trigger mismatch")

    layer_ids = {item["moduleId"] for item in layers["moduleLayers"]}
    require(layer_ids == expected_ids, "visual layer manifest must cover all modules")
    require(layers["policies"]["structuralFallbackRequiredWhenRealisticAssetMissing"] is True, "missing realistic overlays must fall back structurally")
    require(layers["policies"]["fabricationGeometryRequiredForVisualAsset"] is False, "realistic visual work must be allowed before fabrication geometry is exact")

    lower_sink_layer = next(item for item in layers["moduleLayers"] if item["moduleId"] == "lower-sink")
    require(lower_sink_layer["topologyGate"] == "4-drawers-2-doors", "item 03 realistic overlay must retain gaveteiro topology gate")
    require(all(item["fallback"] == "topology-renderer" for item in layers["moduleLayers"]), "every module must remain visible through a structural fallback")

    loader = (ROOT / "prototype" / "i2" / "data-loader.js").read_text(encoding="utf-8")
    require("i3-data/calibration.json" in loader, "runtime must consume I3 calibration")
    require("metricUseAllowed: false" in loader, "runtime placement must remain presentation-only")

    return [
        *i2_messages,
        "I3 visual calibration validated",
        "pixel-to-mm derivation prohibited",
        "8 calibrated presentation placements validated",
        "8 realistic-layer slots with structural fallback validated",
        "item 03 realistic topology gate validated",
    ]


def main() -> None:
    for line in validate():
        print(line)


if __name__ == "__main__":
    main()
