from __future__ import annotations

import copy
import json
import unittest
from unittest.mock import Mock, patch

from tools import hosted_agent_cycle_trace
from tools.agent_tools import trace_collect


ACTOR = {
    "role": "manager-gitops",
    "workerId": "manager-gitops-a",
    "sessionId": "session-lifecycle-close",
}
BEGIN = {
    "runId": 123,
    "sourceSha": "a" * 40,
    "contextHash": "b" * 64,
}


def manifest():
    return {
        "source": {
            "runId": BEGIN["runId"],
            "sourceSha": BEGIN["sourceSha"],
            "issueNumber": 145,
            "commentId": 100,
        },
        "contextHash": BEGIN["contextHash"],
        "actor": copy.deepcopy(ACTOR),
    }


def bot_comment(comment_id, marker, payload):
    return {
        "id": comment_id,
        "author_association": "NONE",
        "user": {"login": "github-actions[bot]"},
        "body": marker + "\n```json\n" + json.dumps(payload) + "\n```",
    }


def boundary_comment(comment_id):
    return {
        "id": comment_id,
        "author_association": "OWNER",
        "user": {"login": "EAKerber"},
        "body": "boundary",
    }


def lifecycle_receipt(cycle_id, action="release", receipt_hash=None):
    receipt_hash = receipt_hash or ("c" * 64)
    return {
        "receiptHash": receipt_hash,
        "command": {
            "actor": copy.deepcopy(ACTOR),
            "declaredIntent": {
                "intent": "agent-write-lease-lifecycle",
                "cycleInstanceId": cycle_id,
                "action": action,
            },
            "target": {
                "domain": "coordination",
                "action": action,
                "subject": {"kind": "coordination", "id": "leases"},
            },
        },
    }


def lifecycle_result(cycle_id, action="release", receipt=None):
    receipt = lifecycle_receipt(cycle_id, action) if receipt is None else receipt
    return {
        "schemaVersion": "AgentWriteLeaseResult 0.1",
        "action": action,
        "begin": copy.deepcopy(BEGIN),
        "cycleInstanceId": cycle_id,
        "actor": copy.deepcopy(ACTOR),
        "binding": {
            "state": "RELEASED" if action == "release" else "ACTIVE",
        },
        "remoteReceipt": copy.deepcopy(receipt),
        "remoteReceiptHash": receipt["receiptHash"],
    }


def lifecycle_comments(*, include_receipt=True, result_cycle=None, published_receipt=None):
    current = manifest()
    cycle_id = trace_collect.cycle_instance_id(current)
    result_cycle = cycle_id if result_cycle is None else result_cycle
    receipt = lifecycle_receipt(result_cycle)
    comments = [
        boundary_comment(100),
        bot_comment(
            110,
            "MOBILIPRESENTER_AGENT_WRITE_LEASE_RESULT_V0_1",
            lifecycle_result(result_cycle, receipt=receipt),
        ),
    ]
    if include_receipt:
        comments.append(
            bot_comment(
                111,
                trace_collect.REMOTE_RESULT_MARKER,
                receipt if published_receipt is None else published_receipt,
            )
        )
    comments.append(boundary_comment(200))
    return comments


