import copy
import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "agent.py"
spec = importlib.util.spec_from_file_location("agent_tool", MODULE_PATH)
agent = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(agent)


class GitOps11Tests(unittest.TestCase):
    def base_state(self):
        return {
            "schemaVersion": "ProjectState 1.0",
            "project": {"id": "mobilipresenter", "repository": "EAKerber/MobiliPresenter", "productInvariants": {}},
            "git": {"controlBranch": "main", "activeDevelopmentBranch": "renderer/fixed-view-realistic-v1", "publishedBranch": "main"},
            "published": {"release": "V7.0-I5", "url": "x", "artifactManifest": "snapshot/mobile/manifest.json", "artifactSha256": "0" * 64},
            "development": {"initiative": "Renderer", "phase": "fidelity-harness", "checkpoint": "FH-00", "nextTransition": "fh-01", "blockers": [], "constraints": [], "plan": "docs/plans/fidelity-harness-v1.md", "prNumber": 6},
            "operations": {"toolboxPhase": "phase-1.1-coherence", "canonicalState": "ops/state/project.json", "commands": ["status", "doctor", "verify", "checkpoint", "handoff"]},
        }

    def test_state_shape_accepts_git_ops_11(self):
        self.assertEqual(agent.validate_state_shape(self.base_state()), [])

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


if __name__ == "__main__":
    unittest.main()
