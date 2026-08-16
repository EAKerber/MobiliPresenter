from __future__ import annotations

import copy
import unittest

from tools.semantics import registry


class SemanticTopologyTests(unittest.TestCase):
    def setUp(self):
        self.value = registry.load_registry()

    def test_live_topology_is_valid(self):
        self.assertEqual([], registry.validate_registry(self.value))

    def test_managed_authorities_have_exactly_one_writer(self):
        for authority_id, item in self.value["managedAuthorities"].items():
            if not item["requiresCanonicalWriter"]:
                continue
            writers = [component_id for component_id, component in self.value["components"].items() if authority_id in component["writesAuthorities"]]
            canonical = [component_id for component_id, component in self.value["components"].items() if authority_id in component["canonicalWriterFor"]]
            self.assertEqual(1, len(writers), authority_id)
            self.assertEqual(writers, canonical, authority_id)

    def test_second_noncanonical_writer_is_rejected(self):
        broken = copy.deepcopy(self.value)
        broken["components"]["agent-cli"]["writesAuthorities"] = ["project-state"]
        self.assertIn("SEMANTIC_ADAPTER_DECLARED_WRITER", registry.validate_registry(broken))
        self.assertIn("SEMANTIC_AUTHORITY_WRITER_COUNT_INVALID", registry.validate_registry(broken))

    def test_second_canonical_writer_is_rejected(self):
        broken = copy.deepcopy(self.value)
        broken["components"]["agent-cli"]["writesAuthorities"] = ["project-state"]
        broken["components"]["agent-cli"]["canonicalWriterFor"] = ["project-state"]
        self.assertIn("SEMANTIC_AUTHORITY_CANONICAL_WRITER_COUNT_INVALID", registry.validate_registry(broken))

    def test_canonical_writer_must_also_write_authority(self):
        broken = copy.deepcopy(self.value)
        broken["components"]["project-state-executor"]["writesAuthorities"] = []
        self.assertIn("SEMANTIC_CANONICAL_WRITER_NOT_WRITER", registry.validate_registry(broken))

    def test_read_only_component_cannot_gain_side_effects(self):
        broken = copy.deepcopy(self.value)
        broken["components"]["scheduler-plan"]["sideEffects"] = True
        self.assertIn("SEMANTIC_READ_ONLY_COMPONENT_WRITES", registry.validate_registry(broken))

    def test_read_only_component_cannot_write_resource(self):
        broken = copy.deepcopy(self.value)
        broken["components"]["prune-plan"]["writesResources"] = ["git-branch-refs"]
        self.assertIn("SEMANTIC_READ_ONLY_COMPONENT_WRITES", registry.validate_registry(broken))

    def test_unknown_authority_reference_is_rejected(self):
        broken = copy.deepcopy(self.value)
        broken["components"]["project-machine"]["readsAuthorities"].append("missing-authority")
        self.assertIn("SEMANTIC_COMPONENT_AUTHORITY_UNKNOWN", registry.validate_registry(broken))

    def test_unknown_resource_reference_is_rejected(self):
        broken = copy.deepcopy(self.value)
        broken["components"]["prune-plan"]["readsResources"].append("missing-resource")
        self.assertIn("SEMANTIC_COMPONENT_RESOURCE_UNKNOWN", registry.validate_registry(broken))

    def test_unknown_artifact_reference_is_rejected(self):
        broken = copy.deepcopy(self.value)
        broken["components"]["scheduler-plan"]["produces"] = ["artifact.missing"]
        self.assertIn("SEMANTIC_COMPONENT_ARTIFACT_UNKNOWN", registry.validate_registry(broken))

    def test_unknown_delegation_is_rejected(self):
        broken = copy.deepcopy(self.value)
        broken["components"]["agent-cli"]["delegatesTo"] = ["missing-component"]
        self.assertIn("SEMANTIC_COMPONENT_DELEGATE_UNKNOWN", registry.validate_registry(broken))

    def test_self_delegation_is_rejected(self):
        broken = copy.deepcopy(self.value)
        broken["components"]["agent-cli"]["delegatesTo"] = ["agent-cli"]
        self.assertIn("SEMANTIC_COMPONENT_SELF_DELEGATION", registry.validate_registry(broken))

    def test_authority_projection_reports_writer_and_readers(self):
        value = registry.managed_authority("project-state")
        self.assertEqual("project-state-executor", value["canonicalWriter"])
        self.assertEqual(["project-state-executor"], value["writers"])
        self.assertIn("project-machine", value["readers"])

    def test_component_projection_reports_adapter_delegation(self):
        value = registry.component("continuation-live-cli")
        self.assertEqual("cli-adapter", value["kind"])
        self.assertEqual(["continuation-executor"], value["delegatesTo"])
        self.assertEqual([], value["writesAuthorities"])


if __name__ == "__main__":
    unittest.main()
