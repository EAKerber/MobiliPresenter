from __future__ import annotations

import unittest
from unittest import mock

from tools import agent_authoring, agent_delivery, agent_ownership, agent_reentry_guidance, agent_write_lifecycle, agent_write_lifecycle_host, continuation_remote, delivery_merge, git_observation
from tools import remote_canonical_execution as bridge
from tools.agent_commands import agent_owned_git
from tools.coordination_remote import ApiResponse


class ProviderBoundaryRetirementTests(unittest.TestCase):
    def test_git_observation_uses_injected_provider(self) -> None:
        class FakeProvider:
            def __init__(self) -> None:
                self.calls: list[tuple[str, str]] = []

            def request(
                self,
                method: str,
                endpoint: str,
                *,
                payload=None,
                include_headers: bool = False,
            ) -> ApiResponse:
                self.calls.append((method, endpoint))
                return ApiResponse(
                    status=200,
                    headers={},
                    body='{"object":{"sha":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}}',
                )

        provider = FakeProvider()
        observed = git_observation.observe_branch(
            "work/operations/provider-boundary-test",
            transport=provider,
        )
        self.assertEqual(observed["branchHead"], "a" * 40)
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(provider.calls[0][0], "GET")

    def test_git_observation_requires_explicit_provider(self) -> None:
        with self.assertRaisesRegex(
            git_observation.GitObservationError,
            "BLOCKED_EXECUTION_SURFACE",
        ):
            git_observation.observe_branch("work/operations/provider-boundary-test")

    def test_reentry_guidance_requires_explicit_provider(self) -> None:
        with self.assertRaisesRegex(
            agent_reentry_guidance.AgentReentryGuidanceError,
            "BLOCKED_EXECUTION_SURFACE",
        ):
            agent_reentry_guidance.observe_live("r6-provider-boundary-retirement")

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


    def test_continuation_authority_requires_explicit_provider(self) -> None:
        with self.assertRaisesRegex(
            continuation_remote.ContinuationRemoteError,
            "BLOCKED_EXECUTION_SURFACE",
        ):
            continuation_remote.GitHubContinuationAuthority()


    @mock.patch("tools.agent_write_lifecycle.validate_begin_binding")
    def test_agent_write_lifecycle_requires_explicit_provider(
        self,
        validate_begin_binding: mock.Mock,
    ) -> None:
        with self.assertRaisesRegex(
            agent_write_lifecycle.AgentWriteLifecycleError,
            "BLOCKED_EXECUTION_SURFACE",
        ):
            agent_write_lifecycle.prepare_dispatch(
                {},
                {},
                {},
                issue_number=145,
                request_comment_id=1,
                hosted_run_id=1,
            )

    def test_agent_write_lifecycle_host_inspect_requires_explicit_provider(self) -> None:
        with self.assertRaisesRegex(
            agent_write_lifecycle_host.AgentWriteLifecycleHostError,
            "BLOCKED_EXECUTION_SURFACE",
        ):
            agent_write_lifecycle_host.inspect_protocol(
                {},
                host_sha="a" * 40,
                hosted_run_id=1,
                run_id=1,
            )

    def test_agent_write_lifecycle_host_execute_requires_explicit_provider(self) -> None:
        with self.assertRaisesRegex(
            agent_write_lifecycle_host.AgentWriteLifecycleHostError,
            "BLOCKED_EXECUTION_SURFACE",
        ):
            agent_write_lifecycle_host.execute_dispatch(
                {},
                host_sha="a" * 40,
                hosted_run_id=1,
                run_id=1,
                attempt_comment_id=1,
            )


    @mock.patch("tools.remote_canonical_execution.validate_command")
    def test_remote_canonical_execution_requires_explicit_provider(
        self,
        validate_command: mock.Mock,
    ) -> None:
        validate_command.return_value = {"kind": "domain"}
        with self.assertRaisesRegex(
            bridge.RemoteCanonicalExecutionError,
            "BLOCKED_EXECUTION_SURFACE",
        ):
            bridge.execute_command({}, source={})


    @mock.patch("tools.delivery_merge.validate_request")
    def test_delivery_merge_prepare_requires_explicit_provider(
        self,
        validate_request: mock.Mock,
    ) -> None:
        request = {}
        validate_request.return_value = request
        with self.assertRaisesRegex(
            delivery_merge.DeliveryMergeError,
            "BLOCKED_EXECUTION_SURFACE",
        ):
            delivery_merge.prepare(request)

    @mock.patch("tools.delivery_merge.validate_dispatch")
    def test_delivery_merge_execute_requires_explicit_provider(
        self,
        validate_dispatch: mock.Mock,
    ) -> None:
        dispatch = {}
        validate_dispatch.return_value = dispatch
        with self.assertRaisesRegex(
            delivery_merge.DeliveryMergeError,
            "BLOCKED_EXECUTION_SURFACE",
        ):
            delivery_merge.execute(dispatch)


if __name__ == "__main__":
    unittest.main()
