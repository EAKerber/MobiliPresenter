import json
import tempfile
import unittest
from pathlib import Path

from tools import project_state, project_state_apply, project_state_transition, test_lifecycle
from tools import transition_protocol as protocol


@test_lifecycle.transitional_suite(
    owner="project-state",
    reason="manual protectedBranches is being monotonically consumed until ProjectState no longer carries retention state",
    retire_when=test_lifecycle.schema_field_absent(
        "ops/schemas/project-state.schema.json", "git.protectedBranches"
    ),
)
class ProjectStateRetentionTransitionTests(unittest.TestCase):
    def state(self):
        return {
            "schemaVersion": "ProjectState 2.1",
            "project": {"id": "mobilipresenter", "repository": "EAKerber/MobiliPresenter"},
            "git": {
                "controlBranch": "main",
                "protectedBranches": [
                    "coordination/leases",
                    "coordination/continuations",
                    "archive/keep",
                ],
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
        return project_state_transition.shrink_protected_branches(
            self.state(),
            ["coordination/continuations", "coordination/leases"],
            validator=project_state.validate_current,
        )

    def test_plan_is_deterministic_order_independent_and_only_shrinks_retention(self):
        first = self.plan()
        second = project_state_transition.shrink_protected_branches(
            self.state(),
            ["coordination/leases", "coordination/continuations"],
            validator=project_state.validate_current,
        )
        self.assertEqual(first, second)
        self.assertEqual(first["action"], "shrink-protected-branches")
        self.assertEqual(
            first["intent"],
            {"remove": ["coordination/continuations", "coordination/leases"]},
        )
        self.assertEqual(first["candidate"]["git"]["protectedBranches"], ["archive/keep"])
        before = self.state()
        candidate = first["candidate"]
        self.assertEqual(candidate["project"], before["project"])
        self.assertEqual(candidate["published"], before["published"])
        self.assertEqual(candidate["development"], before["development"])
        self.assertEqual(candidate["git"]["controlBranch"], before["git"]["controlBranch"])

    def test_no_public_api_can_add_manual_retention(self):
        self.assertFalse(hasattr(project_state_transition, "set_protected_branches"))
        with self.assertRaisesRegex(RuntimeError, "PROJECT_STATE_RETENTION_REMOVE_UNKNOWN:archive/new"):
            project_state_transition.shrink_protected_branches(
                self.state(), ["archive/new"], validator=project_state.validate_current
            )

    def test_empty_and_duplicate_removals_fail_closed(self):
        with self.assertRaisesRegex(RuntimeError, "PROJECT_STATE_RETENTION_REMOVE_INVALID"):
            project_state_transition.shrink_protected_branches(
                self.state(), [], validator=project_state.validate_current
            )
        with self.assertRaisesRegex(RuntimeError, "PROJECT_STATE_RETENTION_REMOVE_DUPLICATE"):
            project_state_transition.shrink_protected_branches(
                self.state(),
                ["coordination/leases", "coordination/leases"],
                validator=project_state.validate_current,
            )

    def test_bound_validation_rejects_added_branch_even_after_rehash(self):
        plan = self.plan()
        plan["candidate"]["git"]["protectedBranches"].append("archive/injected")
        plan["afterStateHash"] = protocol.state_hash(plan["candidate"])
        core = {key: value for key, value in plan.items() if key != "planHash"}
        plan["planHash"] = protocol.stable_hash(core)
        with self.assertRaisesRegex(RuntimeError, "PROJECT_STATE_PLAN_DERIVATION_MISMATCH"):
            project_state_transition.validate_project_state_plan(
                plan,
                validator=project_state.validate_current,
                before=self.state(),
                bind_before=True,
            )

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
