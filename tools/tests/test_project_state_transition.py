import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import project_state
from tools import project_state_apply
from tools import project_state_transition
from tools import transition_protocol as protocol


class ProjectStateTransitionTests(unittest.TestCase):
    def state(self):
        return {
            "schemaVersion": "ProjectState 2.0",
            "project": {"id": "mobilipresenter", "repository": "EAKerber/MobiliPresenter"},
            "git": {"controlBranch": "main", "activeDevelopmentBranch": "work/operations/test-transition", "protectedBranches": []},
            "published": {"url": "https://example.invalid/", "artifactManifest": "ops/published/viewer-next-current.json"},
            "development": {"initiative": "Test", "phase": "active", "checkpoint": "BEFORE", "nextTransition": "next-before", "blockers": [], "prNumber": 1},
        }

    def plan(self):
        return project_state_transition.checkpoint(self.state(), "AFTER", "next-after", None, validator=project_state.validate_current)

    def test_checkpoint_plan_is_deterministic(self):
        first = self.plan(); second = self.plan()
        self.assertEqual(first, second)
        self.assertEqual(first["schemaVersion"], "TransitionPlan 0.1")
        self.assertEqual(first["candidate"]["development"]["checkpoint"], "AFTER")

    def test_checkpoint_plan_validation_binds_candidate_to_intent(self):
        plan = self.plan(); plan["candidate"]["development"]["checkpoint"] = "OTHER"
        plan["afterStateHash"] = protocol.state_hash(plan["candidate"])
        core = {key: value for key, value in plan.items() if key != "planHash"}; plan["planHash"] = protocol.stable_hash(core)
        with self.assertRaisesRegex(RuntimeError, "CHECKPOINT_PLAN_CANDIDATE_INTENT_MISMATCH"):
            project_state_transition.validate_checkpoint_plan(plan, validator=project_state.validate_current)

    def test_apply_guards_and_verified_receipt(self):
        plan = self.plan()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "project.json"; path.write_text(json.dumps(self.state()) + "\n", encoding="utf-8")
            loader = lambda: json.loads(path.read_text(encoding="utf-8"))
            with self.assertRaisesRegex(RuntimeError, "TRANSITION_EXPECTED_PLAN_REQUIRED"):
                project_state_apply.apply(plan, None, state_path=path, load_state=loader, validator=project_state.validate_current, observe_git=lambda: {"worktree": True, "branch": "work/operations/test-transition", "dirty": False})
            receipt = project_state_apply.apply(plan, plan["planHash"], state_path=path, load_state=loader, validator=project_state.validate_current, observe_git=lambda: {"worktree": True, "branch": "work/operations/test-transition", "dirty": False})
            self.assertTrue(receipt["verified"]); protocol.validate_receipt(receipt, plan)

    def test_post_write_failure_restores_previous_state(self):
        plan = self.plan()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "project.json"; original = json.dumps(self.state()) + "\n"; path.write_text(original, encoding="utf-8")
            loader = lambda: json.loads(path.read_text(encoding="utf-8"))
            with mock.patch("tools.project_state_apply.protocol.build_receipt", side_effect=RuntimeError("TEST_POST_WRITE_FAILURE")):
                with self.assertRaisesRegex(RuntimeError, "TEST_POST_WRITE_FAILURE"):
                    project_state_apply.apply(plan, plan["planHash"], state_path=path, load_state=loader, validator=project_state.validate_current, observe_git=lambda: {"worktree": True, "branch": "work/operations/test-transition", "dirty": False})
            self.assertEqual(path.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
