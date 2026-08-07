from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "tools" / "validate_i0.py"
SPEC = importlib.util.spec_from_file_location("validate_i0", VALIDATOR_PATH)
assert SPEC and SPEC.loader
validate_i0 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validate_i0)


class I0ContractsTest(unittest.TestCase):
    def test_full_validator(self) -> None:
        messages = validate_i0.validate()
        self.assertIn("8 modules validated", messages)

    def test_module_detail_has_no_price(self) -> None:
        modules = json.loads((ROOT / "data" / "modules.json").read_text(encoding="utf-8"))["modules"]
        self.assertTrue(all("price" not in module["detail"] for module in modules))

    def test_detail_preserves_scene(self) -> None:
        ui = json.loads((ROOT / "data" / "ui-state.json").read_text(encoding="utf-8"))
        self.assertEqual(ui["states"]["module-detail"]["sceneRegion"], "composition-visible-selected-highlight")

    def test_wall_conflict_is_not_silently_resolved(self) -> None:
        assembly = json.loads((ROOT / "data" / "assembly.json").read_text(encoding="utf-8"))
        self.assertIsNone(assembly["wallEnvelope"]["widthMm"])
        self.assertEqual({c["value"] for c in assembly["wallEnvelope"]["candidates"]}, {3550, 3573})


if __name__ == "__main__":
    unittest.main()
