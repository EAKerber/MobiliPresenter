from __future__ import annotations

import unittest

from tools.semantics.branches import parse_branch_name


class SemanticBranchTests(unittest.TestCase):
    def test_main_is_canonical_control(self):
        value = parse_branch_name("main")
        self.assertEqual("canonical", value["grammar"])
        self.assertEqual("control", value["declaredClass"])
        self.assertIsNone(value["semanticDomain"])

    def test_new_operations_work_branch_is_canonical_and_semantic(self):
        value = parse_branch_name("work/operations/project-state-v2")
        self.assertEqual("canonical", value["grammar"])
        self.assertEqual("work", value["declaredClass"])
        self.assertEqual("operations", value["domain"])
        self.assertEqual("operations", value["semanticDomain"])
        self.assertFalse(value["legacyAlias"])
        self.assertEqual("project-state-v2", value["slug"])

    def test_engine_and_ui_domains_are_shared_across_legacy_and_canonical_grammar(self):
        for domain in ("engine", "ui"):
            legacy = parse_branch_name(f"{domain}/legacy-slice")
            canonical = parse_branch_name(f"work/{domain}/new-slice")
            self.assertEqual(domain, legacy["semanticDomain"])
            self.assertEqual(domain, canonical["semanticDomain"])
            self.assertEqual("legacy", legacy["grammar"])
            self.assertEqual("canonical", canonical["grammar"])

    def test_legacy_ops_alias_resolves_to_operations(self):
        value = parse_branch_name("ops/m3.5b-consumer-convergence")
        self.assertEqual("legacy", value["grammar"])
        self.assertEqual("ops", value["namespace"])
        self.assertEqual("operations", value["semanticDomain"])
        self.assertTrue(value["legacyAlias"])

    def test_unknown_canonical_domain_is_syntactically_valid_but_not_semantically_invented(self):
        value = parse_branch_name("work/ops/project-state-v2")
        self.assertEqual("canonical", value["grammar"])
        self.assertEqual("ops", value["domain"])
        self.assertIsNone(value["semanticDomain"])
        self.assertFalse(value["legacyAlias"])

    def test_new_experiment_and_authority_branches_are_canonical(self):
        experiment = parse_branch_name("experiment/operations/peer-recovery")
        authority = parse_branch_name("authority/coordination/leases")
        self.assertEqual("experiment", experiment["declaredClass"])
        self.assertEqual("operations", experiment["semanticDomain"])
        self.assertEqual("authority", authority["declaredClass"])
        self.assertIsNone(authority["semanticDomain"])

    def test_current_namespaces_remain_legacy(self):
        for name in ("ops/m3.5a-semantic-core", "ui/style-guide-v0.1", "archive/v7.0-i5-recovery", "coordination/leases"):
            value = parse_branch_name(name)
            self.assertEqual("legacy", value["grammar"], name)
            self.assertIsNone(value["declaredClass"], name)

    def test_unknown_namespace_is_not_promoted_to_semantics(self):
        value = parse_branch_name("mystery/foo")
        self.assertEqual("legacy-unknown", value["grammar"])
        self.assertIsNone(value["declaredClass"])
        self.assertIsNone(value["semanticDomain"])

    def test_branch_result_never_contains_retention_or_deletion_decisions(self):
        value = parse_branch_name("work/operations/example")
        forbidden = {"retained", "retention", "protected", "delete", "deletionEligible", "safeToDelete", "lifecycle"}
        self.assertTrue(forbidden.isdisjoint(value))


if __name__ == "__main__":
    unittest.main()
