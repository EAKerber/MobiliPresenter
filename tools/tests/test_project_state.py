import copy
import unittest

from tools import project_state


class ProjectStateCompatibilityTests(unittest.TestCase):
    def v1(self):
        return {
            "schemaVersion": "ProjectState 1.0",
            "project": {"id": "mobilipresenter", "repository": "EAKerber/MobiliPresenter", "productInvariants": {"viewer": "fixed-camera"}},
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

    def test_v1_remains_current_during_m4a(self):
        self.assertEqual(project_state.validate_current(self.v1()), [])
        candidate = project_state.migrate_v1_to_v2(self.v1())
        errors = project_state.validate_current(candidate)
        self.assertTrue(any(item["code"] == "STATE_SCHEMA_UNSUPPORTED" for item in errors))

    def test_migration_is_pure_deterministic_and_v2_valid(self):
        state = self.v1()
        before = copy.deepcopy(state)
        first = project_state.migrate_v1_to_v2(state)
        second = project_state.migrate_v1_to_v2(state)
        self.assertEqual(state, before)
        self.assertEqual(first, second)
        self.assertEqual(project_state.validate_v2(first), [])
        self.assertNotIn("operations", first)
        self.assertNotIn("productInvariants", first["project"])
        self.assertNotIn("release", first["published"])
        self.assertNotIn("artifactSha256", first["published"])
        self.assertNotIn("plan", first["development"])
        self.assertNotIn("constraints", first["development"])
        self.assertNotIn("publishedBranch", first["git"])

    def test_operational_view_is_stable_across_versions(self):
        v1 = self.v1()
        v2 = project_state.migrate_v1_to_v2(v1)
        self.assertEqual(project_state.operational_view(v1), project_state.operational_view(v2))
        self.assertEqual(project_state.operational_view(v1)["git"]["protectedBranches"], v1["git"]["preserveBranches"])

    def test_v2_rejects_removed_baggage(self):
        value = project_state.migrate_v1_to_v2(self.v1())
        value["operations"] = {}
        errors = project_state.validate_v2(value)
        self.assertTrue(any(item["code"] == "STATE_SCHEMA_INVALID" for item in errors))

    def test_development_identity_is_still_atomic(self):
        value = project_state.migrate_v1_to_v2(self.v1())
        value["development"]["prNumber"] = 12
        errors = project_state.validate_v2(value)
        self.assertTrue(any(item["code"] == "DEVELOPMENT_IDENTITY_INCOMPLETE" for item in errors))


if __name__ == "__main__":
    unittest.main()
