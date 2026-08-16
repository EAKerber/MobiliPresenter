from __future__ import annotations

import copy
import unittest

from tools.semantics import registry


class SemanticRegistryTests(unittest.TestCase):
    def test_live_registry_is_valid_and_sorted(self):
        value = registry.load_registry()
        self.assertEqual([], registry.validate_registry(value))
        self.assertEqual(sorted(value["owners"]), list(value["owners"]))
        self.assertEqual(sorted(value["concepts"]), list(value["concepts"]))

    def test_unknown_concept_fails_explicitly(self):
        with self.assertRaisesRegex(RuntimeError, "SEMANTIC_CONCEPT_UNKNOWN"):
            registry.concept("missing.concept")

    def test_legacy_alias_requires_retirement_target(self):
        value = registry.load_registry()
        broken = copy.deepcopy(value)
        broken["concepts"]["coordination.lease"]["aliases"][0].pop("retireBy")
        self.assertIn("SEMANTIC_ALIAS_RETIREMENT_REQUIRED", registry.validate_registry(broken))

    def test_unknown_owner_is_rejected(self):
        value = registry.load_registry()
        broken = copy.deepcopy(value)
        broken["concepts"]["identity.worker"]["owner"] = "unknown-owner"
        self.assertIn("SEMANTIC_CONCEPT_OWNER_UNKNOWN", registry.validate_registry(broken))

    def test_related_concepts_must_exist(self):
        value = registry.load_registry()
        broken = copy.deepcopy(value)
        broken["concepts"]["identity.worker"]["related"].append("identity.missing")
        self.assertIn("SEMANTIC_RELATED_UNKNOWN", registry.validate_registry(broken))

    def test_lock_resolves_as_legacy_alias_of_coordination_lease(self):
        resolved = registry.resolve_term("lock", scope="cli-name")
        self.assertEqual("coordination.lease", resolved["semanticId"])
        self.assertTrue(resolved["alias"])
        self.assertEqual("legacy", resolved["status"])
        self.assertEqual("M11", resolved["retireBy"])


if __name__ == "__main__":
    unittest.main()
