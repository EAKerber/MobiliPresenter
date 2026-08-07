from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "tools" / "validate_i2.py"
SPEC = importlib.util.spec_from_file_location("validate_i2", VALIDATOR)
assert SPEC and SPEC.loader
validate_i2 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validate_i2)


class I2ContractsTest(unittest.TestCase):
    def module(self, number: int):
        return json.loads((ROOT / "prototype" / "i2-data" / f"module-{number:02d}.json").read_text(encoding="utf-8"))["module"]

    def test_validator(self):
        messages = validate_i2.validate()
        self.assertIn("item 03 topology: 4 drawers + 2 doors validated", messages)
        self.assertIn("item 02 freestanding stove fallback validated", messages)

    def test_gaveteiro_never_collapses_to_generic_three_panel_front(self):
        module = self.module(3)
        types = [item["type"] for item in module["frontTopology"]["elements"]]
        self.assertEqual(types.count("drawer"), 4)
        self.assertEqual(types.count("door"), 2)

    def test_upper_sink_preserves_microwave_niche(self):
        module = self.module(6)
        self.assertEqual(module["structuralFeatures"]["niches"], 1)
        self.assertEqual(module["structuralFeatures"]["flapDoors"], 1)
        self.assertIn("niche", [item["type"] for item in module["frontTopology"]["elements"]])

    def test_all_furniture_uses_user_depth_override(self):
        for number in range(1, 8):
            self.assertEqual(self.module(number)["dimensionsMm"]["depth"], 600)

    def test_side_panel_is_18mm_and_supports_lighting(self):
        module = self.module(4)
        self.assertEqual(module["dimensionsMm"]["thickness"], 18)
        self.assertIn("lighting-support", module["capabilities"])


if __name__ == "__main__":
    unittest.main()
