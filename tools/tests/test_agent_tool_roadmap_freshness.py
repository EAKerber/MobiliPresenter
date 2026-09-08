from __future__ import annotations

import unittest
from unittest.mock import patch

from tools.agent_tools import contracts, projection, resolver


def brief(*available: str):
    return {
        "capabilityProjection": {
            "required": [],
            "relevantAvailable": sorted(available),
            "conditional": [],
            "requiredUnavailable": [],
        }
    }


def context():
    return {
        "contextHash": "b" * 64,
        "semanticContext": {
            "role": "manager-gitops",
            "declaredIntent": "inspect-and-plan",
        },
        "semanticBrief": brief("roadmap.freshness.inspect"),
    }


def request(*, base_sha: str = "a" * 40, head_sha: str = "c" * 40):
    begin = {
        "runId": 123,
        "sourceSha": "d" * 40,
        "contextHash": "b" * 64,
    }
    actor = {
        "role": "manager-gitops",
        "workerId": "manager-gitops-a",
        "sessionId": "freshness-discovery",
    }
    target = {}
    input_value = {"baseSha": base_sha, "headSha": head_sha}
    return {
        "schemaVersion": contracts.REQUEST_SCHEMA,
        "requestId": contracts.deterministic_request_id(
            begin=begin,
            actor=actor,
            tool_id="roadmap.freshness.inspect",
            target=target,
            input_value=input_value,
        ),
        "begin": begin,
        "actor": actor,
        "toolId": "roadmap.freshness.inspect",
        "target": target,
        "input": input_value,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


class RoadmapFreshnessAgentToolTests(unittest.TestCase):
    def test_capability_projects_as_available_agent_tool(self):
        value = projection.build_projection(
            {
                "role": "manager-gitops",
                "declaredIntent": "inspect-and-plan",
            },
            brief("roadmap.freshness.inspect"),
        )

        self.assertEqual(
            [item["toolId"] for item in value["available"]],
            ["roadmap.freshness.inspect"],
        )

    @patch("tools.agent_tools.adapters.roadmap_freshness_inspect.roadmap_freshness.command_inspect")
    def test_read_only_adapter_delegates_to_canonical_inspection(self, inspect):
        inspect.return_value = {
            "schemaVersion": "RoadmapFreshnessInspection 0.1",
            "status": "PASS",
            "code": "COVERAGE_COMPLETE",
            "changedFields": ["development.nextTransition"],
            "consumers": [],
            "errors": [],
            "readOnly": True,
            "semanticAuthority": False,
            "authorizesMutation": False,
            "inspectionHash": "e" * 64,
        }

        resolved = resolver.resolve_request(request(), context(), execute=True)

        self.assertEqual(resolved["result"]["status"], "PASS")
        self.assertEqual(
            resolved["plan"]["concrete"]["kind"],
            "roadmap-freshness-inspection",
        )
        inspect.assert_called_once()
        args = inspect.call_args.args
        self.assertEqual(args[0], "a" * 40)
        self.assertEqual(args[1], "c" * 40)
        self.assertEqual(
            args[2].name,
            "roadmap-freshness-coverage.json",
        )

    @patch("tools.agent_tools.adapters.roadmap_freshness_inspect.roadmap_freshness.command_inspect")
    def test_invalid_sha_fails_before_canonical_inspection(self, inspect):
        with self.assertRaisesRegex(
            RuntimeError,
            "AGENT_TOOL_ROADMAP_FRESHNESS_SHA_INVALID",
        ):
            resolver.resolve_request(
                request(base_sha="main"),
                context(),
                execute=True,
            )

        inspect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
