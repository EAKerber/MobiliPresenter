from __future__ import annotations

import copy
import unittest

from tools.semantics import registry


class SemanticRegistryTests(unittest.TestCase):
    def test_live_registry_is_valid_and_sorted(self):
        value = registry.load_registry()
        self.assertEqual([], registry.validate_registry(value))
        self.assertEqual("OperationalSemantics 0.3", value["schemaVersion"])
        self.assertEqual(sorted(value["owners"]), list(value["owners"]))
        self.assertEqual(sorted(value["concepts"]), list(value["concepts"]))
        self.assertEqual(sorted(value["components"]), list(value["components"]))
        self.assertEqual(sorted(value["logicalCapabilities"]), list(value["logicalCapabilities"]))
        self.assertEqual(sorted(value["providerProfiles"]), list(value["providerProfiles"]))
        self.assertEqual(sorted(value["toolSurfaces"]), list(value["toolSurfaces"]))

    def test_version_02_is_not_implicitly_accepted(self):
        value = registry.load_registry()
        broken = copy.deepcopy(value)
        broken["schemaVersion"] = "OperationalSemantics 0.2"
        self.assertIn("SEMANTIC_REGISTRY_SCHEMA_UNSUPPORTED", registry.validate_registry(broken))

    def test_runtime_capability_requires_observable_provider_requirements(self):
        value = registry.load_registry()
        broken = copy.deepcopy(value)
        broken["logicalCapabilities"]["github.repository.read"]["providerRequirements"] = {}
        self.assertIn("SEMANTIC_LOGICAL_CAPABILITY_RUNTIME_REQUIREMENTS_MISSING", registry.validate_registry(broken))

    def test_surface_binding_and_capability_descriptor_must_agree(self):
        value = registry.load_registry()
        broken = copy.deepcopy(value)
        broken["logicalCapabilities"]["semantics.inspect"]["toolSurfaces"] = ["python-module-cli"]
        self.assertIn("SEMANTIC_LOGICAL_CAPABILITY_SURFACE_BINDING_MISMATCH:semantics.inspect", registry.validate_registry(broken))

    def test_unknown_concept_fails_explicitly(self):
        with self.assertRaisesRegex(RuntimeError, "SEMANTIC_CONCEPT_UNKNOWN"):
            registry.concept("missing.concept")

    def test_legacy_alias_requires_retirement_target(self):
        value = registry.load_registry()
        broken = copy.deepcopy(value)
        broken["concepts"]["coordination.lease"]["aliases"] = [
            {"term": "synthetic-legacy", "scope": "test-scope", "status": "legacy"}
        ]
        self.assertIn("SEMANTIC_ALIAS_RETIREMENT_REQUIRED", registry.validate_registry(broken))

    def test_retired_lock_term_is_unknown(self):
        self.assertEqual([], registry.aliases_for("coordination.lease"))
        with self.assertRaisesRegex(RuntimeError, "SEMANTIC_TERM_UNKNOWN"):
            registry.resolve_term("lock", scope="cli-name")

    def test_retired_ops_term_is_unknown_but_historical_grammar_remains(self):
        self.assertEqual([], registry.aliases_for("branch.domain.operations"))
        self.assertIn("ops", registry.load_registry()["branchGrammar"]["legacyNamespaces"])
        with self.assertRaisesRegex(RuntimeError, "SEMANTIC_TERM_UNKNOWN"):
            registry.resolve_term("ops", scope="legacy-branch-namespace")

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


if __name__ == "__main__":
    unittest.main()
