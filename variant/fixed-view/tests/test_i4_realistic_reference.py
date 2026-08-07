from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CALIBRATION = ROOT / "prototype" / "i3-data" / "calibration.json"
I4_JS = ROOT / "prototype" / "i4" / "realistic-reference.js"
I4_CSS = ROOT / "prototype" / "i4" / "realistic-reference.css"


class I4RealisticReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.calibration = json.loads(CALIBRATION.read_text(encoding="utf-8"))
        cls.js = I4_JS.read_text(encoding="utf-8")
        cls.css = I4_CSS.read_text(encoding="utf-8")

    def test_architectural_column_dimensions_are_confirmed(self) -> None:
        column = self.calibration["architecture"]["laundryColumn"]
        self.assertEqual(column["wallSpanMm"], 739)
        self.assertEqual(column["internalProjectionMm"], 206)
        self.assertEqual(column["dimensionStatus"], "user-confirmed")

    def test_refrigerator_side_panel_remains_visually_thin(self) -> None:
        placement = next(
            item for item in self.calibration["placements"]
            if item["moduleId"] == "refrigerator-side-panel"
        )
        self.assertGreater(placement["rect"]["width"], 0)
        self.assertLessEqual(placement["rect"]["width"], 12)

    def test_realistic_layer_uses_supplied_reference_pixels(self) -> None:
        self.assertIn("assets.referenceComposition", self.js)
        self.assertIn("data-realistic-module-id", self.js)
        self.assertIn("realistic-reference-layer", self.js)

    def test_structural_scene_is_only_hidden_in_realistic_mode(self) -> None:
        self.assertIn('[data-base-mode="reference-context"] #scene-modules .scene-module[data-module-id]', self.css)
        self.assertIn("scene-fallback", self.css)

    def test_pixel_to_metric_inference_remains_forbidden(self) -> None:
        self.assertFalse(self.calibration["metricEnvelope"]["pixelToMmConversionAllowed"])
        self.assertFalse(self.calibration["policies"]["deriveMissingDimensionsFromPixels"])
        self.assertFalse(self.calibration["policies"]["fabricationUseAllowed"])


if __name__ == "__main__":
    unittest.main()
