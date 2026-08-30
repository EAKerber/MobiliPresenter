from __future__ import annotations

import copy
import json
import unittest
from unittest.mock import patch

from tools import agent_write_lifecycle as lifecycle
from tools import agent_write_lifecycle_host as host
from tools import hosted_cycle_records
from tools.agent_tools import contracts


BRANCH = "work/operations/r4c-predecessor-test"
OTHER_BRANCH = "work/operations/r4c-other"
BEGIN = {
    "runId": 123,
    "sourceSha": "a" * 40,
    "contextHash": "b" * 64,
}
ACTOR = {
    "role": "manager-gitops",
    "workerId": "manager-gitops-a",
    "sessionId": "session-r4c",
}


def lifecycle_request(*, action: str = "release") -> dict:
    return {
        "schemaVersion": lifecycle.REQUEST_SCHEMA,
        "requestId": f"request-{action}-r4c",
        "action": action,
        "begin": copy.deepcopy(BEGIN),
        "actor": copy.deepcopy(ACTOR),
        "branch": BRANCH,
        "expectedAuthorityHead": "c" * 40,
        "expectedBranchHead": "d" * 40,
        "expectedBindingHash": None if action == "acquire" else "e" * 64,
        "ttlSeconds": 3600 if action == "acquire" else None,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


def bundle(*, action: str = "release") -> dict:
    request = lifecycle_request(action=action)
    return {
        "request": request,
        "dispatch": {
            "action": action,
            "begin": copy.deepcopy(BEGIN),
            "actor": copy.deepcopy(ACTOR),
            "branch": BRANCH,
            "authorityHead": "c" * 40,
            "source": {
                "issueNumber": 145,
                "requestCommentId": 100,
                "hostedRunId": 456,
                "semanticHostSha": "a" * 40,
            },
        },
        "context": {
            "semanticContext": {
                "declaredIntent": "governed-mutation",
            }
        },
        "manifest": {
            "cycleInstanceId": "cycle-instance-" + "7" * 24,
        },
    }


def tool_request(
    *,
    branch: str = BRANCH,
    tool_id: str = "git.files.mutate",
    request_id: str = "agent-tool-r4c",
) -> dict:
    value = {
        "schemaVersion": contracts.REQUEST_SCHEMA,
        "requestId": request_id,
        "begin": copy.deepcopy(BEGIN),
        "actor": copy.deepcopy(ACTOR),
        "toolId": tool_id,
        "target": {"branch": branch, "path": "docs/r4c.txt"},
        "input": {"content": "r4c"},
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    contracts.validate_request(value)
    return value


def view_for(*requests: tuple[int, dict]) -> dict:
    return {
        "records": [
            {
                "kind": "agent-tool-request",
                "binding": hosted_cycle_records.STRONG,
                "commentId": comment_id,
                "normalized": copy.deepcopy(request),
            }
            for comment_id, request in requests
        ]
    }


def bot_result(request: dict, *, status: str, comment_id: int) -> dict:
    payload = {
        "requestHash": contracts.request_hash(request),
        "begin": copy.deepcopy(request["begin"]),
        "actor": copy.deepcopy(request["actor"]),
        "toolId": request["toolId"],
        "status": status,
    }
    return {
        "id": comment_id,
        "user": {"login": "github-actions[bot]"},
        "body": (
            hosted_cycle_records.AGENT_TOOL_RESULT_MARKER
            + "\n```json\n"
            + json.dumps(payload)
            + "\n```"
        ),
    }


class DerivedMutationPredecessorFenceR4CTests(unittest.TestCase):
    @patch("tools.agent_write_lifecycle_host.hosted_cycle_records.collect")
    def test_release_waits_for_earlier_same_branch_mutation_without_terminal(
        self, collect
    ):
        request = tool_request()
        collect.return_value = view_for((90, request))

        value = host._mutation_predecessor_fence([], bundle())

        self.assertEqual(host.PREDECESSOR_WAITING, value["state"])
        self.assertEqual([90], value["predecessorRequestCommentIds"])
        self.assertEqual([90], value["waitingPredecessorRequestCommentIds"])
        self.assertIs(value["semanticAuthority"], False)
        self.assertIs(value["authorizesMutation"], False)
        collect.assert_called_once()

    @patch("tools.agent_write_lifecycle_host.hosted_cycle_records.collect")
    def test_late_correlated_pass_after_release_request_clears_fence(self, collect):
        request = tool_request()
        collect.return_value = view_for((90, request))
        comments = [bot_result(request, status="PASS", comment_id=120)]

        value = host._mutation_predecessor_fence(comments, bundle())

        self.assertEqual("CLEAR", value["state"])

    @patch("tools.agent_write_lifecycle_host.hosted_cycle_records.collect")
    def test_blocked_predecessor_is_terminal_and_safe_to_release(self, collect):
        request = tool_request()
        collect.return_value = view_for((90, request))
        comments = [bot_result(request, status="BLOCKED", comment_id=120)]

        value = host._mutation_predecessor_fence(comments, bundle())

        self.assertEqual("CLEAR", value["state"])

    @patch("tools.agent_write_lifecycle_host.hosted_cycle_records.collect")
    def test_unknown_predecessor_prevents_release_with_unknown_terminal(self, collect):
        request = tool_request()
        collect.return_value = view_for((90, request))
        comments = [bot_result(request, status="UNKNOWN", comment_id=120)]

        value = host._mutation_predecessor_fence(comments, bundle())

        self.assertEqual(host.PREDECESSOR_UNKNOWN, value["state"])
        self.assertEqual("UNKNOWN", value["terminal"]["status"])
        self.assertIn(
            "AGENT_WRITE_LIFECYCLE_MUTATION_PREDECESSOR_UNKNOWN",
            value["terminal"]["blockers"],
        )
        self.assertEqual([90], value["unknownPredecessorRequestCommentIds"])

    @patch("tools.agent_write_lifecycle_host.hosted_cycle_records.collect")
    def test_other_branch_mutation_does_not_serialize_disjoint_work(self, collect):
        request = tool_request(branch=OTHER_BRANCH)
        collect.return_value = view_for((90, request))

        value = host._mutation_predecessor_fence([], bundle())

        self.assertEqual("CLEAR", value["state"])

    @patch("tools.agent_write_lifecycle_host.hosted_cycle_records.collect")
    def test_read_only_tool_does_not_fence_release(self, collect):
        request = tool_request(
            tool_id="project.inspect",
            request_id="agent-tool-r4c-read",
        )
        collect.return_value = view_for((90, request))

        value = host._mutation_predecessor_fence([], bundle())

        self.assertEqual("CLEAR", value["state"])

    @patch("tools.agent_write_lifecycle_host.hosted_cycle_records.collect")
    def test_non_release_lifecycle_actions_do_not_enter_predecessor_scan(self, collect):
        value = host._mutation_predecessor_fence(
            [],
            bundle(action="acquire"),
        )

        self.assertEqual("CLEAR", value["state"])
        collect.assert_not_called()

    @patch("tools.agent_write_lifecycle_host.hosted_cycle_records.collect")
    def test_duplicate_correlated_results_fail_closed(self, collect):
        request = tool_request()
        collect.return_value = view_for((90, request))
        comments = [
            bot_result(request, status="PASS", comment_id=120),
            bot_result(request, status="PASS", comment_id=121),
        ]

        with self.assertRaisesRegex(
            host.AgentWriteLifecycleHostError,
            "AGENT_WRITE_LIFECYCLE_PREDECESSOR_RESULT_DUPLICATE",
        ):
            host._mutation_predecessor_fence(comments, bundle())

    @patch("tools.agent_write_lifecycle_host.lifecycle.build_attempt")
    @patch("tools.agent_write_lifecycle_host._mutation_predecessor_fence")
    @patch("tools.agent_write_lifecycle_host._comments")
    @patch("tools.agent_write_lifecycle_host._validate_bundle")
    def test_inspect_protocol_returns_waiting_before_attempt_marker(
        self,
        validate_bundle,
        comments,
        predecessor,
        build_attempt,
    ):
        comments.return_value = []
        predecessor.return_value = {
            "state": host.PREDECESSOR_WAITING,
            "predecessorRequestCommentIds": [90],
            "waitingPredecessorRequestCommentIds": [90],
            "semanticAuthority": False,
            "authorizesMutation": False,
        }

        value = host.inspect_protocol(
            bundle(),
            host_sha="a" * 40,
            hosted_run_id=456,
            run_id=900,
            transport=object(),
        )

        self.assertEqual(host.PREDECESSOR_WAITING, value["state"])
        build_attempt.assert_not_called()


if __name__ == "__main__":
    unittest.main()
