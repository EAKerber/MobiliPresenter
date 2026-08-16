from __future__ import annotations

import unittest

from tools.semantics.branches import parse_branch_name


class SemanticBranchTests(unittest.TestCase):
    def test_main_is_canonical_control(self):
        value = parse_branch_name("main")
        self.assertEqual("canonical", value["grammar"])
        self.assertEqual("control", value["declaredClass"])

    def test_new_work_branch_is_canonical(self):
        value = parse_branch_name("work/ops/project-state-v2")
        self.assertEqual("canonical", value["grammar"])
        self.assertEqual("work", value["declaredClass"])
        self.assertEqual("ops", value["domain"])
        self.assertEqual("project-state-v2", value["slug"])

    def test_new_experiment_and_authority_branches_are_canonical(self):
        experiment = parse_branch_name("experiment/gitops/peer-recovery")
        authority = parse_branch_name("authority/coordination/leases")
        self.assertEqual("experiment", experiment["declaredClass"])
        self.assertEqual("authority", authority["declaredClass"])

    def test_current_namespaces_remain_legacy(self):
        for name in ("ops/m3.5a-semantic-core", "ui/style-guide-v0.1", "archive/v7.0-i5-recovery", "coordination/leases"):
            value = parse_branch_name(name)
            self.assertEqual("legacy", value["grammar"], name)
            self.assertIsNone(value["declaredClass"], name)

    def test_unknown_namespace_is_not_promoted_to_semantics(self):
        value = parse_branch_name("mystery/foo")
        self.assertEqual("legacy-unknown", value["grammar"])
        self.assertIsNone(value["declaredClass"])

    def test_branch_result_never_contains_retention_or_deletion_decisions(self):
        value = parse_branch_name("work/ops/example")
        forbidden = {"retained", "retention", "protected", "delete", "deletionEligible", "safeToDelete", "lifecycle"}
        self.assertTrue(forbidden.isdisjoint(value))


if __name__ == "__main__":
    unittest.main()
