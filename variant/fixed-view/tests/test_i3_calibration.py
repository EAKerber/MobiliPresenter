from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "tools" / "validate_i3.py"
SPEC = importlib.util.spec_from_file_location("validate_i3", VALIDATOR_PATH)
assert SPEC and SPEC.loader
validate_i3 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validate_i3)


class I3CalibrationTest(unittest.TestCase):
    def test_full_validator(self) -> None:
        messages = validate_i3.validate()
        self.assertIn("I3 visual calibration validated", messages)
        self.assertIn("pixel-to-mm derivation prohibited", messages)

    def test_calibration_is_presentation_only(self) -> None:
        data = json.loads((ROOT / "prototype" / "i3-data" / "calibration.json").read_text(encoding="utf-8"))
        self.assertFalse(data["camera"]["metricCalibration"])
        self.assertFalse(data["metricEnvelope"]["pixelToMmConversionAllowed"])
        self.assertFalse(data["policies"]["fabricationUseAllowed"])
        self.assertFalse(data["policies"]["deriveMissingDimensionsFromPixels"])

    def test_every_module_has_calibration_and_visual_fallback(self) -> None:
        calibration = json.loads((ROOT / "prototype" / "i3-data" / "calibration.json").read_text(encoding="utf-8"))
        layers = json.loads((ROOT / "prototype" / "i3-data" / "visual-layers.json").read_text(encoding="utf-8"))
        calibrated = {item["moduleId"] for item in calibration["placements"]}
        layered = {item["moduleId"] for item in layers["moduleLayers"]}
        self.assertEqual(calibrated, layered)
        self.assertEqual(len(calibrated), 8)
        self.assertTrue(all(item["fallback"] == "topology-renderer" for item in layers["moduleLayers"]))

    def test_lower_sink_cannot_lose_drawer_bank_in_realistic_pipeline(self) -> None:
        layers = json.loads((ROOT / "prototype" / "i3-data" / "visual-layers.json").read_text(encoding="utf-8"))
        item = next(layer for layer in layers["moduleLayers"] if layer["moduleId"] == "lower-sink")
        self.assertEqual(item["topologyGate"], "4-drawers-2-doors")

    def test_stove_fallback_remains_calibrated(self) -> None:
        calibration = json.loads((ROOT / "prototype" / "i3-data" / "calibration.json").read_text(encoding="utf-8"))
        fallback = next(item for item in calibration["fallbacks"] if item["id"] == "freestanding-stove")
        self.assertEqual(fallback["when"]["moduleDisabled"], "lower-stove")
        self.assertIn(fallback["confidence"], {"low", "medium", "high"})


if __name__ == "__main__":
    unittest.main()
