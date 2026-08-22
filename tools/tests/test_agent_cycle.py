import unittest

from tools import agent_cycle, project_machine, runtime_capabilities


class AgentCycleTests(unittest.TestCase):
    def test_entry_profiles_are_closed_and_non_mutating(self):
        profile = agent_cycle.entry_profile("manager-gitops", "inspect-and-plan")
        self.assertEqual(profile["lifecyclePhase"], "bootstrap")
        self.assertIn("repository:read", profile["scope"])
        self.assertNotIn("repository:write", profile["scope"])

    def test_local_cycle_has_hash_bound_baseline_and_executable_close_obligation(self):
        machine = project_machine.inspect_local()
        runtime = runtime_capabilities.build_inspection(
            {"schemaVersion": runtime_capabilities.PROVIDER_OBSERVATIONS_SCHEMA, "providers": {}}
        )
        profile = agent_cycle.entry_profile("manager-gitops", "inspect-and-plan")
        value = agent_cycle.build_context(
            role="manager-gitops",
            declared_intent="inspect-and-plan",
            lifecycle_phase=profile["lifecyclePhase"],
            objects=profile["objects"],
            operations=profile["operations"],
            scopes=profile["scope"],
            machine=machine,
            runtime_inspection=runtime,
        )
        agent_cycle.validate_context(value)
        self.assertTrue(value["closeRequirements"]["required"])
        self.assertTrue(value["closeRequirements"]["implemented"])
        self.assertIsNone(value["closeRequirements"]["nextSlice"])
        self.assertEqual(value["closeRequirements"]["schemaVersion"], "AgentCycleCloseContract 0.1")
        self.assertEqual(value["closeRequirements"]["reminder"], "CLOSE_REQUIRED_AFTER_WORK")
        self.assertFalse(value["authorizesMutation"])
        self.assertTrue(value["cycleId"].startswith("cycle-"))

    def test_unknown_entry_profile_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "AGENT_CYCLE_ENTRY_PROFILE_REQUIRED"):
            agent_cycle.entry_profile("manager-gitops", "governed-mutation")


if __name__ == "__main__":
    unittest.main()
