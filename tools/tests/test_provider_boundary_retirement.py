from __future__ import annotations

import unittest
from unittest import mock

from tools import agent_authoring, agent_delivery, agent_ownership, git_observation
from tools import remote_canonical_execution as bridge
from tools.agent_commands import agent_owned_git


class ProviderBoundaryRetirementTests(unittest.TestCase):
    def test_git_observation_requires_explicit_provider(self) -> None:
        with self.assertRaisesRegex(
            git_observation.GitObservationError,
            "BLOCKED_EXECUTION_SURFACE",
        ):
            git_observation.observe_branch("work/operations/provider-boundary-test")

    def test_agent_owned_git_requires_explicit_provider_before_execution(self) -> None:
        command = {
            "schemaVersion": bridge.COMMAND_SCHEMA,
            "executionId": "provider-boundary-test",
            "kind": "git-direct",
            "actor": {
                "role": "manager-gitops",
                "workerId": "manager-gitops-chat",
                "sessionId": "provider-boundary-test",
            },
            "declaredIntent": {"goal": "prove provider injection"},
            "target": {
                "operation": "create-file",
                "branch": "work/operations/provider-boundary-test",
                "path": "docs/provider-boundary-test.txt",
            },
            "expected": {"branchHead": "a" * 40},
            "payload": {"content": "test\n", "message": "provider boundary test"},
            "semanticAuthority": False,
            "authorizesMutation": False,
        }
        with self.assertRaisesRegex(
            bridge.RemoteCanonicalExecutionError,
            "BLOCKED_EXECUTION_SURFACE",
        ):
            agent_owned_git.execute_agent_owned_git(command, source={})

    @mock.patch("tools.agent_authoring.hosted_cycle_handle.decode_handle")
    @mock.patch("tools.agent_authoring.hosted_handle_requests.validate_tool")
    def test_authoring_submit_requires_explicit_provider(
        self,
        validate_tool: mock.Mock,
        decode_handle: mock.Mock,
    ) -> None:
        request = {"handle": {}}
        validate_tool.return_value = request
        decode_handle.return_value = ({}, {"issueNumber": 145})
        with self.assertRaisesRegex(
            agent_authoring.AgentAuthoringError,
            "BLOCKED_EXECUTION_SURFACE",
        ):
            agent_authoring.submit_authoring_request(request)

    @mock.patch("tools.agent_ownership.hosted_cycle_handle.decode_handle")
    def test_ownership_requires_explicit_provider_before_observation(
        self,
        decode_handle: mock.Mock,
    ) -> None:
        decode_handle.return_value = (
            {},
            {
                "runId": 123,
                "sourceSha": "a" * 40,
                "contextHash": "b" * 64,
                "issueNumber": 145,
            },
        )
        with self.assertRaisesRegex(
            agent_ownership.AgentOwnershipError,
            "BLOCKED_EXECUTION_SURFACE",
        ):
            agent_ownership.ensure_ownership(
                handle={},
                branch="work/operations/provider-boundary-test",
                request_id="provider-boundary-test",
            )

    @mock.patch("tools.agent_delivery._decode_handle")
    def test_delivery_build_requires_explicit_provider_before_observation(
        self,
        decode_handle: mock.Mock,
    ) -> None:
        decode_handle.return_value = ({"actor": {}}, {})
        with self.assertRaisesRegex(
            agent_delivery.AgentDeliveryError,
            "BLOCKED_EXECUTION_SURFACE",
        ):
            agent_delivery.build_delivery_request(
                handle={},
                work_id="provider-boundary-test",
                request_id="provider-boundary-test",
            )

    @mock.patch("tools.agent_delivery._decode_handle")
    @mock.patch("tools.agent_delivery.delivery_merge.validate_request")
    def test_delivery_submit_requires_explicit_provider_before_post(
        self,
        validate_request: mock.Mock,
        decode_handle: mock.Mock,
    ) -> None:
        request = {}
        validate_request.return_value = request
        decode_handle.return_value = ({}, {"issueNumber": 145})
        with self.assertRaisesRegex(
            agent_delivery.AgentDeliveryError,
            "BLOCKED_EXECUTION_SURFACE",
        ):
            agent_delivery.submit_delivery_request(request, handle={})


if __name__ == "__main__":
    unittest.main()
