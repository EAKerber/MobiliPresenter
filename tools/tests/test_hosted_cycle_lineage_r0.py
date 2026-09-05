from __future__ import annotations

import copy
import json
import unittest

from tools import agent_cycle_identity
from tools import hosted_agent_cycle as hosted
from tools import hosted_cycle_artifact, hosted_cycle_handle, hosted_cycle_lineage
from tools.canonical import stable_hash

ISSUE_NUMBER = 145
WORK_ID = "m13-r0-lineage-test"
OTHER_WORK_ID = "m13-r0-other-work"
ACTOR = {
    "role": "manager-gitops",
    "workerId": "manager-gitops-a",
    "sessionId": "m13-r0-test",
}


def _command(work_id: str, request_id: str) -> dict:
    return {
        "schemaVersion": hosted.COMMAND_SCHEMA_V03,
        "requestId": request_id,
        "action": "begin",
        "actor": copy.deepcopy(ACTOR),
        "declaredIntent": "inspect-and-plan",
        "machineScope": "live",
        "workRef": {"workId": work_id},
        "evidenceCommentIds": [],
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


def _request_comment(command: dict, comment_id: int) -> dict:
    return {
        "id": comment_id,
        "author_association": "OWNER",
        "user": {"login": "EAKerber"},
        "body": hosted.REQUEST_MARKER_V03 + "\n" + json.dumps(command),
    }


def _begin_result(command: dict, *, begin_comment_id: int, run_id: int, source_hex: str) -> dict:
    source_sha = source_hex * 40
    context_hash = stable_hash({"runId": run_id, "beginCommentId": begin_comment_id})
    source = {
        "workflow": "hosted-agent-cycle",
        "sourceSha": source_sha,
        "runId": run_id,
        "issueNumber": ISSUE_NUMBER,
        "commentId": begin_comment_id,
    }
    cycle_instance_id = agent_cycle_identity.hosted_cycle_instance_id(source, ACTOR, context_hash)
    artifact_name = f"agent-cycle-begin-{run_id}"
    resume_token = hosted_cycle_handle.build_resume_token(
        {
            "source": copy.deepcopy(source),
            "artifactName": artifact_name,
            "contextHash": context_hash,
            "cycleInstanceId": cycle_instance_id,
        }
    )
    cycle_id = "cycle-" + stable_hash({"cycle": run_id})[:20]
    handle = agent_cycle_identity.build_handle(
        repository=hosted.REPOSITORY,
        cycle_id=cycle_id,
        cycle_instance_id=cycle_instance_id,
        context_schema_version="AgentCycleContext 0.4",
        context_hash=context_hash,
        actor=ACTOR,
        resume_token=resume_token,
    )
    projection = hosted_cycle_artifact.classify_artifact_response(
        {
            "total_count": 1,
            "artifacts": [{
                "id": run_id + 10000,
                "name": artifact_name,
                "expired": False,
                "expires_at": "2026-09-19T00:00:00Z",
                "workflow_run": {"id": run_id, "head_sha": source_sha},
            }],
        },
        run_id=run_id,
        artifact_name=artifact_name,
        source_sha=source_sha,
    )
    core = {
        "schemaVersion": hosted_cycle_artifact.BEGIN_RESULT_SCHEMA,
        "requestId": command["requestId"],
        "commandHash": hosted.transport_command_hash(command),
        "runId": run_id,
        "sourceSha": source_sha,
        "artifactName": artifact_name,
        "cycleId": cycle_id,
        "cycleInstanceId": cycle_instance_id,
        "contextHash": context_hash,
        "carrierFeatures": copy.deepcopy(hosted.CURRENT_FEATURES),
        "manifestHash": stable_hash({"manifest": run_id}),
        "handle": handle,
        "status": "READY",
        "semanticAuthority": False,
        "authorizesMutation": False,
        "resumability": projection,
    }
    return {**core, "resultHash": stable_hash(core)}


def _result_comment(result: dict, comment_id: int) -> dict:
    return {
        "id": comment_id,
        "author_association": "CONTRIBUTOR",
        "user": {"login": "github-actions[bot]"},
        "body": hosted.RESULT_MARKER + "\n" + json.dumps(result),
    }


def _pair(
    *,
    work_id: str = WORK_ID,
    request_id: str = "lineage-begin-1",
    begin_comment_id: int = 1001,
    result_comment_id: int = 2001,
    run_id: int = 3001,
    source_hex: str = "a",
) -> tuple[dict, dict, dict]:
    command = _command(work_id, request_id)
    result = _begin_result(
        command,
        begin_comment_id=begin_comment_id,
        run_id=run_id,
        source_hex=source_hex,
    )
    return command, _request_comment(command, begin_comment_id), _result_comment(result, result_comment_id)


class HostedCycleLineageR0Tests(unittest.TestCase):
    def test_exact_work_request_and_materialized_begin_form_one_candidate(self):
        command, request, result = _pair()
        lineage = hosted_cycle_lineage.build_work_lineage(
            [result, request], work_ref={"workId": WORK_ID}, issue_number=ISSUE_NUMBER
        )
        self.assertEqual(lineage, hosted_cycle_lineage.validate_work_lineage(lineage))
        self.assertFalse(lineage["ambiguous"])
        self.assertEqual([], lineage["pendingRequests"])
        self.assertEqual(1, len(lineage["candidates"]))
        candidate = lineage["candidates"][0]
        self.assertEqual(request["id"], candidate["requestCommentId"])
        self.assertEqual([result["id"]], candidate["resultCommentIds"])
        self.assertEqual(command["requestId"], candidate["requestId"])
        self.assertEqual(hosted.transport_command_hash(command), candidate["commandHash"])
        self.assertEqual("AVAILABLE", candidate["resumability"]["state"])
        self.assertNotIn("selected", lineage)
        self.assertNotIn("replay", lineage)

    def test_request_without_begin_result_is_pending_not_recoverable(self):
        command = _command(WORK_ID, "lineage-pending")
        request = _request_comment(command, 1010)
        lineage = hosted_cycle_lineage.build_work_lineage(
            [request], work_ref={"workId": WORK_ID}, issue_number=ISSUE_NUMBER
        )
        self.assertEqual([], lineage["candidates"])
        self.assertFalse(lineage["ambiguous"])
        self.assertEqual(1010, lineage["pendingRequests"][0]["commentId"])
        self.assertEqual(hosted.transport_command_hash(command), lineage["pendingRequests"][0]["commandHash"])

    def test_multiple_materialized_begins_remain_explicit_ambiguity(self):
        _, request_a, result_a = _pair()
        _, request_b, result_b = _pair(
            request_id="lineage-begin-2", begin_comment_id=1002,
            result_comment_id=2002, run_id=3002, source_hex="b",
        )
        lineage = hosted_cycle_lineage.build_work_lineage(
            [result_b, request_a, result_a, request_b],
            work_ref={"workId": WORK_ID}, issue_number=ISSUE_NUMBER,
        )
        self.assertTrue(lineage["ambiguous"])
        self.assertEqual([1001, 1002], [item["requestCommentId"] for item in lineage["candidates"]])
        self.assertNotIn("selected", lineage)

    def test_unrelated_work_lineage_is_not_promoted(self):
        _, target_request, target_result = _pair()
        _, other_request, other_result = _pair(
            work_id=OTHER_WORK_ID, request_id="other-begin", begin_comment_id=1015,
            result_comment_id=2015, run_id=3015, source_hex="c",
        )
        lineage = hosted_cycle_lineage.build_work_lineage(
            [other_result, target_result, other_request, target_request],
            work_ref={"workId": WORK_ID}, issue_number=ISSUE_NUMBER,
        )
        self.assertEqual(1, len(lineage["candidates"]))
        self.assertEqual(1001, lineage["candidates"][0]["requestCommentId"])

    def test_malformed_unrelated_result_is_ambient_not_target_failure(self):
        _, target_request, target_result = _pair()
        _, other_request, other_result = _pair(
            work_id=OTHER_WORK_ID, request_id="other-begin", begin_comment_id=1016,
            result_comment_id=2016, run_id=3016, source_hex="d",
        )
        payload = json.loads(other_result["body"].split("\n", 1)[1])
        payload["sourceSha"] = "f" * 40
        core = {key: copy.deepcopy(item) for key, item in payload.items() if key != "resultHash"}
        payload["resultHash"] = stable_hash(core)
        other_result["body"] = hosted.RESULT_MARKER + "\n" + json.dumps(payload)

        lineage = hosted_cycle_lineage.build_work_lineage(
            [other_request, other_result, target_request, target_result],
            work_ref={"workId": WORK_ID}, issue_number=ISSUE_NUMBER,
        )
        self.assertEqual([1001], [item["requestCommentId"] for item in lineage["candidates"]])

    def test_rehashed_target_result_cannot_substitute_source_binding(self):
        _, request, result_comment = _pair()
        payload = json.loads(result_comment["body"].split("\n", 1)[1])
        payload["sourceSha"] = "f" * 40
        core = {key: copy.deepcopy(item) for key, item in payload.items() if key != "resultHash"}
        payload["resultHash"] = stable_hash(core)
        result_comment["body"] = hosted.RESULT_MARKER + "\n" + json.dumps(payload)
        with self.assertRaisesRegex(RuntimeError, "HOSTED_CYCLE_LINEAGE_BEGIN_RESULT_BINDING_MISMATCH"):
            hosted_cycle_lineage.build_work_lineage(
                [request, result_comment], work_ref={"workId": WORK_ID}, issue_number=ISSUE_NUMBER
            )

    def test_malformed_canonical_request_fails_closed(self):
        command = _command(WORK_ID, "bad-marker")
        request = _request_comment(command, 1030)
        request["body"] = hosted.REQUEST_MARKER_V04 + "\n" + json.dumps(command)
        with self.assertRaisesRegex(RuntimeError, "HOSTED_CYCLE_LINEAGE_REQUEST_INVALID"):
            hosted_cycle_lineage.build_work_lineage(
                [request], work_ref={"workId": WORK_ID}, issue_number=ISSUE_NUMBER
            )

    def test_duplicate_identical_result_comments_are_transport_duplicates_not_cycles(self):
        _, request, result = _pair()
        duplicate = copy.deepcopy(result)
        duplicate["id"] = 2009
        lineage = hosted_cycle_lineage.build_work_lineage(
            [duplicate, request, result], work_ref={"workId": WORK_ID}, issue_number=ISSUE_NUMBER
        )
        self.assertEqual(1, len(lineage["candidates"]))
        self.assertEqual([2001, 2009], lineage["candidates"][0]["resultCommentIds"])

    def test_lineage_hash_tamper_is_rejected(self):
        _, request, result = _pair()
        lineage = hosted_cycle_lineage.build_work_lineage(
            [request, result], work_ref={"workId": WORK_ID}, issue_number=ISSUE_NUMBER
        )
        lineage["ambiguous"] = True
        with self.assertRaisesRegex(RuntimeError, "HOSTED_CYCLE_LINEAGE_AMBIGUITY_INVALID"):
            hosted_cycle_lineage.validate_work_lineage(lineage)


if __name__ == "__main__":
    unittest.main()
