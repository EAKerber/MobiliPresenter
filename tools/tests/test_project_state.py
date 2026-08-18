import copy
import unittest

from tools import project_state, test_lifecycle


class ProjectStateTests(unittest.TestCase):
    def state(self):
        return {
            "schemaVersion": "ProjectState 2.0",
            "project": {"id": "mobilipresenter", "repository": "EAKerber/MobiliPresenter"},
            "git": {"controlBranch": "main", "activeDevelopmentBranch": None, "protectedBranches": ["coordination/leases"]},
            "published": {"url": "https://example.invalid/", "artifactManifest": "ops/published/viewer-next-current.json"},
            "development": {"initiative": "Viewer Next", "phase": "between-increments", "checkpoint": "C", "nextTransition": "next", "blockers": [], "prNumber": None},
        }

    def test_v2_is_the_only_current_contract(self):
        value = self.state()
        self.assertEqual(project_state.validate_current(value), [])
        self.assertEqual(project_state.operational_view(value), value | {"schemaVersion": value["schemaVersion"]} if False else {k: copy.deepcopy(value[k]) for k in ("project", "git", "published", "development")})
        old = copy.deepcopy(value)
        old["schemaVersion"] = "ProjectState 1.0"
        self.assertTrue(any(item["code"] == "STATE_SCHEMA_UNSUPPORTED" for item in project_state.validate_current(old)))

    def test_removed_baggage_is_rejected(self):
        cases = [
            ("top", "operations", {}),
            ("project", "productInvariants", {}),
            ("git", "publishedBranch", "main"),
            ("git", "preserveBranches", []),
            ("published", "release", "x"),
            ("published", "artifactSha256", "a" * 64),
            ("development", "constraints", []),
            ("development", "plan", "x"),
        ]
        for section, key, value in cases:
            with self.subTest(section=section, key=key):
                state = self.state()
                if section == "top":
                    state[key] = value
                else:
                    state[section][key] = value
                self.assertTrue(project_state.validate_current(state))

    @test_lifecycle.transitional_test(
        owner="operations-core",
        reason="ProjectState 2.0 temporarily owns development branch/PR atomicity before Work becomes the sole execution authority",
        retire_when=test_lifecycle.schema_field_absent(
            "ops/schemas/project-state.schema.json", "git.activeDevelopmentBranch"
        ),
    )
    def test_development_identity_remains_atomic(self):
        state = self.state()
        state["development"]["prNumber"] = 7
        self.assertTrue(any(item["code"] == "DEVELOPMENT_IDENTITY_INCOMPLETE" for item in project_state.validate_current(state)))


if __name__ == "__main__":
    unittest.main()
