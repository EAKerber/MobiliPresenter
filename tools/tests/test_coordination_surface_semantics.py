from __future__ import annotations

import unittest

from tools.semantics import registry
from tools.semantics import convergence


class CoordinationSurfaceSemanticsTests(unittest.TestCase):
    def setUp(self):
        self.value = registry.load_registry()

    def test_canonical_coordination_cli_is_adapter_not_writer(self):
        item = registry.component("coordination-cli")
        self.assertEqual("tools.coordination_cli", item["module"])
        self.assertEqual("cli-adapter", item["kind"])
        self.assertEqual([], item["writesAuthorities"])
        self.assertEqual(["coordination-executor"], item["delegatesTo"])
        self.assertEqual(
            ["artifact.receipt", "artifact.transition-plan"],
            item["produces"],
        )

    def test_legacy_lock_delegates_to_canonical_surface(self):
        item = registry.component("coordination-lock-cli")
        self.assertEqual("tools.lock", item["module"])
        self.assertEqual([], item["writesAuthorities"])
        self.assertEqual(["coordination-cli"], item["delegatesTo"])

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
        self.assertEqual(
            ["coordination.guard.inspect", "coordination.mutate"],
            matches[0]["capabilities"],
        )

    def test_convergence_classifies_thin_lock_wrapper(self):
        texts = {
            "tools/lock.py": (
                "from tools.coordination_cli import legacy_lock_main\n"
                "LEGACY_LOCK_WRAPPER = True\n"
            )
        }
        consumers = convergence._lock_consumers(self.value, texts)
        wrapper = [item for item in consumers if item["path"] == "tools/lock.py"]
        self.assertEqual(1, len(wrapper))
        self.assertEqual("LEGACY_COMPATIBILITY_WRAPPER", wrapper[0]["class"])
        self.assertTrue(wrapper[0]["blocking"])


if __name__ == "__main__":
    unittest.main()
