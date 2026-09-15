from __future__ import annotations

import copy
import json
import unittest
from types import SimpleNamespace

from tools import agent_authoring, agent_cycle_identity, hosted_cycle_handle


REPOSITORY = "EAKerber/MobiliPresenter"
BRANCH = "work/operations/r4-authoring-test"
ACTOR = {
    "role": "manager-gitops",
    "workerId": "manager-gitops-chat",
    "sessionId": "session-r4-authoring",
}
CONTEXT_HASH = "b" * 64
CYCLE_INSTANCE_ID = "cycle-instance-" + "7" * 24
LOCATOR = {
    "artifactName": "agent-cycle-begin-123",
    "runId": 123,
    "sourceSha": "a" * 40,
    "issueNumber": 145,
    "beginCommentId": 500,
    "contextHash": CONTEXT_HASH,
    "cycleInstanceId": CYCLE_INSTANCE_ID,
}
RESUME_TOKEN = hosted_cycle_handle.HOSTED_TOKEN_PREFIX + json.dumps(
    LOCATOR, sort_keys=True, separators=(",", ":")
)
HANDLE = agent_cycle_identity.build_handle(
    repository=REPOSITORY,
    cycle_id="cycle-" + "6" * 20,
    cycle_instance_id=CYCLE_INSTANCE_ID,
    context_schema_version="AgentCycleContext 0.4",
    context_hash=CONTEXT_HASH,
    actor=ACTOR,
    resume_token=RESUME_TOKEN,
)
CHANGES = [
    {"path": "tools/example.py", "content": "print('ok')\n"},
    {"path": "docs/old.txt", "delete": True},
]


class FakeTransport:
    def __init__(self, comment_id: int = 900):
        self.comment_id = comment_id
        self.calls: list[tuple[str, str, object]] = []

    def request(self, method: str, endpoint: str, *, payload=None, include_headers=False):
        del include_headers
        self.calls.append((method, endpoint, copy.deepcopy(payload)))
        if method.upper() == "POST" and endpoint.endswith("/issues/145/comments"):
            return SimpleNamespace(body=json.dumps({"id": self.comment_id}))
        raise AssertionError((method, endpoint, payload))


class AgentAuthoringR4Tests(unittest.TestCase):
    def test_build_composes_existing_v02_tool_request_only(self) -> None:
        request = agent_authoring.build_authoring_request(
            handle=HANDLE,
            branch=BRANCH,
            changes=CHANGES,
            message="R4 authoring test",
            request_id="r4-authoring-test",
        )

        self.assertEqual("HostedAgentToolRequest 0.2", request["schemaVersion"])
        self.assertEqual("git.files.mutate", request["toolId"])
        self.assertEqual({"branch": BRANCH}, request["target"])
        self.assertEqual(CHANGES, request["input"]["changes"])
        self.assertEqual("R4 authoring test", request["input"]["message"])
        self.assertFalse(request["semanticAuthority"])
        self.assertFalse(request["authorizesMutation"])

    def test_outer_request_does_not_duplicate_git_cas_or_ownership_state(self) -> None:
        request = agent_authoring.build_authoring_request(
            handle=HANDLE,
            branch=BRANCH,
            changes=CHANGES,
            message="R4 authoring test",
            request_id="r4-authoring-no-duplicate-state",
        )

        self.assertNotIn("expected", request)
        self.assertNotIn("branchHead", request)
        self.assertNotIn("leaseId", request)
        self.assertNotIn("bindingHash", request)
        self.assertEqual(
            {
                "schemaVersion", "requestId", "handle", "toolId",
                "target", "input", "semanticAuthority", "authorizesMutation",
            },
            set(request),
        )

    def test_build_deep_copies_authoring_payload(self) -> None:
        changes = copy.deepcopy(CHANGES)
        request = agent_authoring.build_authoring_request(
            handle=HANDLE,
            branch=BRANCH,
            changes=changes,
            message="R4 authoring test",
            request_id="r4-authoring-copy-test",
        )
        changes[0]["content"] = "mutated\n"
        self.assertEqual("print('ok')\n", request["input"]["changes"][0]["content"])

    def test_submit_uses_existing_v02_marker_and_only_posts_bus_comment(self) -> None:
        transport = FakeTransport()
        value = agent_authoring.author_changes(
            handle=HANDLE,
            branch=BRANCH,
            changes=CHANGES,
            message="R4 authoring test",
            request_id="r4-authoring-submit-test",
            submit=True,
            transport=transport,
        )

        self.assertEqual(900, value["requestCommentId"])
        self.assertEqual(1, len(transport.calls))
        method, endpoint, payload = transport.calls[0]
        self.assertEqual("POST", method)
        self.assertTrue(endpoint.endswith("/issues/145/comments"))
        body = payload["body"]
        self.assertTrue(body.startswith("MOBILIPRESENTER_AGENT_TOOL_REQUEST_V0_2\n"))
        posted = json.loads(body.split("\n", 1)[1])
        self.assertEqual(value["request"], posted)
        self.assertEqual("git.files.mutate", posted["toolId"])

    def test_non_submit_path_has_no_transport_side_effect(self) -> None:
        transport = FakeTransport()
        value = agent_authoring.author_changes(
            handle=HANDLE,
            branch=BRANCH,
            changes=CHANGES,
            message="R4 authoring test",
            request_id="r4-authoring-build-only-test",
            submit=False,
            transport=transport,
        )

        self.assertIsNone(value["requestCommentId"])
        self.assertEqual([], transport.calls)

    def test_invalid_handle_is_rejected_by_existing_handle_validator(self) -> None:
        bad = copy.deepcopy(HANDLE)
        bad["repository"] = "other/repo"
        with self.assertRaisesRegex(agent_authoring.AgentAuthoringError, "AGENT_AUTHORING_REQUEST_INVALID"):
            agent_authoring.build_authoring_request(
                handle=bad,
                branch=BRANCH,
                changes=CHANGES,
                message="R4 authoring test",
                request_id="r4-authoring-invalid-handle",
            )


if __name__ == "__main__":
    unittest.main()
