from __future__ import annotations

import copy
import json
import unittest
from unittest.mock import Mock

from tools import hosted_agent_cycle_trace
from tools.agent_tools import contracts, trace_collect
from tools.canonical import stable_hash


ACTOR = {"role": "manager-gitops", "workerId": "manager-gitops-a", "sessionId": "session-1"}
BEGIN = {"runId": 123, "sourceSha": "a" * 40, "contextHash": "b" * 64}


def manifest():
    return {
        "source": {"runId": 123, "sourceSha": "a" * 40, "issueNumber": 145, "commentId": 100},
        "contextHash": "b" * 64,
        "actor": copy.deepcopy(ACTOR),
    }


def owner_comment(comment_id, marker, payload):
    return {
        "id": comment_id,
        "author_association": "OWNER",
        "user": {"login": "EAKerber"},
        "body": marker + "\n" + json.dumps(payload),
    }


def bot_comment(comment_id, marker, payload):
    return {
        "id": comment_id,
        "author_association": "NONE",
        "user": {"login": "github-actions[bot]"},
        "body": marker + "\n```json\n" + json.dumps(payload) + "\n```",
    }


def tool_request(request_id="agent-tool-one"):
    return {
        "schemaVersion": contracts.REQUEST_SCHEMA,
        "requestId": request_id,
        "begin": copy.deepcopy(BEGIN),
        "actor": copy.deepcopy(ACTOR),
        "toolId": "project.inspect",
        "target": {},
        "input": {},
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


def remote_request():
    return {
        "schemaVersion": "RemoteCanonicalCommand 0.1",
        "executionId": "remote-one",
        "kind": "git-direct",
        "actor": copy.deepcopy(ACTOR),
        "declaredIntent": {"goal": "test"},
        "target": {"operation": "create-file", "branch": "work/operations/example", "path": "docs/example.txt"},
        "expected": {"branchHead": "c" * 40},
        "payload": {"content": "x", "message": "test"},
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


def complete_comments():
    tool = tool_request()
    remote = remote_request()
    return [
        {"id": 100, "author_association": "OWNER", "user": {"login": "EAKerber"}, "body": "begin"},
        owner_comment(101, trace_collect.AGENT_TOOL_REQUEST_MARKER, tool),
        bot_comment(102, trace_collect.AGENT_TOOL_RESULT_MARKER, {
            "requestHash": stable_hash(tool),
            "begin": copy.deepcopy(BEGIN),
            "actor": copy.deepcopy(ACTOR),
            "status": "BLOCKED",
            "blockers": ["EXPECTED_BLOCKER"],
        }),
        owner_comment(103, trace_collect.REMOTE_REQUEST_MARKER, remote),
        bot_comment(104, trace_collect.REMOTE_RESULT_MARKER, {
            "executionId": "remote-one",
            "commandHash": stable_hash(remote),
            "status": "PASS",
            "blockers": [],
        }),
        {"id": 200, "author_association": "OWNER", "user": {"login": "EAKerber"}, "body": "close"},
    ]


def close_command(evidence=None):
    return {
        "schemaVersion": "HostedAgentCycleCommand 0.1",
        "requestId": "hosted-close-test",
        "action": "close",
        "actor": copy.deepcopy(ACTOR),
        "declaredIntent": "inspect-and-plan",
        "machineScope": "live",
        "begin": copy.deepcopy(BEGIN),
        "evidenceCommentIds": [] if evidence is None else evidence,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


class AgentCycleExecutionTraceTests(unittest.TestCase):
    def test_hidden_blocked_attempt_remains_visible_and_pass_receipt_is_discovered(self):
        value = trace_collect.build_trace(complete_comments(), manifest(), close_comment_id=200)
        self.assertEqual(value["traceStatus"], "PASS")
        self.assertEqual(value["summary"], {
            "attemptCount": 2,
            "matchedCount": 2,
            "passCount": 1,
            "blockedCount": 1,
            "unknownCount": 0,
        })
        self.assertEqual([item["status"] for item in value["attempts"]], ["BLOCKED", "PASS"])
        self.assertEqual(trace_collect.remote_evidence_comment_ids(value), [104])

    def test_missing_result_makes_trace_incomplete(self):
        comments = complete_comments()
        comments = [comment for comment in comments if comment["id"] != 102]
        value = trace_collect.build_trace(comments, manifest(), close_comment_id=200)
        self.assertEqual(value["traceStatus"], "INCOMPLETE")
        self.assertEqual(value["summary"]["unknownCount"], 1)
        self.assertFalse(value["attempts"][0]["matched"])

    def test_other_session_does_not_contaminate_trace(self):
        comments = complete_comments()
        other = remote_request()
        other["executionId"] = "remote-other"
        other["actor"]["sessionId"] = "other-session"
        comments.insert(-1, owner_comment(150, trace_collect.REMOTE_REQUEST_MARKER, other))
        value = trace_collect.build_trace(comments, manifest(), close_comment_id=200)
        self.assertEqual(value["summary"]["attemptCount"], 2)

    def test_close_preparation_uses_trace_as_source_of_remote_evidence(self):
        amended, value = hosted_agent_cycle_trace.prepare_close(
            close_command([]),
            {"issueNumber": 145, "commentId": 200},
            manifest(),
            {},
            complete_comments(),
        )
        self.assertEqual(value["summary"]["attemptCount"], 2)
        self.assertEqual(amended["evidenceCommentIds"], [104])

    def test_close_preparation_blocks_incomplete_trace_even_if_caller_omits_attempt(self):
        comments = [comment for comment in complete_comments() if comment["id"] != 102]
        with self.assertRaisesRegex(RuntimeError, "EXECUTION_TRACE_INCOMPLETE"):
            hosted_agent_cycle_trace.prepare_close(
                close_command([104]),
                {"issueNumber": 145, "commentId": 200},
                manifest(),
                {},
                comments,
            )

    def test_transport_stabilization_reobserves_without_replaying_work(self):
        incomplete = [comment for comment in complete_comments() if comment["id"] != 102]
        complete = complete_comments()
        observations = [incomplete, complete]
        fetch = Mock(side_effect=lambda repository, issue: observations.pop(0))
        sleep = Mock()
        amended, value = hosted_agent_cycle_trace.prepare_close_stabilized(
            close_command([]),
            {"issueNumber": 145, "commentId": 200},
            manifest(),
            {},
            repository="EAKerber/MobiliPresenter",
            fetch_comments=fetch,
            sleep=sleep,
            attempts=2,
            delay_seconds=0,
        )
        self.assertEqual(value["traceStatus"], "PASS")
        self.assertEqual(amended["evidenceCommentIds"], [104])
        self.assertEqual(fetch.call_count, 2)
        sleep.assert_called_once_with(0.0)
        self.assertEqual(hosted_agent_cycle_trace.TRACE_COMPLETENESS_SCOPE, "same-cycle-attributable-events")

    def test_agent_tool_orphan_result_is_not_silently_ignored(self):
        comments = complete_comments()
        orphan = tool_request("agent-tool-orphan")
        comments.insert(-1, bot_comment(160, trace_collect.AGENT_TOOL_RESULT_MARKER, {
            "requestHash": stable_hash(orphan),
            "begin": copy.deepcopy(BEGIN),
            "actor": copy.deepcopy(ACTOR),
            "status": "BLOCKED",
            "blockers": ["ORPHAN"],
        }))
        with self.assertRaisesRegex(RuntimeError, "ORPHAN_AGENT_TOOL_RESULT"):
            trace_collect.build_trace(comments, manifest(), close_comment_id=200)


if __name__ == "__main__":
    unittest.main()
