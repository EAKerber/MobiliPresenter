from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "tools" / "validate_i1.py"
SPEC = importlib.util.spec_from_file_location("validate_i1", VALIDATOR_PATH)
assert SPEC and SPEC.loader
validate_i1 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validate_i1)


class I1ContractsTest(unittest.TestCase):
    def test_full_validator(self) -> None:
        messages = validate_i1.validate()
        self.assertIn("8 modules validated", messages)
        self.assertIn("3550 mm operational wall validated", messages)

    def test_layout_covers_catalog(self) -> None:
        modules = json.loads((ROOT / "data" / "modules.json").read_text(encoding="utf-8"))["modules"]
        layout = json.loads((ROOT / "data" / "i1-layout.json").read_text(encoding="utf-8"))
        self.assertEqual({module["id"] for module in modules}, {item["moduleId"] for item in layout["placements"]})

    def test_lighting_dependency_is_blocking_and_repairable(self) -> None:
        rules = json.loads((ROOT / "data" / "rules.json").read_text(encoding="utf-8"))["rules"]
        rule = next(item for item in rules if item["id"] == "lighting-requires-refrigerator-side-panel")
        self.assertEqual(rule["severity"], "blocking")
        self.assertEqual(rule["requires"]["moduleEnabled"], "refrigerator-side-panel")
        self.assertEqual(rule["resolution"]["type"], "offer-enable-module")

    def test_price_is_absent_from_detail_and_front_rules_remain(self) -> None:
        modules = json.loads((ROOT / "data" / "modules.json").read_text(encoding="utf-8"))["modules"]
        presets = json.loads((ROOT / "data" / "presets.json").read_text(encoding="utf-8"))
        self.assertTrue(all("price" not in module["detail"] for module in modules))
        self.assertEqual(presets["policies"]["carcassColor"]["value"], "white")
        self.assertTrue(presets["policies"]["customerOverride"]["allowed"])


if __name__ == "__main__":
    unittest.main()
