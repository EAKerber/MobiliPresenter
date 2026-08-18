import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "prune_plan.py"
spec = importlib.util.spec_from_file_location("prune_plan", MODULE_PATH)
prune = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(prune)


class PrunePlan03Tests(unittest.TestCase):
    def state(self, protected=None):
        return {
            "schemaVersion": "ProjectState 2.0",
            "project": {"id": "mobilipresenter", "repository": "EAKerber/MobiliPresenter"},
            "git": {"controlBranch": "main", "activeDevelopmentBranch": None, "protectedBranches": list(protected or [])},
            "published": {"url": "x", "artifactManifest": "ops/published/viewer-next-current.json"},
            "development": {"initiative": "I", "phase": "between-increments", "checkpoint": "C", "nextTransition": "N", "blockers": [], "prNumber": None},
        }

    def build(self, refs, prs=None, ancestry=None, **kwargs):
        return prune.build_prune_plan(self.state(kwargs.pop("protected", None)), refs, [] if prs is None else prs, ancestry or {branch: "diverged" for branch in refs}, published_source_branch="main", **kwargs)

    def test_prefix_is_never_retention_or_delete_evidence(self):
        refs = {"main": "a" * 40, "archive/old": "b" * 40, "backup/old": "c" * 40, "variant/old": "d" * 40, "tmp/old": "e" * 40}
        by = {entry["branch"]: entry for entry in self.build(refs)["entries"]}
        for branch in refs:
            if branch != "main":
                self.assertEqual(by[branch]["action"], "review")
                self.assertFalse(by[branch]["autoDeleteEligible"])
        self.assertEqual(by["main"]["action"], "keep")

    def test_explicit_protection_wins_independent_of_name(self):
        refs = {"main": "a" * 40, "archive/old": "b" * 40}
        plan = self.build(refs, ancestry={"main": "identical-to-control", "archive/old": "ancestor-of-control"}, protected=["archive/old"])
        entry = next(item for item in plan["entries"] if item["branch"] == "archive/old")
        self.assertEqual(entry["action"], "keep")
        self.assertIn("project-state-protected", entry["protections"])

    def test_exact_merged_pr_head_is_delete_candidate(self):
        refs = {"main": "a" * 40, "work/operations/old": "b" * 40}
        prs = [{"number": 7, "state": "closed", "merged": True, "headRef": "work/operations/old", "headSha": "b" * 40}]
        entry = next(item for item in self.build(refs, prs=prs)["entries"] if item["branch"] == "work/operations/old")
        self.assertEqual(entry["action"], "delete-candidate")
        self.assertIn("merged-pr:7", entry["evidence"])

    def test_closed_unmerged_pr_text_is_not_lifecycle_evidence(self):
        refs = {"main": "a" * 40, "ops/old": "b" * 40}
        prs = [{"number": 8, "state": "closed", "merged": False, "headRef": "ops/old", "headSha": "b" * 40, "title": "Superseded", "body": "superseded by #9"}]
        entry = next(item for item in self.build(refs, prs=prs)["entries"] if item["branch"] == "ops/old")
        self.assertEqual(entry["action"], "review")
        self.assertEqual(entry["evidence"], [])

    def test_ancestor_of_control_is_objective_delete_evidence(self):
        refs = {"main": "a" * 40, "legacy/name": "b" * 40}
        plan = self.build(refs, ancestry={"main": "identical-to-control", "legacy/name": "ancestor-of-control"})
        entry = next(item for item in plan["entries"] if item["branch"] == "legacy/name")
        self.assertEqual(entry["action"], "delete-candidate")
        self.assertIn("ancestor-of-control", entry["evidence"])

    def test_open_and_protected_branches_override_evidence(self):
        refs = {"main": "a" * 40, "ops/live": "b" * 40, "other/protected": "c" * 40}
        prs = [{"number": 9, "state": "open", "merged": False, "headRef": "ops/live", "headSha": "b" * 40}]
        plan = self.build(refs, prs=prs, ancestry={branch: "ancestor-of-control" for branch in refs}, protected=["other/protected"])
        by = {entry["branch"]: entry for entry in plan["entries"]}
        self.assertEqual(by["ops/live"]["action"], "keep")
        self.assertIn("open-pr-head", by["ops/live"]["protections"])
        self.assertEqual(by["other/protected"]["action"], "keep")

    def test_open_pr_base_is_dynamic_protection(self):
        refs = {"main": "a" * 40, "feature/base": "b" * 40, "work/head": "c" * 40}
        prs = [{"number": 12, "state": "open", "merged": False, "headRef": "work/head", "headSha": "c" * 40, "baseRef": "feature/base"}]
        ancestry = {name: "ancestor-of-control" for name in refs}
        plan = self.build(refs, prs=prs, ancestry=ancestry)
        by = {entry["branch"]: entry for entry in plan["entries"]}
        self.assertEqual(plan["openPrBases"], ["feature/base"])
        self.assertIn("open-pr-base", by["feature/base"]["protections"])
        self.assertEqual(by["feature/base"]["action"], "keep")

    def test_current_head_must_match_merged_pr_head(self):
        refs = {"main": "a" * 40, "ops/old": "c" * 40}
        prs = [{"number": 10, "state": "closed", "merged": True, "headRef": "ops/old", "headSha": "b" * 40}]
        entry = next(item for item in self.build(refs, prs=prs)["entries"] if item["branch"] == "ops/old")
        self.assertEqual(entry["action"], "review")

    def test_exact_duplicate_of_integrated_head_becomes_candidate(self):
        refs = {"main": "a" * 40, "ops/integrated": "b" * 40, "misc/duplicate": "b" * 40}
        prs = [{"number": 11, "state": "closed", "merged": True, "headRef": "ops/integrated", "headSha": "b" * 40}]
        duplicate = next(item for item in self.build(refs, prs=prs)["entries"] if item["branch"] == "misc/duplicate")
        self.assertEqual(duplicate["action"], "delete-candidate")
        self.assertEqual(duplicate["duplicateOf"], ["ops/integrated"])

    def test_incomplete_observation_is_encoded_and_hashed(self):
        refs = {"main": "a" * 40}
        plan = prune.build_prune_plan(self.state(), refs, None, {"main": "identical-to-control"}, branch_inventory_complete=True, ancestry_complete=True, branch_inventory_source="remote-git-refs", remote_observation_error="PR_HISTORY_READ_FAILED", published_source_branch="main")
        self.assertFalse(plan["observations"]["complete"])
        self.assertEqual(plan["observations"]["prHistoryError"], "PR_HISTORY_READ_FAILED")
        body = {key: value for key, value in plan.items() if key != "planHash"}
        self.assertEqual(plan["planHash"], prune.stable_hash(body))

    def test_plan_hash_covers_inventory_source_and_provenance(self):
        refs = {"main": "a" * 40, "ops/x": "b" * 40}
        first = self.build(refs, branch_inventory_source="remote-git-refs")
        second = self.build(refs, branch_inventory_source="fixture")
        self.assertNotEqual(first["planHash"], second["planHash"])
        prs = [{"number": 12, "state": "closed", "merged": True, "headRef": "ops/x", "headSha": "b" * 40}]
        third = self.build(refs, prs=prs, branch_inventory_source="remote-git-refs")
        self.assertNotEqual(first["planHash"], third["planHash"])

    def test_branch_identity_is_observational_only(self):
        refs = {"main": "a" * 40, "work/operations/x": "b" * 40, "authority/operations/x": "c" * 40}
        by = {entry["branch"]: entry for entry in self.build(refs)["entries"]}
        self.assertEqual(by["work/operations/x"]["branchIdentity"]["semanticDomain"], "operations")
        self.assertEqual(by["authority/operations/x"]["branchIdentity"]["declaredClass"], "authority")
        self.assertEqual(by["work/operations/x"]["action"], "review")
        self.assertEqual(by["authority/operations/x"]["action"], "review")


if __name__ == "__main__":
    unittest.main()
