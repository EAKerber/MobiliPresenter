import copy
import importlib.util
import os
import unittest
from pathlib import Path
from unittest import mock

MODULE_PATH = Path(__file__).resolve().parents[1] / "agent.py"
spec = importlib.util.spec_from_file_location("agent_tool", MODULE_PATH)
agent = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(agent)


class GitOps12Tests(unittest.TestCase):
    def base_state(self):
        return {
            "schemaVersion": "ProjectState 1.0",
            "project": {"id": "mobilipresenter", "repository": "EAKerber/MobiliPresenter", "productInvariants": {}},
            "git": {
                "controlBranch": "main",
                "activeDevelopmentBranch": "renderer/fixed-view-realistic-v1",
                "publishedBranch": "main",
                "preserveBranches": ["integration/viewer-parallel-v0.1", "ui/product-shell-v0.1"],
            },
            "published": {
                "release": "ViewerNext",
                "url": "x",
                "artifactManifest": "ops/published/viewer-next-current.json",
                "artifactSha256": "0" * 64,
            },
            "development": {
                "initiative": "Renderer",
                "phase": "fidelity-harness",
                "checkpoint": "FH-00",
                "nextTransition": "fh-01",
                "blockers": [],
                "constraints": [],
                "plan": "docs/plans/fidelity-harness-v1.md",
                "prNumber": 6,
            },
            "operations": {
                "toolboxPhase": "phase-1.2-branch-hygiene",
                "canonicalState": "ops/state/project.json",
                "commands": ["status", "doctor", "verify", "checkpoint", "handoff", "git prune-plan"],
            },
        }

    def between_increments_state(self):
        state = self.base_state()
        state["git"]["activeDevelopmentBranch"] = None
        state["development"]["prNumber"] = None
        state["development"]["phase"] = "between-increments"
        return state

    def test_state_shape_accepts_git_ops_12_active_development(self):
        self.assertEqual(agent.validate_state_shape(self.base_state()), [])

    def test_state_shape_accepts_between_increments(self):
        self.assertEqual(agent.validate_state_shape(self.between_increments_state()), [])

    def test_state_shape_rejects_partial_development_identity(self):
        state = self.between_increments_state()
        state["development"]["prNumber"] = 99
        errors = agent.validate_state_shape(state)
        self.assertTrue(any(error["code"] == "DEVELOPMENT_IDENTITY_INCOMPLETE" for error in errors))

    def test_checkpoint_candidate_does_not_mutate_input(self):
        state = self.base_state()
        before = copy.deepcopy(state)
        candidate = agent.checkpoint_candidate(state, checkpoint="FH-01", next_transition="fh-02", phase=None)
        self.assertEqual(state, before)
        self.assertEqual(candidate["development"]["checkpoint"], "FH-01")
        self.assertEqual(candidate["development"]["nextTransition"], "fh-02")

    def test_ci_aggregation(self):
        self.assertEqual(agent.aggregate_ci([]), "unknown")
        self.assertEqual(agent.aggregate_ci([{"status": "IN_PROGRESS", "conclusion": None}]), "pending")
        self.assertEqual(agent.aggregate_ci([{"status": "COMPLETED", "conclusion": "FAILURE"}]), "failed")
        self.assertEqual(agent.aggregate_ci([{"status": "COMPLETED", "conclusion": "SUCCESS"}]), "green")

    def test_unexpected_branch_is_rejected(self):
        check = agent.git_context_check(self.base_state(), {"worktree": True, "branch": "random/branch"})
        self.assertEqual(check["status"], "FAIL")
        self.assertEqual(check["code"], "UNEXPECTED_BRANCH")

    def test_control_branch_is_valid_context(self):
        check = agent.git_context_check(self.base_state(), {"worktree": True, "branch": "main"})
        self.assertEqual(check["status"], "PASS")
        self.assertEqual(check["context"], "control")

    def test_preserved_parallel_branch_is_valid_context(self):
        check = agent.git_context_check(self.between_increments_state(), {"worktree": True, "branch": "ui/product-shell-v0.1"})
        self.assertEqual(check["status"], "PASS")
        self.assertEqual(check["context"], "preserved-parallel")

    def test_git_ops_branch_is_valid_operational_context(self):
        check = agent.git_context_check(self.between_increments_state(), {"worktree": True, "branch": "ops/git-ops-1.2"})
        self.assertEqual(check["status"], "PASS")
        self.assertEqual(check["context"], "operations")

    def test_ci_branch_name_uses_pull_request_head_ref(self):
        with mock.patch.dict(os.environ, {"GITHUB_HEAD_REF": "ops/git-ops-1.2", "GITHUB_REF_NAME": "31/merge"}, clear=False):
            self.assertEqual(agent.ci_branch_name(), "ops/git-ops-1.2")

    def test_branch_refs_prefers_origin_remote_inventory(self):
        remote = "origin/main\t" + "a" * 40 + "\norigin/ui/live\t" + "b" * 40 + "\norigin/HEAD\t" + "c" * 40
        with mock.patch.object(agent, "run_git", side_effect=[(True, remote)]):
            self.assertEqual(agent.branch_refs(), {"main": "a" * 40, "ui/live": "b" * 40})

    def test_prune_plan_protects_state_and_open_pr_heads(self):
        state = self.between_increments_state()
        refs = {
            "main": "a" * 40,
            "integration/viewer-parallel-v0.1": "b" * 40,
            "ui/product-shell-v0.1": "c" * 40,
            "ui/live-pr": "d" * 40,
            "tmp/old-preview": "e" * 40,
            "engine/old-slice": "f" * 40,
            "variant/legacy": "1" * 40,
            "docs/old": "2" * 40,
        }
        plan = agent.build_prune_plan(state, refs, {"ui/live-pr"})
        by_branch = {entry["branch"]: entry for entry in plan["entries"]}
        self.assertEqual(by_branch["main"]["action"], "keep")
        self.assertEqual(by_branch["integration/viewer-parallel-v0.1"]["action"], "keep")
        self.assertEqual(by_branch["ui/live-pr"]["action"], "keep")
        self.assertEqual(by_branch["tmp/old-preview"]["action"], "candidate")
        self.assertEqual(by_branch["engine/old-slice"]["action"], "candidate")
        self.assertEqual(by_branch["variant/legacy"]["action"], "archive-first")
        self.assertEqual(by_branch["docs/old"]["action"], "review")
        self.assertTrue(plan["applyEligible"])

    def test_prune_plan_hash_is_stable_and_ref_sensitive(self):
        state = self.between_increments_state()
        refs = {"main": "a" * 40, "tmp/old": "b" * 40}
        first = agent.build_prune_plan(state, refs, set())
        second = agent.build_prune_plan(state, dict(refs), set())
        self.assertEqual(first["planHash"], second["planHash"])
        refs["tmp/old"] = "c" * 40
        third = agent.build_prune_plan(state, refs, set())
        self.assertNotEqual(first["planHash"], third["planHash"])

    def test_prune_plan_without_remote_pr_observation_is_not_apply_eligible(self):
        plan = agent.build_prune_plan(self.between_increments_state(), {"main": "a" * 40}, None)
        self.assertFalse(plan["applyEligible"])
        self.assertFalse(plan["remoteOpenPrProtection"])


if __name__ == "__main__":
    unittest.main()
