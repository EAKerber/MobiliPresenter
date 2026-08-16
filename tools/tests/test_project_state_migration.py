import unittest

from tools import project_state


class ProjectStateMigrationMapTests(unittest.TestCase):
    def test_live_v1_migration_map_is_complete(self):
        state = project_state.load_state()
        mapping = project_state.load_json(project_state.MIGRATION_MAP_PATH)
        self.assertEqual(project_state.validate_current(state), [])
        self.assertEqual(project_state.validate_migration_map(mapping, state), [])

    def test_live_candidate_is_v2_valid_and_view_equivalent(self):
        state = project_state.load_state()
        candidate = project_state.migrate_v1_to_v2(state)
        self.assertEqual(project_state.validate_v2(candidate), [])
        self.assertEqual(project_state.operational_view(state), project_state.operational_view(candidate))
        self.assertEqual(candidate["git"]["protectedBranches"], state["git"]["preserveBranches"])

    def test_live_authority_is_not_migrated_in_m4a(self):
        state = project_state.load_state()
        self.assertEqual(state["schemaVersion"], "ProjectState 1.0")
        self.assertTrue(project_state.CURRENT_SCHEMA_PATH.is_file())
        self.assertTrue(project_state.CANDIDATE_V2_SCHEMA_PATH.is_file())


if __name__ == "__main__":
    unittest.main()
