import copy
import unittest

from tools import project_state


class ProjectStateTests(unittest.TestCase):
    def state(self):
        return {
            "schemaVersion": "ProjectState 2.1",
            "project": {"id": "mobilipresenter", "repository": "EAKerber/MobiliPresenter"},
            "git": {"controlBranch": "main", "protectedBranches": ["coordination/leases"]},
            "published": {"url": "https://example.invalid/", "artifactManifest": "ops/published/viewer-next-current.json"},
            "development": {"initiative": "Viewer Next", "phase": "between-increments", "checkpoint": "C", "nextTransition": "next"},
        }

    def test_v21_is_the_only_current_contract(self):
        value = self.state()
        self.assertEqual(project_state.validate_current(value), [])
        self.assertEqual(
            project_state.operational_view(value),
            {k: copy.deepcopy(value[k]) for k in ("project", "git", "published", "development")},
        )
        old = copy.deepcopy(value)
        old["schemaVersion"] = "ProjectState 2.0"
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

    def test_execution_identity_is_not_part_of_projectstate_21(self):
        cases = [
            ("git", "activeDevelopmentBranch", None),
            ("development", "prNumber", None),
            ("development", "blockers", []),
        ]
        for section, key, value in cases:
            with self.subTest(field=f"{section}.{key}"):
                state = self.state()
                state[section][key] = value
                errors = project_state.validate_current(state)
                self.assertTrue(any(item["code"] == "STATE_SCHEMA_INVALID" for item in errors))


if __name__ == "__main__":
    unittest.main()
