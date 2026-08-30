from __future__ import annotations

import copy
import json
import unittest

from tools import agent_cycle_identity, hosted_cycle_handle, hosted_cycle_records
from tools.agent_tools import contracts, trace_collect
from tools.canonical import stable_hash

REPOSITORY = "EAKerber/MobiliPresenter"
ACTOR = {
    "role": "manager-gitops",
    "workerId": "manager-gitops-a",
    "sessionId": "session-r4a",
}
CONTEXT_HASH = "b" * 64


def manifest() -> dict:
    source = {
        "workflow": "hosted-agent-cycle",
        "runId": 123,
        "sourceSha": "a" * 40,
        "issueNumber": 145,
        "commentId": 100,
    }
    cycle_instance_id = agent_cycle_identity.hosted_cycle_instance_id(
        source, ACTOR, CONTEXT_HASH
    )
    return {
        "schemaVersion": "HostedAgentCycleBeginManifest 0.3",
        "requestId": "begin-r4a",
        "commandHash": "c" * 64,
        "actor": copy.deepcopy(ACTOR),
        "declaredIntent": "governed-mutation",
        "machineScope": "live",
        "source": source,
        "artifactName": "agent-cycle-begin-123",
        "cycleId": "cycle-" + "d" * 20,
        "cycleInstanceId": cycle_instance_id,
        "contextHash": CONTEXT_HASH,
        "carrierFeatures": ["agent-write-lease-lifecycle-0.1", "execution-trace-0.1"],
        "status": "READY",
        "semanticAuthority": False,
        "authorizesMutation": False,
        "manifestHash": "f" * 64,
    }


def begin_ref(current: dict) -> dict:
    return {
        "runId": current["source"]["runId"],
        "sourceSha": current["source"]["sourceSha"],
        "contextHash": current["contextHash"],
    }


def handle_for(current: dict) -> dict:
    return agent_cycle_identity.build_handle(
        repository=REPOSITORY,
        cycle_id=current["cycleId"],
        cycle_instance_id=current["cycleInstanceId"],
        context_schema_version="AgentCycleContext 0.4",
        context_hash=current["contextHash"],
        actor=current["actor"],
        resume_token=hosted_cycle_handle.build_resume_token(current),
    )


def owner(comment_id: int, marker: str, payload: dict) -> dict:
    return {
        "id": comment_id,
        "author_association": "OWNER",
        "user": {"login": "EAKerber"},
        "body": marker + "\n" + json.dumps(payload),
    }


def bot(comment_id: int, marker: str, payload: dict) -> dict:
    return {
        "id": comment_id,
        "author_association": "NONE",
        "user": {"login": "github-actions[bot]"},
        "body": marker + "\n```json\n" + json.dumps(payload) + "\n```",
    }


def begin_boundary() -> dict:
    return {
        "id": 100,
        "author_association": "OWNER",
        "user": {"login": "EAKerber"},
        "body": "begin",
    }


