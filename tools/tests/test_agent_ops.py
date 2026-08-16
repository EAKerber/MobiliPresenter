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
        state = self.between_increments_state(); state["development"]["prNumber"] = 99
        errors = agent.validate_state_shape(state)
        self.assertTrue(any(error["code"] == "DEVELOPMENT_IDENTITY_INCOMPLETE" for error in errors))

    def test_ci_aggregation(self):
        self.assertEqual(agent.aggregate_ci([]), "unknown")
        self.assertEqual(agent.aggregate_ci([{"status": "IN_PROGRESS", "conclusion": None}]), "pending")
        self.assertEqual(agent.aggregate_ci([{"status": "COMPLETED", "conclusion": "FAILURE"}]), "failed")
        self.assertEqual(agent.aggregate_ci([{"status": "COMPLETED", "conclusion": "SUCCESS"}]), "green")

    def test_verification_summary_distinguishes_unknown_from_failure(self):
        self.assertEqual(agent.verification_summary([{"status": "PASS"}]), {"status": "PASS", "ok": True, "complete": True})
        self.assertEqual(agent.verification_summary([{"status": "PASS"}, {"status": "UNKNOWN"}]), {"status": "UNKNOWN", "ok": True, "complete": False})
        self.assertEqual(agent.verification_summary([{"status": "UNKNOWN"}, {"status": "FAIL"}]), {"status": "FAIL", "ok": False, "complete": False})

    def test_invalid_verification_status_fails_closed(self):
        self.assertEqual(agent.verification_summary([{"status": "MAYBE"}]), {"status": "FAIL", "ok": False, "complete": False})

    def test_remote_unavailable_is_unknown_not_green(self):
        checks = agent.remote_verification_checks(self.base_state(), {"available": False, "reason": "GH_NOT_FOUND", "ci": "unknown"})
        self.assertEqual(checks[0]["status"], "UNKNOWN")
        self.assertEqual(checks[0]["code"], "REMOTE_OBSERVATION_UNAVAILABLE")

    def test_remote_ci_pending_and_unknown_are_unknown(self):
        state = self.base_state()
        remote = {"available": True, "developmentActive": True, "pr": {"number": 6, "headRef": "renderer/fixed-view-realistic-v1", "baseRef": "main", "state": "open"}, "ci": "pending"}
        checks = agent.remote_verification_checks(state, remote)
        self.assertEqual(checks[0]["status"], "PASS")
        self.assertEqual(checks[1]["status"], "UNKNOWN")
        self.assertEqual(checks[1]["code"], "REMOTE_CI_PENDING")
        remote["ci"] = "unknown"
        checks = agent.remote_verification_checks(state, remote)
        self.assertEqual(checks[1]["status"], "UNKNOWN")
        self.assertEqual(checks[1]["code"], "REMOTE_CI_UNKNOWN")

    def test_remote_green_and_failed_remain_decisive(self):
        state = self.base_state()
        remote = {"available": True, "developmentActive": True, "pr": {"number": 6, "headRef": "renderer/fixed-view-realistic-v1", "baseRef": "main", "state": "open"}, "ci": "green"}
        checks = agent.remote_verification_checks(state, remote)
        self.assertEqual(checks[1]["status"], "PASS")
        remote["ci"] = "failed"
        checks = agent.remote_verification_checks(state, remote)
        self.assertEqual(checks[1]["status"], "FAIL")
        self.assertEqual(checks[1]["code"], "REMOTE_CI_FAILED")

    def test_no_active_development_is_known_pass(self):
        checks = agent.remote_verification_checks(self.between_increments_state(), {"available": True, "developmentActive": False, "reason": "NO_ACTIVE_DEVELOPMENT", "ci": "unknown"})
        self.assertEqual(checks, [{"name": "remote-development", "status": "PASS", "code": "NO_ACTIVE_DEVELOPMENT"}])

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

    def test_legacy_ops_branch_is_valid_operational_context(self):
        check = agent.git_context_check(self.between_increments_state(), {"worktree": True, "branch": "ops/project-machine-m0-baseline"})
        self.assertEqual(check["status"], "PASS")
        self.assertEqual(check["context"], "operations")

    def test_canonical_work_operations_branch_is_valid_operational_context(self):
        check = agent.git_context_check(self.between_increments_state(), {"worktree": True, "branch": "work/operations/project-state-v2"})
        self.assertEqual(check["status"], "PASS")
        self.assertEqual(check["context"], "operations")

    def test_canonical_experiment_operations_branch_is_valid_operational_context(self):
        check = agent.git_context_check(self.between_increments_state(), {"worktree": True, "branch": "experiment/operations/peer-health"})
        self.assertEqual(check["status"], "PASS")
        self.assertEqual(check["context"], "operations")

    def test_authority_name_does_not_grant_operational_work_context(self):
        check = agent.git_context_check(self.between_increments_state(), {"worktree": True, "branch": "authority/operations/control"})
        self.assertEqual(check["status"], "FAIL")
        self.assertEqual(check["code"], "UNEXPECTED_BRANCH")

    def test_legacy_prune_classifier_is_removed(self):
        self.assertFalse(hasattr(agent, "build_prune_plan"))
        self.assertFalse(hasattr(agent, "stable_plan_hash"))

    def test_ci_branch_name_uses_pull_request_head_ref(self):
        with mock.patch.dict(os.environ, {"GITHUB_HEAD_REF": "work/operations/test", "GITHUB_REF_NAME": "31/merge"}, clear=False):
            self.assertEqual(agent.ci_branch_name(), "work/operations/test")


if __name__ == "__main__":
    unittest.main()
