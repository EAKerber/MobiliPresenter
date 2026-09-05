from __future__ import annotations

import copy
import unittest

from tools import (
    agent_cycle,
    agent_cycle_close,
    agent_cycle_readiness,
    project_machine,
    runtime_capabilities,
)
from tools.canonical import stable_hash


HISTORICAL_CONTEXT_FIELDS = {
    "AgentCycleContext 0.1": {"workRef", "readiness", "agentTools"},
    "AgentCycleContext 0.2": {"workRef", "readiness"},
    "AgentCycleContext 0.3": {"workRef"},
}
HISTORICAL_BASELINE_FIELDS = {
    "AgentCycleContext 0.1": {"readinessHash", "agentToolProjectionHash"},
    "AgentCycleContext 0.2": {"readinessHash"},
    "AgentCycleContext 0.3": set(),
}


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


def _rehash_tool_projection(value: dict) -> dict:
    value["projectionHash"] = stable_hash(
        {key: item for key, item in value.items() if key != "projectionHash"}
    )
    return value


def _historical_context_fixture(version: str) -> dict:
    """Freeze historical outer contracts instead of following moving version aliases.

    Nested artifacts intentionally reuse current-valid deterministic inputs; the historical
    outer field sets and baseline additions are literal per the producer versions that
    introduced AgentCycleContext 0.1, 0.2 and 0.3. This keeps the compatibility test from
    silently changing meaning when the current producer advances again.
    """
    if version not in HISTORICAL_CONTEXT_FIELDS:
        raise RuntimeError("TEST_HISTORICAL_CONTEXT_VERSION_UNSUPPORTED")
    value = copy.deepcopy(_context("inspect-and-plan"))
    value["schemaVersion"] = version
    for field in HISTORICAL_CONTEXT_FIELDS[version]:
        value.pop(field)
    for field in HISTORICAL_BASELINE_FIELDS[version]:
        value["baseline"].pop(field)
    return _rehash(value)


class AgentCycleReadinessTests(unittest.TestCase):
    def test_governed_mutation_separates_context_from_execution_readiness(self):
        context = _context("governed-mutation")
        readiness = context["readiness"]

        self.assertEqual(context["schemaVersion"], agent_cycle.SCHEMA_VERSION)
        self.assertEqual(context["schemaVersion"], "AgentCycleContext 0.4")
        self.assertEqual(readiness["schemaVersion"], "AgentCycleReadiness 0.2")
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
        self.assertEqual(
            readiness["nextSafeAction"]["action"],
            "RESOLVE_PROVIDER",
        )
        self.assertEqual(readiness["nextSafeAction"]["toolId"], "git.files.mutate")
        self.assertEqual(
            readiness["nextSafeAction"]["reasonCodes"],
            ["CAPABILITY_NOT_AVAILABLE:remote.canonical.execute"],
        )
        self.assertFalse(readiness["nextSafeAction"]["authorizesMutation"])
        self.assertFalse(readiness["authorizesMutation"])

    def test_multi_tool_intent_requires_explicit_tool_selection(self):
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
        action = readiness["nextSafeAction"]
        self.assertEqual(action["action"], "SELECT_TOOL")
        self.assertGreaterEqual(len(action["candidateToolIds"]), 2)
        self.assertEqual(action["candidateToolIds"], sorted(action["candidateToolIds"]))
        self.assertFalse(action["authorizesMutation"])

    def test_bootstrap_discovery_routes_to_supported_intent_without_archaeology(self):
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
        action = context["readiness"]["nextSafeAction"]
        self.assertEqual(action["action"], "SELECT_INTENT")
        self.assertEqual(
            action["candidateIntents"],
            ["governed-mutation", "inspect-and-plan"],
        )
        self.assertFalse(action["semanticAuthority"])
        self.assertFalse(action["authorizesMutation"])

    def test_available_mutation_routes_to_authorization_resolution_not_execution(self):
        context = _context("governed-mutation")
        tools = copy.deepcopy(context["agentTools"])
        entry = tools["conditional"].pop()
        entry.pop("reasonCode")
        tools["available"] = [entry]
        _rehash_tool_projection(tools)

        readiness = agent_cycle_readiness.build_projection(
            legacy_status="READY",
            blocking_unknowns=[],
            tools=tools,
        )
        action = readiness["nextSafeAction"]
        self.assertEqual(action["action"], "RESOLVE_MUTATION_AUTHORIZATION")
        self.assertEqual(action["mode"], "mutation-execute")
        self.assertFalse(action["authorizesMutation"])
        self.assertNotIn("EXECUTE_MUTATION", agent_cycle_readiness.NEXT_ACTIONS)

    def test_readiness_01_remains_validatable_after_guidance_upgrade(self):
        context = _context("inspect-and-plan")
        legacy = copy.deepcopy(context["readiness"])
        legacy["schemaVersion"] = "AgentCycleReadiness 0.1"
        legacy.pop("nextSafeAction")
        legacy["readinessHash"] = stable_hash(
            {key: item for key, item in legacy.items() if key != "readinessHash"}
        )

        self.assertEqual(
            agent_cycle_readiness.validate_projection(
                legacy,
                legacy_status=context["status"],
                blocking_unknowns=context["blockingUnknowns"],
                tools=context["agentTools"],
            ),
            legacy,
        )

    def test_v03_context_remains_readable_without_work_binding(self):
        legacy = _historical_context_fixture("AgentCycleContext 0.3")

        self.assertEqual(agent_cycle.validate_context(legacy), legacy)
        self.assertNotIn("workRef", legacy)
        self.assertIn("readiness", legacy)
        self.assertIn("agentTools", legacy)

        delta = agent_cycle_close.build_delta(legacy, _context("inspect-and-plan"))
        self.assertEqual(delta["durableChanges"], [])
        self.assertEqual(delta["derivedChanges"], [])

    def test_v02_context_remains_readable_without_dimensional_promotion(self):
        legacy = _historical_context_fixture("AgentCycleContext 0.2")

        self.assertEqual(agent_cycle.validate_context(legacy), legacy)
        self.assertNotIn("workRef", legacy)
        self.assertNotIn("readiness", legacy)
        self.assertIn("agentTools", legacy)

        delta = agent_cycle_close.build_delta(legacy, _context("inspect-and-plan"))
        self.assertEqual(delta["durableChanges"], [])
        self.assertEqual(
            [item["artifact"] for item in delta["derivedChanges"]],
            ["readinessHash"],
        )

    def test_v01_context_remains_readable_without_tool_or_readiness_projection(self):
        legacy = _historical_context_fixture("AgentCycleContext 0.1")

        self.assertEqual(agent_cycle.validate_context(legacy), legacy)
        self.assertNotIn("workRef", legacy)
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
