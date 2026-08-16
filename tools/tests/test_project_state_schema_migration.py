import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import project_state
from tools import project_state_apply
from tools import project_state_transition
from tools import transition_protocol as protocol


class ProjectStateSchemaMigrationTests(unittest.TestCase):
    def state(self):
        return {
            "schemaVersion": "ProjectState 1.0",
            "project": {
                "id": "mobilipresenter",
                "repository": "EAKerber/MobiliPresenter",
                "productInvariants": {"viewer": "fixed-camera"},
            },
            "git": {
                "controlBranch": "main",
                "activeDevelopmentBranch": None,
                "publishedBranch": "main",
                "preserveBranches": ["coordination/leases", "archive/example"],
            },
            "published": {
                "release": "ViewerNext",
                "url": "https://example.invalid/",
                "artifactManifest": "ops/published/viewer-next-current.json",
                "artifactSha256": "a" * 64,
            },
            "development": {
                "initiative": "Viewer Next",
                "phase": "between-increments",
                "checkpoint": "C",
                "nextTransition": "next",
                "blockers": [],
                "constraints": ["fixed-camera-is-product-invariant"],
                "plan": "docs/plans/developer-continuation-2026-08.md",
                "prNumber": None,
            },
            "operations": {
                "toolboxPhase": "phase-1.2-branch-hygiene",
                "canonicalState": "ops/state/project.json",
                "commands": ["status", "doctor", "verify", "checkpoint", "handoff", "git prune-plan"],
            },
        }

    def migration_map(self):
        return {
            "schemaVersion": "ProjectStateMigrationMap 0.1",
            "sourceVersion": "ProjectState 1.0",
            "targetVersion": "ProjectState 2.0",
            "baseline": "0" * 40,
            "fieldMappings": [
                {
                    "sourceField": "project.id",
                    "disposition": "retain",
                    "destination": "project.id",
                    "reason": "test",
                }
            ],
            "constraintMappings": [
                {
                    "sourceValue": "fixed-camera-is-product-invariant",
                    "class": "contract",
                    "destination": "docs/adr/0002-scene-core-boundaries.md",
                    "evidence": "test",
                    "status": "resolved",
                }
            ],
        }

    def plan(self, state=None, mapping=None):
        return project_state_transition.schema_migration(
            state or self.state(),
            mapping or self.migration_map(),
            source_control_head="1" * 40,
            source_state_blob_sha="2" * 40,
            work_branch="work/operations/project-state-v2-migration",
            source_validator=project_state.validate_v1,
            target_validator=project_state.validate_v2,
            migrate=project_state.migrate_v1_to_v2,
            validate_migration_map=project_state.validate_migration_map,
        )

    def apply(self, plan, path, *, mapping=None, authorized=True, git=None, control_head=None, state_blob=None):
        loader = lambda: json.loads(path.read_text(encoding="utf-8"))
        return project_state_apply.apply_schema_migration(
            plan,
            plan["planHash"],
            authorized=authorized,
            state_path=path,
            load_state=loader,
            source_validator=project_state.validate_v1,
            target_validator=project_state.validate_v2,
            migration_map_loader=lambda: copy.deepcopy(mapping or self.migration_map()),
            validate_migration_map=project_state.validate_migration_map,
            migrate=project_state.migrate_v1_to_v2,
            observe_git=lambda: git or {
                "worktree": True,
                "branch": "work/operations/project-state-v2-migration",
                "dirty": False,
            },
            observe_control_head=lambda: control_head or "1" * 40,
            observe_state_blob=lambda: state_blob or "2" * 40,
        )

    def test_plan_is_deterministic_and_candidate_preserves_operational_view(self):
        before = self.state()
        snapshot = copy.deepcopy(before)
        first = self.plan(before)
        second = self.plan(before)
        self.assertEqual(before, snapshot)
        self.assertEqual(first, second)
        self.assertEqual(first["action"], "schema-migration")
        self.assertEqual(first["intent"]["fromSchemaVersion"], "ProjectState 1.0")
        self.assertEqual(first["intent"]["toSchemaVersion"], "ProjectState 2.0")
        self.assertEqual(project_state.validate_v2(first["candidate"]), [])
        self.assertEqual(project_state.operational_view(before), project_state.operational_view(first["candidate"]))

    def test_apply_requires_expected_plan_and_explicit_authorization(self):
        plan = self.plan()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "project.json"
            path.write_text(json.dumps(self.state()) + "\n", encoding="utf-8")
            loader = lambda: json.loads(path.read_text(encoding="utf-8"))
            kwargs = dict(
                authorized=True,
                state_path=path,
                load_state=loader,
                source_validator=project_state.validate_v1,
                target_validator=project_state.validate_v2,
                migration_map_loader=lambda: self.migration_map(),
                validate_migration_map=project_state.validate_migration_map,
                migrate=project_state.migrate_v1_to_v2,
                observe_git=lambda: {"worktree": True, "branch": "work/operations/project-state-v2-migration", "dirty": False},
                observe_control_head=lambda: "1" * 40,
                observe_state_blob=lambda: "2" * 40,
            )
            with self.assertRaisesRegex(RuntimeError, "TRANSITION_EXPECTED_PLAN_REQUIRED"):
                project_state_apply.apply_schema_migration(plan, None, **kwargs)
            kwargs["authorized"] = False
            with self.assertRaisesRegex(RuntimeError, "PROJECT_STATE_SCHEMA_MIGRATION_AUTHORIZATION_REQUIRED"):
                project_state_apply.apply_schema_migration(plan, plan["planHash"], **kwargs)

    def test_guard_drift_and_active_development_fail_before_write(self):
        plan = self.plan()
        scenarios = [
            ({"control_head": "3" * 40}, "PROJECT_STATE_MIGRATION_SOURCE_CONTROL_HEAD_DRIFT"),
            ({"state_blob": "4" * 40}, "PROJECT_STATE_MIGRATION_SOURCE_STATE_BLOB_DRIFT"),
            ({"git": {"worktree": True, "branch": "work/operations/other", "dirty": False}}, "PROJECT_STATE_MIGRATION_WRONG_BRANCH"),
            ({"git": {"worktree": True, "branch": "work/operations/project-state-v2-migration", "dirty": True}}, "PROJECT_STATE_MIGRATION_DIRTY_WORKTREE"),
        ]
        for overrides, code in scenarios:
            with self.subTest(code=code), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "project.json"
                original = json.dumps(self.state()) + "\n"
                path.write_text(original, encoding="utf-8")
                with self.assertRaisesRegex(RuntimeError, code):
                    self.apply(plan, path, **overrides)
                self.assertEqual(path.read_text(encoding="utf-8"), original)

        active = self.state()
        active["git"]["activeDevelopmentBranch"] = "work/ui/example"
        active["development"]["prNumber"] = 7
        active_plan = self.plan(active)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "project.json"
            original = json.dumps(active) + "\n"
            path.write_text(original, encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "PROJECT_STATE_MIGRATION_ACTIVE_DEVELOPMENT"):
                self.apply(active_plan, path)
            self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_map_drift_and_rehashed_candidate_tampering_are_blocked(self):
        plan = self.plan()
        drifted_map = self.migration_map()
        drifted_map["fieldMappings"][0]["reason"] = "changed"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "project.json"
            original = json.dumps(self.state()) + "\n"
            path.write_text(original, encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "PROJECT_STATE_MIGRATION_MAP_HASH_DRIFT"):
                self.apply(plan, path, mapping=drifted_map)
            self.assertEqual(path.read_text(encoding="utf-8"), original)

        tampered = copy.deepcopy(plan)
        tampered["candidate"]["development"]["nextTransition"] = "tampered"
        tampered["afterStateHash"] = protocol.state_hash(tampered["candidate"])
        core = {key: value for key, value in tampered.items() if key != "planHash"}
        tampered["planHash"] = protocol.stable_hash(core)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "project.json"
            original = json.dumps(self.state()) + "\n"
            path.write_text(original, encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "PROJECT_STATE_MIGRATION_CANDIDATE_REBUILD_MISMATCH"):
                self.apply(tampered, path)
            self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_valid_apply_returns_verified_receipt_and_post_write_failure_rolls_back(self):
        plan = self.plan()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "project.json"
            path.write_text(json.dumps(self.state()) + "\n", encoding="utf-8")
            receipt = self.apply(plan, path)
            migrated = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(receipt["schemaVersion"], "TransitionReceipt 0.1")
            self.assertTrue(receipt["verified"])
            self.assertEqual(project_state.validate_v2(migrated), [])
            self.assertEqual(protocol.state_hash(migrated), plan["afterStateHash"])
            protocol.validate_receipt(receipt, plan)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "project.json"
            original = json.dumps(self.state()) + "\n"
            path.write_text(original, encoding="utf-8")
            with mock.patch("tools.project_state_apply.protocol.build_receipt", side_effect=RuntimeError("TEST_POST_WRITE_FAILURE")):
                with self.assertRaisesRegex(RuntimeError, "TEST_POST_WRITE_FAILURE"):
                    self.apply(plan, path)
            self.assertEqual(path.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
