import json
import tempfile
import unittest
from pathlib import Path

from tools import project_state, project_state_apply, project_state_transition
from tools import transition_protocol as protocol


class ProjectStateRetentionTransitionTests(unittest.TestCase):
    def state(self):
        return {
            "schemaVersion": "ProjectState 2.1",
            "project": {"id": "mobilipresenter", "repository": "EAKerber/MobiliPresenter"},
            "git": {
                "controlBranch": "main",
                "protectedBranches": ["coordination/leases", "archive/keep"],
            },
            "published": {"url": "https://example.invalid/", "artifactManifest": "ops/published/viewer-next-current.json"},
            "development": {
                "initiative": "Test",
                "phase": "between-increments",
                "checkpoint": "C",
                "nextTransition": "N",
            },
        }

    def plan(self):
        return project_state_transition.set_protected_branches(
            self.state(), ["archive/keep"], validator=project_state.validate_current
        )

    def test_plan_is_deterministic_and_only_changes_retention(self):
        first = self.plan()
        second = self.plan()
        self.assertEqual(first, second)
        self.assertEqual(first["action"], "set-protected-branches")
        self.assertEqual(first["candidate"]["git"]["protectedBranches"], ["archive/keep"])
        self.assertEqual(first["intent"]["removed"], ["coordination/leases"])
        self.assertEqual(first["intent"]["added"], [])
        before = self.state()
        candidate = first["candidate"]
        self.assertEqual(candidate["project"], before["project"])
        self.assertEqual(candidate["published"], before["published"])
        self.assertEqual(candidate["development"], before["development"])
        self.assertEqual(candidate["git"]["controlBranch"], before["git"]["controlBranch"])

    def test_validation_binds_candidate_to_intent_even_after_rehash(self):
        plan = self.plan()
        plan["candidate"]["git"]["protectedBranches"] = []
        plan["afterStateHash"] = protocol.state_hash(plan["candidate"])
        core = {key: value for key, value in plan.items() if key != "planHash"}
        plan["planHash"] = protocol.stable_hash(core)
        with self.assertRaisesRegex(RuntimeError, "PROJECT_STATE_PROTECTED_BRANCHES_PLAN_CANDIDATE_INTENT_MISMATCH"):
            project_state_transition.validate_protected_branches_plan(plan, validator=project_state.validate_current)

    def test_executor_reuses_expected_plan_readback_and_receipt_guards(self):
        plan = self.plan()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "project.json"
            path.write_text(json.dumps(self.state()) + "\n", encoding="utf-8")
            loader = lambda: json.loads(path.read_text(encoding="utf-8"))
            observe = lambda: {"worktree": True, "branch": "work/operations/m6b", "dirty": False}
            receipt = project_state_apply.apply(
                plan,
                plan["planHash"],
                state_path=path,
                load_state=loader,
                validator=project_state.validate_current,
                observe_git=observe,
            )
            self.assertTrue(receipt["verified"])
            self.assertEqual(receipt["afterStateHash"], receipt["readbackStateHash"])
            self.assertEqual(loader()["git"]["protectedBranches"], ["archive/keep"])
            protocol.validate_receipt(receipt, plan)


if __name__ == "__main__":
    unittest.main()
