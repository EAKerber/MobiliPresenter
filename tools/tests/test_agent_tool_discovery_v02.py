from __future__ import annotations

import copy
import unittest

from tools import agent_cycle_readiness
from tools.agent_tools import contracts, projection, resolver
from tools.canonical import stable_hash


def brief(*available: str, conditional=()):
    return {
        "capabilityProjection": {
            "required": [],
            "relevantAvailable": sorted(available),
            "conditional": sorted(conditional),
            "requiredUnavailable": [],
        }
    }


class AgentToolDiscoveryV02Tests(unittest.TestCase):
    def test_manager_bootstrap_keeps_role_tools_discoverable_without_admitting_them(self):
        value = projection.build_projection(
            {"role": "manager-gitops", "declaredIntent": "bootstrap-discovery"},
            brief(),
        )

        self.assertEqual(value["schemaVersion"], "AgentToolProjection 0.2")
        self.assertEqual(value["available"], [])
        self.assertEqual(value["plannable"], [])
        self.assertEqual(value["conditional"], [])
        self.assertEqual(
            [item["toolId"] for item in value["discoverable"]],
            ["git.files.mutate", "project.inspect", "routine.inspect"],
        )
        git_tool = value["discoverable"][0]
        self.assertFalse(git_tool["currentIntentAllowed"])
        self.assertEqual(
            git_tool["allowedIntents"], ["governed-mutation", "inspect-and-plan"]
        )
        self.assertEqual(
            git_tool["requiredCapabilities"], ["remote.canonical.execute"]
        )

    def test_ui_discovery_stays_role_bounded(self):
        value = projection.build_projection(
            {"role": "ui-ux", "declaredIntent": "bootstrap-discovery"},
            brief(),
        )

        self.assertEqual(
            [item["toolId"] for item in value["discoverable"]],
            ["git.files.mutate", "project.inspect"],
        )
        self.assertNotIn(
            "routine.inspect", [item["toolId"] for item in value["discoverable"]]
        )

    def test_discoverable_does_not_promote_readiness(self):
        tools = projection.build_projection(
            {"role": "manager-gitops", "declaredIntent": "bootstrap-discovery"},
            brief(),
        )
        readiness = agent_cycle_readiness.build_projection(
            legacy_status="READY",
            blocking_unknowns=[],
            tools=tools,
        )

        self.assertEqual(readiness["toolReadiness"]["status"], "BLOCKED")
        self.assertEqual(
            readiness["toolReadiness"]["reasonCodes"],
            ["NO_TOOL_SURFACE_FOR_INTENT"],
        )
        self.assertEqual(readiness["providerResolution"]["status"], "UNKNOWN")
        self.assertEqual(readiness["mutationAuthorization"]["status"], "NOT_APPLICABLE")

    def test_discovery_does_not_relax_resolver_intent_admission(self):
        begin = {"runId": 123, "sourceSha": "a" * 40, "contextHash": "b" * 64}
        actor = {
            "role": "manager-gitops",
            "workerId": "manager-gitops-r1c",
            "sessionId": "r1c-discovery",
        }
        request = {
            "schemaVersion": contracts.REQUEST_SCHEMA,
            "requestId": contracts.deterministic_request_id(
                begin=begin,
                actor=actor,
                tool_id="git.files.mutate",
                target={"branch": "work/operations/r1c"},
                input_value={
                    "changes": [{"path": "docs/r1c.txt", "content": "x\n"}],
                    "message": "R1C admission regression",
                },
            ),
            "begin": copy.deepcopy(begin),
            "actor": copy.deepcopy(actor),
            "toolId": "git.files.mutate",
            "target": {"branch": "work/operations/r1c"},
            "input": {
                "changes": [{"path": "docs/r1c.txt", "content": "x\n"}],
                "message": "R1C admission regression",
            },
            "semanticAuthority": False,
            "authorizesMutation": False,
        }
        context = {
            "contextHash": begin["contextHash"],
            "semanticContext": {
                "role": "manager-gitops",
                "declaredIntent": "bootstrap-discovery",
            },
        }

        with self.assertRaisesRegex(RuntimeError, "AGENT_TOOL_INTENT_FORBIDDEN"):
            resolver.resolve_request(request, context, execute=False)

    def test_legacy_projection_01_remains_readable(self):
        core = {
            "schemaVersion": "AgentToolProjection 0.1",
            "role": "manager-gitops",
            "declaredIntent": "inspect-and-plan",
            "available": [],
            "plannable": [
                {
                    "toolId": "git.files.mutate",
                    "effectClass": "shared-durable-mutation",
                    "mode": "plan-only",
                    "requiredCapabilities": ["remote.canonical.execute"],
                }
            ],
            "conditional": [],
            "policyHash": "a" * 64,
        }
        legacy = {**core, "projectionHash": stable_hash(core)}

        self.assertEqual(projection.validate_projection(legacy), legacy)

    def test_discoverable_is_hash_bound(self):
        value = projection.build_projection(
            {"role": "manager-gitops", "declaredIntent": "bootstrap-discovery"},
            brief(),
        )
        tampered = copy.deepcopy(value)
        tampered["discoverable"][0]["currentIntentAllowed"] = True

        with self.assertRaisesRegex(
            RuntimeError,
            "AGENT_TOOL_PROJECTION_CURRENT_INTENT_INVALID|AGENT_TOOL_PROJECTION_HASH_MISMATCH",
        ):
            projection.validate_projection(tampered)


if __name__ == "__main__":
    unittest.main()
