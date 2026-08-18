import copy
import unittest

from tools import project_state, project_state_migration, test_lifecycle
from tools import transition_protocol as protocol


@test_lifecycle.transitional_suite(
    owner="operations-core",
    reason="Bounded proof for the one-time ProjectState 2.0 to 2.1 authority cutover",
    retire_when=test_lifecycle.schema_field_absent(
        "ops/schemas/project-state.schema.json", "git.activeDevelopmentBranch"
    ),
)
class ProjectStateMigrationTests(unittest.TestCase):
    def state(self):
        return {
            "schemaVersion": "ProjectState 2.0",
            "project": {"id": "mobilipresenter", "repository": "EAKerber/MobiliPresenter"},
            "git": {
                "controlBranch": "main",
                "activeDevelopmentBranch": None,
                "protectedBranches": ["coordination/leases"],
            },
            "published": {
                "url": "https://example.invalid/",
                "artifactManifest": "ops/published/viewer-next-current.json",
            },
            "development": {
                "initiative": "Viewer Next",
                "phase": "between-increments",
                "checkpoint": "C",
                "nextTransition": "next",
                "blockers": [],
                "prNumber": None,
            },
        }

    def test_candidate_removes_only_execution_fields_and_changes_schema_version(self):
        before = self.state()
        frozen = copy.deepcopy(before)
        candidate = project_state_migration.candidate_from_v20(before)
        self.assertEqual(before, frozen)
        self.assertEqual(candidate["schemaVersion"], "ProjectState 2.1")
        self.assertEqual(candidate["project"], before["project"])
        self.assertEqual(candidate["published"], before["published"])
        self.assertEqual(candidate["git"], {
            "controlBranch": before["git"]["controlBranch"],
            "protectedBranches": before["git"]["protectedBranches"],
        })
        self.assertEqual(candidate["development"], {
            key: before["development"][key]
            for key in ("initiative", "phase", "checkpoint", "nextTransition")
        })
        self.assertEqual(project_state_migration.validate_target(candidate), [])

    def test_plan_is_deterministic_and_bound_to_exact_before_state(self):
        before = self.state()
        first = project_state_migration.build_plan(before)
        second = project_state_migration.build_plan(copy.deepcopy(before))
        self.assertEqual(first, second)
        self.assertEqual(first["action"], "migrate-schema")
        self.assertEqual(first["intent"]["removedFields"], list(project_state_migration.REMOVED_FIELDS))
        self.assertEqual(first["beforeStateHash"], protocol.state_hash(before))
        self.assertEqual(first["afterStateHash"], protocol.state_hash(first["candidate"]))
        self.assertEqual(project_state_migration.validate_plan(first, before=before), first)

    def test_nonempty_legacy_execution_blocks_migration(self):
        cases = (
            ("branch", lambda value: value["git"].__setitem__("activeDevelopmentBranch", "work/ui/example")),
            ("pr", lambda value: (value["git"].__setitem__("activeDevelopmentBranch", "work/ui/example"), value["development"].__setitem__("prNumber", 7))),
            ("blockers", lambda value: value["development"].__setitem__("blockers", ["still-live"])),
        )
        for label, mutate in cases:
            with self.subTest(label=label):
                before = self.state()
                mutate(before)
                if label == "branch":
                    before["development"]["prNumber"] = 7
                with self.assertRaisesRegex(RuntimeError, "PROJECT_STATE_MIGRATION_LEGACY_EXECUTION_NOT_EMPTY"):
                    project_state_migration.build_plan(before)

    def test_candidate_drift_is_rejected_even_when_transition_hashes_are_recomputed(self):
        before = self.state()
        plan = project_state_migration.build_plan(before)
        plan["candidate"]["development"]["checkpoint"] = "MUTATED"
        plan["afterStateHash"] = protocol.state_hash(plan["candidate"])
        core = {key: copy.deepcopy(value) for key, value in plan.items() if key != "planHash"}
        plan["planHash"] = protocol.stable_hash(core)
        with self.assertRaisesRegex(RuntimeError, "PROJECT_STATE_MIGRATION_CANDIDATE_DRIFT"):
            project_state_migration.validate_plan(plan, before=before)

    def test_stale_before_state_is_rejected(self):
        before = self.state()
        plan = project_state_migration.build_plan(before)
        changed = copy.deepcopy(before)
        changed["development"]["checkpoint"] = "NEWER"
        with self.assertRaisesRegex(RuntimeError, "TRANSITION_PLAN_STALE"):
            project_state_migration.validate_plan(plan, before=changed)

    def test_target_rejects_removed_execution_fields(self):
        candidate = project_state_migration.candidate_from_v20(self.state())
        candidate["git"]["activeDevelopmentBranch"] = None
        self.assertTrue(project_state_migration.validate_target(candidate))

    def test_live_authority_is_safe_to_plan_without_mutation(self):
        before = project_state.load_state()
        plan = project_state_migration.build_plan(before)
        project_state_migration.validate_plan(plan, before=before)
        self.assertEqual(before["schemaVersion"], project_state.CURRENT_SCHEMA_VERSION)
        self.assertEqual(plan["candidate"]["schemaVersion"], project_state_migration.TARGET_SCHEMA_VERSION)


if __name__ == "__main__":
    unittest.main()
