import unittest
from unittest import mock

from tools import prune_plan as prune


class ManagedAuthorityPruneProtectionTests(unittest.TestCase):
    def state(self):
        return {
            "schemaVersion": "ProjectState 2.1",
            "project": {"id": "mobilipresenter", "repository": "EAKerber/MobiliPresenter"},
            "git": {"controlBranch": "main", "protectedBranches": []},
            "published": {"url": "x", "artifactManifest": "ops/published/viewer-next-current.json"},
            "development": {
                "initiative": "I",
                "phase": "between-increments",
                "checkpoint": "C",
                "nextTransition": "N",
            },
        }

    def build(self):
        refs = {
            "main": "a" * 40,
            "coordination/leases": "b" * 40,
            "coordination/continuations": "c" * 40,
        }
        ancestry = {branch: "ancestor-of-control" for branch in refs}
        ancestry["main"] = "identical-to-control"
        return prune.build_prune_plan(
            self.state(),
            refs,
            [],
            ancestry,
            work_items=[],
            work_authority_complete=True,
            work_authority_head="f" * 40,
            published_source_branch="main",
        )

    def test_git_authority_branches_are_derived_from_semantic_registry(self):
        self.assertEqual(
            prune.managed_git_authority_branches(),
            {"coordination/continuations", "coordination/leases"},
        )

    def test_managed_authorities_are_kept_without_projectstate_protection(self):
        plan = self.build()
        by_branch = {entry["branch"]: entry for entry in plan["entries"]}
        for branch in ("coordination/leases", "coordination/continuations"):
            entry = by_branch[branch]
            self.assertEqual(entry["action"], "keep")
            self.assertIn("managed-authority", entry["protections"])
            self.assertNotIn("project-state-protected", entry["protections"])
            self.assertIn("ancestor-of-control", entry["evidence"])

    def test_invalid_registry_fails_closed_before_branch_classification(self):
        with mock.patch.object(prune.semantic_registry, "load_registry", return_value={}), \
             mock.patch.object(prune.semantic_registry, "validate_registry", return_value=["SEMANTIC_TEST_INVALID"]):
            with self.assertRaisesRegex(RuntimeError, "SEMANTIC_REGISTRY_INVALID:SEMANTIC_TEST_INVALID"):
                self.build()


if __name__ == "__main__":
    unittest.main()
