import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "prune_plan.py"
spec = importlib.util.spec_from_file_location("prune_plan", MODULE_PATH)
prune = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(prune)


class PrunePlan02Tests(unittest.TestCase):
    def state(self):
        return {
            "schemaVersion": "ProjectState 1.0",
            "project": {"repository": "EAKerber/MobiliPresenter"},
            "git": {
                "controlBranch": "main",
                "publishedBranch": "main",
                "activeDevelopmentBranch": None,
                "preserveBranches": ["ui/preserved", "coordination/leases"],
            },
        }

    def test_prefix_is_never_delete_evidence(self):
        refs = {"main": "a" * 40, "engine/diverged": "b" * 40, "agent/unknown": "c" * 40}
        ancestry = {"main": "identical-to-control", "engine/diverged": "diverged", "agent/unknown": "diverged"}
        plan = prune.build_prune_plan(self.state(), refs, [], ancestry)
        by_branch = {e["branch"]: e for e in plan["entries"]}
        self.assertEqual(by_branch["engine/diverged"]["action"], "review")
        self.assertEqual(by_branch["agent/unknown"]["action"], "review")

    def test_open_and_preserved_branches_win_over_all_delete_evidence(self):
        refs = {"main": "a" * 40, "ui/preserved": "b" * 40, "ui/live": "c" * 40}
        prs = [{"number": 10, "state": "open", "merged": False, "headRef": "ui/live", "headSha": "c" * 40, "title": "WIP", "body": ""}]
        ancestry = {branch: "ancestor-of-control" for branch in refs}
        ancestry["main"] = "identical-to-control"
        plan = prune.build_prune_plan(self.state(), refs, prs, ancestry)
        by_branch = {e["branch"]: e for e in plan["entries"]}
        self.assertEqual(by_branch["ui/preserved"]["action"], "keep")
        self.assertIn("project-state-preserve", by_branch["ui/preserved"]["protections"])
        self.assertEqual(by_branch["ui/live"]["action"], "keep")
        self.assertIn("open-pr-head", by_branch["ui/live"]["protections"])

    def test_current_head_must_match_merged_pr_head(self):
        refs = {"main": "a" * 40, "ops/work": "c" * 40}
        prs = [{"number": 5, "state": "closed", "merged": True, "headRef": "ops/work", "headSha": "b" * 40, "title": "merged", "body": ""}]
        ancestry = {"main": "identical-to-control", "ops/work": "diverged"}
        plan = prune.build_prune_plan(self.state(), refs, prs, ancestry)
        entry = next(e for e in plan["entries"] if e["branch"] == "ops/work")
        self.assertEqual(entry["action"], "review")
        self.assertFalse(entry["prProvenance"][0]["headMatchesCurrent"])

    def test_exact_merged_pr_head_is_delete_candidate_even_after_squash(self):
        refs = {"main": "a" * 40, "ops/work": "b" * 40}
        prs = [{"number": 5, "state": "closed", "merged": True, "headRef": "ops/work", "headSha": "b" * 40, "title": "merged", "body": ""}]
        ancestry = {"main": "identical-to-control", "ops/work": "diverged"}
        plan = prune.build_prune_plan(self.state(), refs, prs, ancestry)
        entry = next(e for e in plan["entries"] if e["branch"] == "ops/work")
        self.assertEqual(entry["action"], "delete-candidate")
        self.assertIn("merged-pr:5", entry["evidence"])

    def test_terminal_superseded_body_requires_exact_head(self):
        refs = {"main": "a" * 40, "agent/old": "b" * 40}
        prs = [{"number": 56, "state": "closed", "merged": False, "headRef": "agent/old", "headSha": "b" * 40, "title": "Experimental", "body": "Superseded by #57."}]
        ancestry = {"main": "identical-to-control", "agent/old": "diverged"}
        plan = prune.build_prune_plan(self.state(), refs, prs, ancestry)
        entry = next(e for e in plan["entries"] if e["branch"] == "agent/old")
        self.assertEqual(entry["action"], "delete-candidate")
        self.assertIn("terminal-pr:superseded:56", entry["evidence"])

    def test_ancestor_of_control_is_strong_delete_evidence(self):
        refs = {"main": "a" * 40, "feature/absorbed": "b" * 40}
        ancestry = {"main": "identical-to-control", "feature/absorbed": "ancestor-of-control"}
        plan = prune.build_prune_plan(self.state(), refs, [], ancestry)
        entry = next(e for e in plan["entries"] if e["branch"] == "feature/absorbed")
        self.assertEqual(entry["action"], "delete-candidate")
        self.assertTrue(entry["autoDeleteEligible"])

    def test_exact_duplicate_of_integrated_head_becomes_candidate(self):
        refs = {"main": "a" * 40, "ops/integrated": "b" * 40, "ops/alias": "b" * 40}
        prs = [{"number": 38, "state": "closed", "merged": True, "headRef": "ops/integrated", "headSha": "b" * 40, "title": "merged", "body": ""}]
        ancestry = {"main": "identical-to-control", "ops/integrated": "diverged", "ops/alias": "diverged"}
        plan = prune.build_prune_plan(self.state(), refs, prs, ancestry)
        alias = next(e for e in plan["entries"] if e["branch"] == "ops/alias")
        self.assertEqual(alias["action"], "delete-candidate")
        self.assertEqual(alias["duplicateOf"], ["ops/integrated"])

    def test_archive_backup_and_variant_are_never_direct_delete(self):
        refs = {"main": "a" * 40, "archive/a": "b" * 40, "backup/b": "c" * 40, "variant/c": "d" * 40}
        ancestry = {branch: "ancestor-of-control" for branch in refs}
        ancestry["main"] = "identical-to-control"
        plan = prune.build_prune_plan(self.state(), refs, [], ancestry)
        by_branch = {e["branch"]: e for e in plan["entries"]}
        self.assertEqual(by_branch["archive/a"]["action"], "keep")
        self.assertEqual(by_branch["backup/b"]["action"], "keep")
        self.assertEqual(by_branch["variant/c"]["action"], "archive-first")

    def test_incomplete_pr_history_blocks_apply_eligibility(self):
        refs = {"main": "a" * 40, "ops/work": "b" * 40}
        ancestry = {"main": "identical-to-control", "ops/work": "ancestor-of-control"}
        plan = prune.build_prune_plan(self.state(), refs, None, ancestry)
        self.assertFalse(plan["applyEligible"])
        self.assertFalse(plan["observations"]["prHistoryComplete"])

    def test_plan_hash_changes_with_ref_or_pr_provenance(self):
        refs = {"main": "a" * 40, "ops/work": "b" * 40}
        ancestry = {"main": "identical-to-control", "ops/work": "diverged"}
        first = prune.build_prune_plan(self.state(), refs, [], ancestry)
        second = prune.build_prune_plan(self.state(), refs, [], ancestry)
        self.assertEqual(first["planHash"], second["planHash"])
        prs = [{"number": 5, "state": "closed", "merged": True, "headRef": "ops/work", "headSha": "b" * 40, "title": "merged", "body": ""}]
        third = prune.build_prune_plan(self.state(), refs, prs, ancestry)
        self.assertNotEqual(first["planHash"], third["planHash"])


if __name__ == "__main__":
    unittest.main()