def legacy_close(current: dict, request_id: str) -> dict:
    return {
        "schemaVersion": "HostedAgentCycleCommand 0.1",
        "requestId": request_id,
        "action": "close",
        "actor": copy.deepcopy(ACTOR),
        "declaredIntent": current["declaredIntent"],
        "machineScope": current["machineScope"],
        "begin": begin_ref(current),
        "evidenceCommentIds": [],
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


def handle_close(current: dict, request_id: str) -> dict:
    return {
        "schemaVersion": "HostedAgentCycleCommand 0.2",
        "requestId": request_id,
        "action": "close",
        "handle": handle_for(current),
        "evidenceCommentIds": [],
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


def tool_request(current: dict, request_id: str = "tool-r4a") -> dict:
    return contracts.validate_request({
        "schemaVersion": contracts.REQUEST_SCHEMA,
        "requestId": request_id,
        "begin": begin_ref(current),
        "actor": copy.deepcopy(ACTOR),
        "toolId": "project.inspect",
        "target": {},
        "input": {},
        "semanticAuthority": False,
        "authorizesMutation": False,
    })


def tool_result(current: dict, request: dict, *, status: str = "PASS") -> dict:
    return {
        "requestHash": stable_hash(request),
        "begin": begin_ref(current),
        "actor": copy.deepcopy(ACTOR),
        "status": status,
        "blockers": [],
    }


class AgentCycleStableSealR4ATests(unittest.TestCase):
    def test_first_bound_close_is_stable_across_retry_for_legacy_and_handle_close(self):
        current = manifest()
        for marker, builder in (
            (hosted_cycle_records.AGENT_CYCLE_REQUEST_MARKER, legacy_close),
            (hosted_cycle_records.AGENT_CYCLE_REQUEST_MARKER_V02, handle_close),
        ):
            with self.subTest(marker=marker):
                comments = [
                    begin_boundary(),
                    owner(200, marker, builder(current, "close-one")),
                    owner(260, marker, builder(current, "close-two")),
                ]
                self.assertEqual(
                    hosted_cycle_records.stable_seal_comment_id(
                        comments, current, observation_comment_id=260
                    ),
                    200,
                )

    def test_late_result_for_pre_seal_request_can_complete_retry_without_expanding_request_set(self):
        current = manifest()
        request = tool_request(current)
        comments = [
            begin_boundary(),
            owner(110, hosted_cycle_records.AGENT_TOOL_REQUEST_MARKER, request),
            owner(
                200,
                hosted_cycle_records.AGENT_CYCLE_REQUEST_MARKER_V02,
                handle_close(current, "close-one"),
            ),
            bot(230, hosted_cycle_records.AGENT_TOOL_RESULT_MARKER, tool_result(current, request)),
            owner(
                260,
                hosted_cycle_records.AGENT_CYCLE_REQUEST_MARKER_V02,
                handle_close(current, "close-two"),
            ),
        ]

        trace = trace_collect.build_trace(comments, current, close_comment_id=260)

        self.assertEqual(trace["traceStatus"], "PASS")
        self.assertEqual(trace["window"]["closeCommentId"], 200)
        self.assertEqual(trace["summary"]["attemptCount"], 1)
        self.assertEqual(trace["attempts"][0]["requestCommentId"], 110)
        self.assertEqual(trace["attempts"][0]["resultCommentId"], 230)

    def test_same_close_preserves_previous_single_window_behavior(self):
        current = manifest()
        request = tool_request(current)
        comments = [
            begin_boundary(),
            owner(110, hosted_cycle_records.AGENT_TOOL_REQUEST_MARKER, request),
            bot(120, hosted_cycle_records.AGENT_TOOL_RESULT_MARKER, tool_result(current, request)),
            owner(
                200,
                hosted_cycle_records.AGENT_CYCLE_REQUEST_MARKER_V02,
                handle_close(current, "close-one"),
            ),
        ]

        trace = trace_collect.build_trace(comments, current, close_comment_id=200)

        self.assertEqual(trace["traceStatus"], "PASS")
        self.assertEqual(trace["window"]["closeCommentId"], 200)
        self.assertEqual(trace["attempts"][0]["resultCommentId"], 120)

    def test_strong_request_after_seal_fails_closed_instead_of_joining_retry(self):
        current = manifest()
        pre = tool_request(current, "pre-seal")
        post = tool_request(current, "post-seal")
        comments = [
            begin_boundary(),
            owner(110, hosted_cycle_records.AGENT_TOOL_REQUEST_MARKER, pre),
            owner(
                200,
                hosted_cycle_records.AGENT_CYCLE_REQUEST_MARKER_V02,
                handle_close(current, "close-one"),
            ),
            owner(220, hosted_cycle_records.AGENT_TOOL_REQUEST_MARKER, post),
            owner(
                260,
                hosted_cycle_records.AGENT_CYCLE_REQUEST_MARKER_V02,
                handle_close(current, "close-two"),
            ),
        ]

        with self.assertRaisesRegex(
            RuntimeError, "HOSTED_CYCLE_RECORD_POST_SEAL_REQUEST"
        ):
            hosted_cycle_records.collect(comments, current, close_comment_id=260)

    def test_duplicate_late_result_still_fails_closed(self):
        current = manifest()
        request = tool_request(current)
        result = tool_result(current, request)
        comments = [
            begin_boundary(),
            owner(110, hosted_cycle_records.AGENT_TOOL_REQUEST_MARKER, request),
            owner(
                200,
                hosted_cycle_records.AGENT_CYCLE_REQUEST_MARKER_V02,
                handle_close(current, "close-one"),
            ),
            bot(230, hosted_cycle_records.AGENT_TOOL_RESULT_MARKER, result),
            bot(240, hosted_cycle_records.AGENT_TOOL_RESULT_MARKER, result),
            owner(
                260,
                hosted_cycle_records.AGENT_CYCLE_REQUEST_MARKER_V02,
                handle_close(current, "close-two"),
            ),
        ]

        with self.assertRaisesRegex(RuntimeError, "AGENT_TRACE_RESULT_DUPLICATE"):
            trace_collect.build_trace(comments, current, close_comment_id=260)

    def test_malformed_or_unrelated_earlier_close_does_not_become_seal(self):
        current = manifest()
        unrelated = legacy_close(current, "other")
        unrelated["actor"] = {**unrelated["actor"], "sessionId": "other-session"}
        comments = [
            begin_boundary(),
            owner(150, hosted_cycle_records.AGENT_CYCLE_REQUEST_MARKER, unrelated),
            owner(
                200,
                hosted_cycle_records.AGENT_CYCLE_REQUEST_MARKER_V02,
                handle_close(current, "close-one"),
            ),
            owner(
                260,
                hosted_cycle_records.AGENT_CYCLE_REQUEST_MARKER_V02,
                handle_close(current, "close-two"),
            ),
        ]

        self.assertEqual(
            hosted_cycle_records.stable_seal_comment_id(
                comments, current, observation_comment_id=260
            ),
            200,
        )

    def test_historical_unmarked_close_keeps_current_cutoff(self):
        current = manifest()
        comments = [
            begin_boundary(),
            {
                "id": 200,
                "author_association": "OWNER",
                "user": {"login": "EAKerber"},
                "body": "historical-close-fixture",
            },
        ]
        self.assertEqual(
            hosted_cycle_records.stable_seal_comment_id(
                comments, current, observation_comment_id=200
            ),
            200,
        )


if __name__ == "__main__":
    unittest.main()
