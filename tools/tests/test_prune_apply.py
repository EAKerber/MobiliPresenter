import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parents[1]
PLAN_SPEC = importlib.util.spec_from_file_location("prune_plan", TOOLS / "prune_plan.py")
plan_mod = importlib.util.module_from_spec(PLAN_SPEC)
assert PLAN_SPEC and PLAN_SPEC.loader
PLAN_SPEC.loader.exec_module(plan_mod)

import sys
sys.modules["prune_plan"] = plan_mod
APPLY_SPEC = importlib.util.spec_from_file_location("prune_apply", TOOLS / "prune_apply.py")
apply_mod = importlib.util.module_from_spec(APPLY_SPEC)
assert APPLY_SPEC and APPLY_SPEC.loader
APPLY_SPEC.loader.exec_module(apply_mod)


class PruneApplyTests(unittest.TestCase):
    def state(self):
        return {
            "schemaVersion": "ProjectState 2.0",
            "project": {"id": "mobilipresenter", "repository": "EAKerber/MobiliPresenter"},
            "git": {"controlBranch": "main", "activeDevelopmentBranch": None, "protectedBranches": []},
            "published": {"url": "x", "artifactManifest": "ops/published/viewer-next-current.json"},
            "development": {
                "initiative": "I", "phase": "between-increments", "checkpoint": "C",
                "nextTransition": "N", "blockers": [], "prNumber": None,
            },
        }

    def plan(self, two_candidates=False):
        refs = {"main": "a" * 40, "old/a": "b" * 40, "review/x": "c" * 40}
        if two_candidates:
            refs["old/b"] = "d" * 40
        ancestry = {branch: "diverged" for branch in refs}
        ancestry["main"] = "identical-to-control"
        ancestry["old/a"] = "ancestor-of-control"
        if two_candidates:
            ancestry["old/b"] = "ancestor-of-control"
        return plan_mod.build_prune_plan(
            self.state(), refs, [], ancestry,
            work_items=[], work_authority_complete=True, work_authority_head="f" * 40,
            published_source_branch="main",
        )

    def test_select_candidates_only_strong_unprotected(self):
        selected = apply_mod.select_candidates(self.plan())
        self.assertEqual([item["branch"] for item in selected], ["old/a"])

    def test_plan_hash_mismatch_is_rejected(self):
        plan = self.plan(); plan["planHash"] = "0" * 64
        with self.assertRaisesRegex(RuntimeError, "PLAN_HASH_MISMATCH"):
            apply_mod.select_candidates(plan)

    def test_expected_plan_is_required_and_exact_before_observation(self):
        plan = self.plan()
        with mock.patch.object(apply_mod, "observe_branch_inventory") as observe, mock.patch.object(apply_mod, "delete_remote_ref") as delete:
            with self.assertRaisesRegex(RuntimeError, "EXPECTED_PLAN_REQUIRED"):
                apply_mod.apply_plan(plan, None)
            observe.assert_not_called(); delete.assert_not_called()
        with mock.patch.object(apply_mod, "observe_branch_inventory") as observe, mock.patch.object(apply_mod, "delete_remote_ref") as delete:
            with self.assertRaisesRegex(RuntimeError, "EXPECTED_PLAN_MISMATCH"):
                apply_mod.apply_plan(plan, "0" * 64)
            observe.assert_not_called(); delete.assert_not_called()

    def test_load_plan_preserves_exact_materialized_plan(self):
        plan = self.plan()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plan.json"; path.write_text(json.dumps(plan), encoding="utf-8")
            self.assertEqual(apply_mod.load_plan(path), plan)

    def test_protected_candidate_is_rejected(self):
        plan = self.plan(); plan["entries"][1]["protections"] = ["open-pr-head"]
        plan["planHash"] = plan_mod.stable_hash({k: v for k, v in plan.items() if k != "planHash"})
        with self.assertRaisesRegex(RuntimeError, "PROTECTED_CANDIDATE"):
            apply_mod.select_candidates(plan)

    def test_incomplete_plan_is_rejected(self):
        plan = self.plan()
        plan["observations"]["workAuthorityComplete"] = False
        plan["observations"]["workAuthorityHead"] = None
        plan["observations"]["workAuthorityError"] = "CONTINUATION_REMOTE_UNAVAILABLE"
        plan["observations"]["complete"] = False
        plan["planHash"] = plan_mod.stable_hash({k: v for k, v in plan.items() if k != "planHash"})
        with self.assertRaisesRegex(RuntimeError, "PLAN_OBSERVATION_INCOMPLETE"):
            apply_mod.select_candidates(plan)

    def test_authorization_is_required_after_plan_identity(self):
        plan = self.plan()
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(apply_mod, "observe_branch_inventory") as observe:
            with self.assertRaisesRegex(RuntimeError, "DESTRUCTIVE_AUTHORIZATION_MISSING"):
                apply_mod.apply_plan(plan, plan["planHash"])
            observe.assert_not_called()

    def test_initial_inventory_drift_blocks_immediately(self):
        plan = self.plan()
        with mock.patch.dict(os.environ, {apply_mod.AUTH_ENV: "1"}, clear=False), mock.patch.object(apply_mod, "observe_branch_inventory", return_value={"main": "a" * 40}):
            with self.assertRaisesRegex(RuntimeError, "REF_INVENTORY_DRIFT:initial"):
                apply_mod.apply_plan(plan, plan["planHash"])

    def test_open_pr_appearing_after_plan_blocks_before_delete(self):
        plan = self.plan(); inventory = {"main": "a" * 40, "old/a": "b" * 40, "review/x": "c" * 40}
        with mock.patch.dict(os.environ, {apply_mod.AUTH_ENV: "1"}, clear=False), \
             mock.patch.object(apply_mod, "observe_branch_inventory", return_value=inventory), \
             mock.patch.object(apply_mod, "observe_open_prs_using_branch", return_value=[{"number": 99}]), \
             mock.patch.object(apply_mod, "delete_remote_ref") as delete:
            with self.assertRaisesRegex(RuntimeError, "STALE_PLAN:OPEN_PR_RELATION_APPEARED:old/a"):
                apply_mod.apply_plan(plan, plan["planHash"])
            delete.assert_not_called()

    def test_open_pr_base_is_reobserved_before_delete(self):
        with mock.patch.object(apply_mod, "observe_open_prs_for_branch", return_value=[]), \
             mock.patch.object(apply_mod, "gh_json", return_value=(True, [{"number": 12}])) as gh:
            observed = apply_mod.observe_open_prs_using_branch("EAKerber/MobiliPresenter", "feature/base")
        self.assertEqual([item["number"] for item in observed], [12])
        self.assertIn("base=feature%2Fbase", gh.call_args.args[0])

    def test_allowed_stale_inventory_is_only_deleted_refs_at_exact_sha(self):
        expected = {"main": "a" * 40}; deleted = {"old/a": "b" * 40, "old/b": "d" * 40}
        self.assertTrue(apply_mod.is_allowed_stale_inventory({**expected, "old/a": "b" * 40}, expected, deleted))
        self.assertFalse(apply_mod.is_allowed_stale_inventory({**expected, "old/a": "e" * 40}, expected, deleted))
        self.assertFalse(apply_mod.is_allowed_stale_inventory({"main": "f" * 40, "old/a": "b" * 40}, expected, deleted))
        self.assertFalse(apply_mod.is_allowed_stale_inventory({**expected, "new/ref": "1" * 40}, expected, deleted))

    def test_non_monotonic_replica_staleness_retries_across_deletes(self):
        plan = self.plan(two_candidates=True)
        initial = {"main": "a" * 40, "old/a": "b" * 40, "old/b": "d" * 40, "review/x": "c" * 40}
        after_a = {"main": "a" * 40, "old/b": "d" * 40, "review/x": "c" * 40}
        stale_a = dict(initial); after_b = {"main": "a" * 40, "review/x": "c" * 40}; stale_both = dict(initial)
        with mock.patch.dict(os.environ, {apply_mod.AUTH_ENV: "1"}, clear=False), \
             mock.patch.object(apply_mod, "observe_branch_inventory", side_effect=[initial, initial, stale_a, after_a, stale_a, after_a, stale_both, after_b, after_b]), \
             mock.patch.object(apply_mod, "observe_open_prs_using_branch", return_value=[]), \
             mock.patch.object(apply_mod, "delete_remote_ref") as delete, \
             mock.patch.object(apply_mod.time, "sleep"):
            result = apply_mod.apply_plan(plan, plan["planHash"])
        self.assertEqual(delete.call_count, 2)
        self.assertEqual(result["deletedCount"], 2)
        self.assertGreaterEqual(result["readbackRetries"], 3)
        self.assertEqual(result["readback"], "PASS")

    def test_unrelated_drift_during_retry_fails_immediately(self):
        expected = {"main": "a" * 40}; deleted = {"old/a": "b" * 40}; drift = {"main": "f" * 40, "old/a": "b" * 40}
        with mock.patch.object(apply_mod, "observe_branch_inventory", return_value=drift):
            with self.assertRaisesRegex(RuntimeError, "REF_INVENTORY_DRIFT:test"):
                apply_mod.wait_for_consistent_inventory("EAKerber/MobiliPresenter", expected, deleted, context="test", attempts=2, delay_seconds=0)


if __name__ == "__main__":
    unittest.main()
