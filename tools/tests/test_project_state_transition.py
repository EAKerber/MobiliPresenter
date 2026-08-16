import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import agent
from tools import project_state_apply
from tools import project_state_transition
from tools import transition_protocol as protocol


class ProjectStateTransitionTests(unittest.TestCase):
    def state(self):
        return {
            "schemaVersion": "ProjectState 1.0",
            "project": {"id": "mobilipresenter", "repository": "EAKerber/MobiliPresenter", "productInvariants": {}},
            "git": {
                "controlBranch": "main",
                "activeDevelopmentBranch": "ops/test-transition",
                "publishedBranch": "main",
                "preserveBranches": [],
            },
            "published": {
                "release": "ViewerNext",
                "url": "x",
                "artifactManifest": "ops/published/viewer-next-current.json",
                "artifactSha256": "0" * 64,
            },
            "development": {
                "initiative": "Test",
                "phase": "active",
                "checkpoint": "BEFORE",
                "nextTransition": "next-before",
                "blockers": [],
                "constraints": [],
                "plan": "docs/plans/developer-continuation-2026-08.md",
                "prNumber": 1,
            },
            "operations": {
                "toolboxPhase": "phase-1.2-branch-hygiene",
                "canonicalState": "ops/state/project.json",
                "commands": ["status", "doctor", "verify", "checkpoint", "handoff", "git prune-plan"],
            },
        }

    def plan(self):
        return project_state_transition.checkpoint(
            self.state(), "AFTER", "next-after", None, validator=agent.validate_state_shape
        )

    def test_checkpoint_plan_does_not_mutate_input_and_is_deterministic(self):
        state = self.state()
        before = json.loads(json.dumps(state))
        first = project_state_transition.checkpoint(state, "AFTER", "next-after", None, validator=agent.validate_state_shape)
        second = project_state_transition.checkpoint(state, "AFTER", "next-after", None, validator=agent.validate_state_shape)
        self.assertEqual(state, before)
        self.assertEqual(first, second)
        self.assertEqual(first["schemaVersion"], "TransitionPlan 0.1")
        self.assertEqual(first["domain"], "project-state")
        self.assertEqual(first["candidate"]["development"]["checkpoint"], "AFTER")

    def test_checkpoint_plan_validation_binds_candidate_to_intent(self):
        plan = self.plan()
        plan["candidate"]["development"]["checkpoint"] = "OTHER"
        plan["afterStateHash"] = protocol.state_hash(plan["candidate"])
        core = {key: value for key, value in plan.items() if key != "planHash"}
        plan["planHash"] = protocol.stable_hash(core)
        with self.assertRaisesRegex(RuntimeError, "CHECKPOINT_PLAN_CANDIDATE_INTENT_MISMATCH"):
            project_state_transition.validate_checkpoint_plan(plan, validator=agent.validate_state_shape)

    def test_apply_requires_expected_plan_and_exact_before_state(self):
        plan = self.plan()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "project.json"
            path.write_text(json.dumps(self.state()) + "\n", encoding="utf-8")
            loader = lambda: json.loads(path.read_text(encoding="utf-8"))
            observe = lambda: {"worktree": True, "branch": "ops/test-transition", "dirty": False}
            with self.assertRaisesRegex(RuntimeError, "TRANSITION_EXPECTED_PLAN_REQUIRED"):
                project_state_apply.apply(plan, None, state_path=path, load_state=loader, validator=agent.validate_state_shape, observe_git=observe)
            changed = self.state()
            changed["development"]["checkpoint"] = "DRIFT"
            path.write_text(json.dumps(changed) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "TRANSITION_PLAN_STALE"):
                project_state_apply.apply(plan, plan["planHash"], state_path=path, load_state=loader, validator=agent.validate_state_shape, observe_git=observe)
            self.assertEqual(loader()["development"]["checkpoint"], "DRIFT")

    def test_apply_guards_branch_and_dirty_worktree_before_write(self):
        plan = self.plan()
        for observed, code in [
            ({"worktree": True, "branch": "wrong", "dirty": False}, "CHECKPOINT_WRONG_BRANCH"),
            ({"worktree": True, "branch": "ops/test-transition", "dirty": True}, "CHECKPOINT_DIRTY_WORKTREE"),
        ]:
            with self.subTest(code=code), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "project.json"
                original = json.dumps(self.state()) + "\n"
                path.write_text(original, encoding="utf-8")
                loader = lambda: json.loads(path.read_text(encoding="utf-8"))
                with self.assertRaisesRegex(RuntimeError, code):
                    project_state_apply.apply(
                        plan, plan["planHash"], state_path=path, load_state=loader,
                        validator=agent.validate_state_shape, observe_git=lambda: observed,
                    )
                self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_valid_apply_returns_verified_receipt(self):
        plan = self.plan()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "project.json"
            path.write_text(json.dumps(self.state()) + "\n", encoding="utf-8")
            loader = lambda: json.loads(path.read_text(encoding="utf-8"))
            receipt = project_state_apply.apply(
                plan, plan["planHash"], state_path=path, load_state=loader,
                validator=agent.validate_state_shape,
                observe_git=lambda: {"worktree": True, "branch": "ops/test-transition", "dirty": False},
            )
            self.assertEqual(receipt["schemaVersion"], "TransitionReceipt 0.1")
            self.assertTrue(receipt["verified"])
            self.assertEqual(loader(), plan["candidate"])
            protocol.validate_receipt(receipt, plan)

    def test_post_write_failure_restores_previous_state(self):
        plan = self.plan()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "project.json"
            original = json.dumps(self.state()) + "\n"
            path.write_text(original, encoding="utf-8")
            loader = lambda: json.loads(path.read_text(encoding="utf-8"))
            with mock.patch("tools.project_state_apply.protocol.build_receipt", side_effect=RuntimeError("TEST_POST_WRITE_FAILURE")):
                with self.assertRaisesRegex(RuntimeError, "TEST_POST_WRITE_FAILURE"):
                    project_state_apply.apply(
                        plan, plan["planHash"], state_path=path, load_state=loader,
                        validator=agent.validate_state_shape,
                        observe_git=lambda: {"worktree": True, "branch": "ops/test-transition", "dirty": False},
                    )
            self.assertEqual(loader(), self.state())


if __name__ == "__main__":
    unittest.main()
