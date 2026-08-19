import json
import unittest
from unittest import mock

from tools import agent


class AgentRuntimeCapabilityTests(unittest.TestCase):
    def test_doctor_exposes_runtime_capability_inspection_without_turning_unknown_into_failure(self):
        runtime = {
            "schemaVersion": "RuntimeCapabilityInspection 0.1",
            "providerObservationSchemaVersion": "RuntimeProviderObservations 0.1",
            "providers": {},
            "capabilities": {
                "github.repository.read": {
                    "status": "UNKNOWN",
                    "reasonCode": "PROVIDER_OBSERVATION_INCOMPLETE",
                    "requiredFeatures": ["repository-read"],
                    "supportedProviders": ["gh-api", "github-connector"],
                    "satisfiedProviders": [],
                    "providerEvaluations": [],
                }
            },
            "authorizesMutation": False,
            "inspectionHash": "a" * 64,
        }
        provider_observations = {
            "schemaVersion": "RuntimeProviderObservations 0.1",
            "providers": {},
        }
        with (
            mock.patch("tools.agent.runtime_capabilities.local_provider_observations", return_value=provider_observations),
            mock.patch("tools.agent.runtime_capabilities.build_inspection", return_value=runtime),
            mock.patch("tools.agent.project_state.load_state", return_value={}),
            mock.patch("tools.agent.project_state.validate_current", return_value=[]),
            mock.patch("tools.agent.observed_git", return_value={"worktree": True, "origin": "https://github.com/EAKerber/MobiliPresenter.git"}),
            mock.patch("builtins.print") as output,
        ):
            self.assertEqual(agent.command_doctor(True), 0)
        rendered = output.call_args.args[0]
        payload = json.loads(rendered)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["runtimeCapabilities"]["capabilities"]["github.repository.read"]["status"], "UNKNOWN")
        self.assertFalse(payload["runtimeCapabilities"]["authorizesMutation"])


if __name__ == "__main__":
    unittest.main()
