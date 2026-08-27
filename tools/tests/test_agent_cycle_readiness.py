from __future__ import annotations

import copy
import unittest

from tools import agent_cycle, agent_cycle_close, project_machine, runtime_capabilities
from tools.canonical import stable_hash


def _context(intent: str) -> dict:
    machine = project_machine.inspect_local()
    runtime = runtime_capabilities.build_inspection(
        {
            "schemaVersion": runtime_capabilities.PROVIDER_OBSERVATIONS_SCHEMA,
            "providers": {},
        }
    )
    profile = agent_cycle.entry_profile("manager-gitops", intent)
    return agent_cycle.build_context(
        role="manager-gitops",
        declared_intent=intent,
        lifecycle_phase=profile["lifecyclePhase"],
        objects=profile["objects"],
        operations=profile["operations"],
        scopes=profile["scope"],
        machine=machine,
        runtime_inspection=runtime,
    )


def _rehash(value: dict) -> dict:
    value["baseline"]["baselineHash"] = stable_hash(
        {key: item for key, item in value["baseline"].items() if key != "baselineHash"}
    )
    value["cycleId"] = f"cycle-{value['baseline']['baselineHash'][:20]}"
    value["contextHash"] = stable_hash(
        {key: item for key, item in value.items() if key != "contextHash"}
    )
    return value


class AgentCycleReadinessTests(unittest.TestCase):
    def test_governed_mutation_separates_context_from_execution_readiness(self):
        context = _context("governed-mutation")
        readiness = context["readiness"]

        self.assertEqual(context["schemaVersion"], "AgentCycleContext 0.3")
        self.assertEqual(context["status"], "READY")
        self.assertEqual(readiness["legacyStatus"], "READY")
        self.assertEqual(readiness["contextStatus"], {"status": "PASS", "reasonCodes": []})
        self.assertEqual(readiness["intentReadiness"], {"status": "PASS", "reasonCodes": []})
        self.assertEqual(readiness["toolReadiness"]["status"], "UNKNOWN")
        self.assertEqual(
            readiness["providerResolution"]["reasonCodes"],
            ["CAPABILITY_NOT_AVAILABLE:remote.canonical.execute"],
        )
        self.assertEqual(
            readiness["mutationAuthorization"],
            {
                "status": "UNKNOWN",
                "reasonCodes": ["OPERATION_AUTHORIZATION_NOT_EVALUATED"],
            },
        )
        self.assertFalse(readiness["authorizesMutation"])

    def test_multi_tool_intent_does_not_claim_a_provider_before_operation_selection(self):
        readiness = _context("inspect-and-plan")["readiness"]

        self.assertEqual(readiness["toolReadiness"]["status"], "PASS")
        self.assertEqual(
            readiness["providerResolution"],
            {"status": "UNKNOWN", "reasonCodes": ["OPERATION_NOT_SELECTED"]},
        )
        self.assertEqual(
            readiness["mutationAuthorization"],
            {"status": "NOT_APPLICABLE", "reasonCodes": []},
        )

    def test_intent_without_agent_tool_surface_is_explicitly_blocked_at_tool_dimension(self):
        context = _context("bootstrap-discovery")

        self.assertEqual(context["status"], "READY")
        self.assertEqual(
            context["readiness"]["toolReadiness"],
            {"status": "BLOCKED", "reasonCodes": ["NO_TOOL_SURFACE_FOR_INTENT"]},
        )
        self.assertEqual(
            context["readiness"]["providerResolution"],
            {
                "status": "UNKNOWN",
                "reasonCodes": ["NO_TOOL_SURFACE_FOR_PROVIDER_RESOLUTION"],
            },
        )

    def test_v02_context_remains_readable_without_dimensional_promotion(self):
        legacy = copy.deepcopy(_context("inspect-and-plan"))
        legacy["schemaVersion"] = agent_cycle.PREVIOUS_SCHEMA_VERSION
        legacy.pop("readiness")
        legacy["baseline"].pop("readinessHash")
        _rehash(legacy)

        self.assertEqual(agent_cycle.validate_context(legacy), legacy)
        self.assertNotIn("readiness", legacy)

        delta = agent_cycle_close.build_delta(legacy, _context("inspect-and-plan"))
        self.assertEqual(delta["durableChanges"], [])
        self.assertEqual(
            [item["artifact"] for item in delta["derivedChanges"]],
            ["readinessHash"],
        )

    def test_v01_context_remains_readable_without_tool_or_readiness_projection(self):
        legacy = copy.deepcopy(_context("inspect-and-plan"))
        legacy["schemaVersion"] = agent_cycle.LEGACY_SCHEMA_VERSION
        legacy.pop("readiness")
        legacy.pop("agentTools")
        legacy["baseline"].pop("readinessHash")
        legacy["baseline"].pop("agentToolProjectionHash")
        _rehash(legacy)

        self.assertEqual(agent_cycle.validate_context(legacy), legacy)
        self.assertNotIn("readiness", legacy)
        self.assertNotIn("agentTools", legacy)

    def test_rehashed_readiness_cannot_promote_authorization(self):
        context = _context("governed-mutation")
        context["readiness"]["mutationAuthorization"] = {
            "status": "PASS",
            "reasonCodes": [],
        }
        readiness_core = {
            key: item
            for key, item in context["readiness"].items()
            if key != "readinessHash"
        }
        context["readiness"]["readinessHash"] = stable_hash(readiness_core)
        context["baseline"]["readinessHash"] = context["readiness"]["readinessHash"]
        _rehash(context)

        with self.assertRaisesRegex(
            RuntimeError, "AGENT_CYCLE_READINESS_PROJECTION_MISMATCH"
        ):
            agent_cycle.validate_context(context)


if __name__ == "__main__":
    unittest.main()