class AgentWriteLifecycleCloseEvidenceTests(unittest.TestCase):
    @patch("tools.remote_canonical_execution.validate_receipt", side_effect=lambda value: value)
    @patch("tools.agent_write_lifecycle.validate_result", side_effect=lambda value: value)
    def test_discovers_exact_same_cycle_lifecycle_receipt(self, validate_result, validate_receipt):
        ids = hosted_agent_cycle_trace._agent_write_lifecycle_evidence_comment_ids(
            lifecycle_comments(), manifest(), close_comment_id=200
        )
        self.assertEqual(ids, [111])
        validate_result.assert_called_once()
        validate_receipt.assert_called_once()

    @patch("tools.remote_canonical_execution.validate_receipt", side_effect=lambda value: value)
    @patch("tools.agent_write_lifecycle.validate_result", side_effect=lambda value: value)
    def test_discovers_acquire_and_release_receipts_for_same_cycle(
        self, validate_result, validate_receipt
    ):
        current = manifest()
        cycle_id = trace_collect.cycle_instance_id(current)
        acquire_receipt = lifecycle_receipt(cycle_id, "acquire", "a" * 64)
        release_receipt = lifecycle_receipt(cycle_id, "release", "b" * 64)
        comments = [
            boundary_comment(100),
            bot_comment(
                110,
                "MOBILIPRESENTER_AGENT_WRITE_LEASE_RESULT_V0_1",
                lifecycle_result(cycle_id, "acquire", acquire_receipt),
            ),
            bot_comment(111, trace_collect.REMOTE_RESULT_MARKER, acquire_receipt),
            bot_comment(
                120,
                "MOBILIPRESENTER_AGENT_WRITE_LEASE_RESULT_V0_1",
                lifecycle_result(cycle_id, "release", release_receipt),
            ),
            bot_comment(121, trace_collect.REMOTE_RESULT_MARKER, release_receipt),
            boundary_comment(200),
        ]
        ids = hosted_agent_cycle_trace._agent_write_lifecycle_evidence_comment_ids(
            comments, current, close_comment_id=200
        )
        self.assertEqual(ids, [111, 121])
        self.assertEqual(validate_result.call_count, 2)
        self.assertEqual(validate_receipt.call_count, 2)

    @patch("tools.remote_canonical_execution.validate_receipt", side_effect=lambda value: value)
    @patch("tools.agent_write_lifecycle.validate_result", side_effect=lambda value: value)
    def test_other_cycle_lifecycle_result_is_ignored(self, validate_result, validate_receipt):
        ids = hosted_agent_cycle_trace._agent_write_lifecycle_evidence_comment_ids(
            lifecycle_comments(
                include_receipt=False,
                result_cycle="cycle-instance-" + "0" * 24,
            ),
            manifest(),
            close_comment_id=200,
        )
        self.assertEqual(ids, [])
        validate_result.assert_not_called()
        validate_receipt.assert_not_called()

    @patch("tools.remote_canonical_execution.validate_receipt", side_effect=lambda value: value)
    @patch("tools.agent_write_lifecycle.validate_result", side_effect=lambda value: value)
    def test_missing_published_lifecycle_receipt_is_retryable_observation_gap(
        self, validate_result, validate_receipt
    ):
        with self.assertRaisesRegex(RuntimeError, "AGENT_TRACE_LIFECYCLE_RECEIPT_MISSING"):
            hosted_agent_cycle_trace._agent_write_lifecycle_evidence_comment_ids(
                lifecycle_comments(include_receipt=False),
                manifest(),
                close_comment_id=200,
            )
        validate_result.assert_called_once()
        validate_receipt.assert_not_called()

    @patch("tools.remote_canonical_execution.validate_receipt", side_effect=lambda value: value)
    @patch("tools.agent_write_lifecycle.validate_result", side_effect=lambda value: value)
    def test_lifecycle_receipt_mismatch_fails_closed(self, validate_result, validate_receipt):
        cycle_id = trace_collect.cycle_instance_id(manifest())
        expected = lifecycle_receipt(cycle_id)
        mismatched = copy.deepcopy(expected)
        mismatched["command"]["target"]["subject"]["id"] = "other"
        with self.assertRaisesRegex(RuntimeError, "AGENT_TRACE_LIFECYCLE_RECEIPT_MISMATCH"):
            hosted_agent_cycle_trace._agent_write_lifecycle_evidence_comment_ids(
                lifecycle_comments(published_receipt=mismatched),
                manifest(),
                close_comment_id=200,
            )
        validate_result.assert_called_once()
        validate_receipt.assert_called_once()

    @patch(
        "tools.hosted_agent_cycle_trace._agent_write_lifecycle_evidence_comment_ids",
        return_value=[106],
    )
    @patch(
        "tools.hosted_agent_cycle_trace.trace_collect.agent_tool_mutation_evidence_comment_ids",
        return_value=[105],
    )
    @patch(
        "tools.hosted_agent_cycle_trace.trace_collect.remote_evidence_comment_ids",
        return_value=[104],
    )
    def test_close_amendment_unions_remote_mutation_and_lifecycle_receipts(
        self, remote_ids, mutation_ids, lifecycle_ids
    ):
        command = {"evidenceCommentIds": [103]}
        amended = hosted_agent_cycle_trace._amend_command(
            command,
            {},
            [],
            manifest(),
            close_comment_id=200,
        )
        self.assertEqual(amended["evidenceCommentIds"], [103, 104, 105, 106])
        self.assertEqual(command["evidenceCommentIds"], [103])
        remote_ids.assert_called_once_with({})
        mutation_ids.assert_called_once()
        lifecycle_ids.assert_called_once()

    @patch("tools.hosted_agent_cycle_trace._amend_command")
    @patch("tools.hosted_agent_cycle_trace._bound_trace")
    def test_stabilization_reobserves_delayed_lifecycle_receipt_without_replay(
        self, bound_trace, amend
    ):
        trace_value = {"traceStatus": "PASS"}
        bound_trace.return_value = trace_value
        amend.side_effect = [
            hosted_agent_cycle_trace.HostedAgentCycleTraceError(
                hosted_agent_cycle_trace.LIFECYCLE_RECEIPT_MISSING
            ),
            {"evidenceCommentIds": [111]},
        ]
        fetch = Mock(return_value=[])
        sleep = Mock()
        amended, observed = hosted_agent_cycle_trace.prepare_close_stabilized(
            {"evidenceCommentIds": []},
            {"issueNumber": 145, "commentId": 200},
            manifest(),
            {},
            repository="EAKerber/MobiliPresenter",
            fetch_comments=fetch,
            sleep=sleep,
            attempts=2,
            delay_seconds=0,
        )
        self.assertEqual(amended["evidenceCommentIds"], [111])
        self.assertIs(observed, trace_value)
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(amend.call_count, 2)
        sleep.assert_called_once_with(0.0)

    @patch("tools.hosted_agent_cycle_trace._amend_command")
    @patch("tools.hosted_agent_cycle_trace._bound_trace")
    def test_lifecycle_receipt_mismatch_does_not_retry(self, bound_trace, amend):
        bound_trace.return_value = {"traceStatus": "PASS"}
        amend.side_effect = hosted_agent_cycle_trace.HostedAgentCycleTraceError(
            "AGENT_TRACE_LIFECYCLE_RECEIPT_MISMATCH"
        )
        fetch = Mock(return_value=[])
        sleep = Mock()
        with self.assertRaisesRegex(RuntimeError, "AGENT_TRACE_LIFECYCLE_RECEIPT_MISMATCH"):
            hosted_agent_cycle_trace.prepare_close_stabilized(
                {"evidenceCommentIds": []},
                {"issueNumber": 145, "commentId": 200},
                manifest(),
                {},
                repository="EAKerber/MobiliPresenter",
                fetch_comments=fetch,
                sleep=sleep,
                attempts=3,
                delay_seconds=0,
            )
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(amend.call_count, 1)
        sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
