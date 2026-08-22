from __future__ import annotations

import unittest
from pathlib import Path

from tools.semantics import registry

ROOT = Path(__file__).resolve().parents[2]


class CoordinationSurfaceSemanticsTests(unittest.TestCase):
    def setUp(self):
        self.value = registry.load_registry()

    def test_canonical_coordination_cli_is_adapter_not_writer(self):
        item = registry.component("coordination-cli")
        self.assertEqual("tools.coordination_cli", item["module"])
        self.assertEqual("cli-adapter", item["kind"])
        self.assertEqual([], item["writesAuthorities"])
        self.assertEqual(["coordination-executor"], item["delegatesTo"])
        self.assertEqual(["artifact.receipt", "artifact.transition-plan"], item["produces"])

    def test_legacy_lock_surface_is_absent(self):
        self.assertFalse((ROOT / "tools" / "lock.py").exists())
        self.assertNotIn("coordination-lock-cli", self.value["components"])
        bindings = self.value["toolSurfaces"]["python-module-cli"]["bindings"]
        self.assertFalse(any(item.get("target") == "coordination-lock-cli" for item in bindings))
        self.assertEqual([], registry.aliases_for("coordination.lease"))

    def test_coordination_authority_still_has_exactly_one_writer(self):
        writers = [
            component_id
            for component_id, item in self.value["components"].items()
            if "coordination-leases" in item["writesAuthorities"]
        ]
        self.assertEqual(["coordination-executor"], writers)

    def test_python_surface_binds_canonical_coordination_capabilities(self):
        bindings = self.value["toolSurfaces"]["python-module-cli"]["bindings"]
        matches = [item for item in bindings if item.get("target") == "coordination-cli"]
        self.assertEqual(1, len(matches))
        self.assertEqual(["coordination.guard.inspect", "coordination.mutate"], matches[0]["capabilities"])


if __name__ == "__main__":
    unittest.main()
