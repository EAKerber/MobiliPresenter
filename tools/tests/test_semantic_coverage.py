from __future__ import annotations

import copy
import unittest

from tools.semantics import coverage
from tools.semantics.registry import load_registry


class OperationalSemanticsCoverageTests(unittest.TestCase):
    def test_live_inventory_has_complete_deterministic_coverage(self):
        first = coverage.build_inspection()
        second = coverage.build_inspection()
        self.assertEqual(first, second)
        self.assertTrue(first["coverageComplete"])
        self.assertTrue(all(not values for values in first["findings"].values()))
        self.assertEqual(26, first["catalogCounts"]["entrypoints"])
        self.assertEqual(6, first["catalogCounts"]["workflows"])
        self.assertEqual(coverage.validate_inspection(first), first)

    def test_missing_entrypoint_binding_is_explicit(self):
        registry = copy.deepcopy(load_registry())
        bindings = registry["toolSurfaces"]["python-module-cli"]["bindings"]
        registry["toolSurfaces"]["python-module-cli"]["bindings"] = [
            item for item in bindings if item["target"] != "semantic-cli"
        ]
        inspection = coverage.build_inspection(registry)
        self.assertIn(
            "tools/semantics/__main__.py",
            inspection["findings"]["missingEntrypointBindings"],
        )
        self.assertFalse(inspection["coverageComplete"])

    def test_unregistered_schema_is_explicit(self):
        registry = copy.deepcopy(load_registry())
        registry["contracts"].pop("ecosystem-maxims")
        inspection = coverage.build_inspection(registry)
        self.assertIn(
            "ops/schemas/ecosystem-maxims.schema.json",
            inspection["findings"]["unregisteredSchemas"],
        )
        self.assertFalse(inspection["coverageComplete"])

    def test_tampered_inspection_is_rejected(self):
        inspection = coverage.build_inspection()
        inspection["coverageComplete"] = False
        with self.assertRaisesRegex(
            RuntimeError, "OPERATIONAL_SEMANTICS_COVERAGE_MISMATCH"
        ):
            coverage.validate_inspection(inspection)


if __name__ == "__main__":
    unittest.main()
