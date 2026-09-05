from __future__ import annotations

import copy
import json
import unittest

from tools import agent_cycle_identity, agent_failure, continuation
from tools import hosted_agent_cycle as hosted
from tools import hosted_agent_cycle_waiting
from tools import hosted_cycle_artifact, hosted_cycle_handle, hosted_cycle_reentry
from tools.canonical import stable_hash

ISSUE_NUMBER = 145
WORK_ID = "m13-r0-reentry-test"
HEAD = "a" * 40
ACTOR = {
    "role": "manager-gitops",
    "workerId": "manager-gitops-a",
    "sessionId": "m13-r0-reentry",
}


def _work(status: str = "IN_PROGRESS") -> dict:
    value = {
        "schemaVersion": continuation.CURRENT_SCHEMA_VERSION,
        "id": WORK_ID,
        "workerId": "manager-gitops-a",
        "status": status,
        "branch": None,
        "prNumber": None,
        "dependsOn": [],
        "completed": [],
        "remaining": ["finish-r0"],
        "nextAction": "continue-r0",
        "lastKnownGood": {"sha": HEAD, "checkpoint": "M13-R0"},
        "blockers": [],
        "handoffToWorkerId": None,
    }
    if status == "WAITING":
        value["blockers"] = ["external-result"]
        value["nextAction"] = "wait-for-result"
    elif status == "HANDOFF":
        value["handoffToWorkerId"] = "manager-gitops-b"
        value["nextAction"] = "handoff"
    elif status == "DONE":
        value["completed"] = ["finish-r0"]
        value["remaining"] = []
        value["nextAction"] = None
    return continuation.valid(value, WORK_ID)


def _begin_command(request_id: str = "begin-r0") -> dict:
    return {
        "schemaVersion": hosted.COMMAND_SCHEMA_V03,
        "requestId": request_id,
        "action": "begin",
        "actor": copy.deepcopy(ACTOR),
        "declaredIntent": "inspect-and-plan",
        "machineScope": "live",
        "workRef": {"workId": WORK_ID},
        "evidenceCommentIds": [],
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


def _owner_comment(marker: str, payload: dict, cid: int) -> dict:
    return {
        "id": cid,
        "author_association": "OWNER",
        "user": {"login": "EAKerber"},
        "body": marker + "\n" + json.dumps(payload),
    }


def _bot_comment(payload: dict, cid: int) -> dict:
    return {
        "id": cid,
        "author_association": "CONTRIBUTOR",
        "user": {"login": "github-actions[bot]"},
        "body": hosted.RESULT_MARKER + "\n" + json.dumps(payload),
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
    resume_token = hosted_cycle_handle.build_resume_token({
        "source": copy.deepcopy(source),
        "artifactName": artifact_name,
        "contextHash": context_hash,
        "cycleInstanceId": cycle_instance_id,
    })
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
    resumability = hosted_cycle_artifact.classify_artifact_response(
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
        "resumability": resumability,
    }
    return {**core, "resultHash": stable_hash(core)}


def _begin_pair(*, request_id="begin-r0", begin_id=1001, result_id=2001, run_id=3001, source_hex="b"):
    command = _begin_command(request_id)
    result = _begin_result(command, begin_comment_id=begin_id, run_id=run_id, source_hex=source_hex)
    return (
        _owner_comment(hosted.REQUEST_MARKER_V03, command, begin_id),
        _bot_comment(result, result_id),
        result,
    )


def _close_command(handle: dict, request_id: str = "close-r0") -> dict:
    return {
        "schemaVersion": hosted.COMMAND_SCHEMA_V02,
        "requestId": request_id,
        "action": "close",
        "handle": copy.deepcopy(handle),
        "evidenceCommentIds": [],
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


def _close_pass(command: dict, begin_result: dict, *, run_id=4001, source_hex="c") -> dict:
    core = {
        "schemaVersion": hosted.CLOSE_RESULT_SCHEMA,
        "requestId": command["requestId"],
        "commandHash": hosted.transport_command_hash(command),
        "runId": run_id,
        "sourceSha": source_hex * 40,
        "beginRunId": begin_result["runId"],
        "cycleId": begin_result["cycleId"],
        "contextHash": begin_result["contextHash"],
        "receiptHash": stable_hash({"receipt": run_id}),
        "closureHash": stable_hash({"closure": run_id}),
        "status": "PASS",
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**core, "resultHash": stable_hash(core)}


def _waiting(command: dict, begin_result: dict) -> dict:
    core = {
        "schemaVersion": hosted_agent_cycle_waiting.WAITING_SCHEMA,
        "requestId": command["requestId"],
        "commandHash": hosted.transport_command_hash(command),
        "cycleInstanceId": begin_result["cycleInstanceId"],
        "status": "WAITING",
        "waitingFor": ["REMOTE_CANONICAL_RESULT"],
        "observationRetry": "SAFE",
        "operationReplay": "NOT_APPLICABLE",
        "sourceFailureHash": stable_hash({"source": "wait"}),
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**core, "resultHash": stable_hash(core)}


def _failure(command: dict) -> dict:
    failure_core = agent_failure.build_failure_core(
        surface="AGENT_CYCLE",
        phase="CLOSE",
        status="BLOCKED",
        causes=[{"code": "HOSTED_AGENT_CLOSE_NOT_PASS", "source": "hosted-agent-cycle", "phase": "CLOSE"}],
        observation_retry="NOT_APPLICABLE",
        operation_replay="NOT_APPLICABLE",
        mutation_state="NOT_APPLICABLE",
    )
    core = {
        "schemaVersion": agent_failure.HOSTED_CYCLE_FAILURE_SCHEMA,
        "requestId": command["requestId"],
        "commandHash": hosted.transport_command_hash(command),
        "status": "BLOCKED",
        "failureCore": failure_core,
    }
    return {**core, "failureHash": stable_hash(core)}


def _inspect(comments, status="IN_PROGRESS"):
    return hosted_cycle_reentry.inspect_reentry(
        comments,
        work=_work(status),
        work_authority_head=HEAD,
        issue_number=ISSUE_NUMBER,
    )


class HostedCycleReentryR0Tests(unittest.TestCase):
    def test_fresh_active_work_can_begin_new_cycle(self):
        result = _inspect([])
        self.assertEqual("CLEAN_REENTRY", result["state"])
        self.assertEqual("BEGIN_NEW_CYCLE", result["nextSafeAction"])
        self.assertEqual(["NO_MATERIALIZED_CYCLE"], result["reasonCodes"])
        self.assertIsNone(result["targetCycle"])

    def test_one_open_resumable_cycle_is_exact_reentry_target(self):
        request, begin_comment, begin_result = _begin_pair()
        result = _inspect([begin_comment, request])
        self.assertEqual("CLEAN_REENTRY", result["state"])
        self.assertEqual("RESUME_EXACT_CYCLE", result["nextSafeAction"])
        self.assertEqual(begin_result["cycleInstanceId"], result["targetCycle"]["cycleInstanceId"])
        self.assertEqual(begin_result["handle"], result["targetCycle"]["handle"])
        self.assertEqual("OPEN", result["cycleOutcomes"][0]["state"])

    def test_passed_cycle_allows_new_cycle(self):
        begin_request, begin_comment, begin_result = _begin_pair()
        close = _close_command(begin_result["handle"])
        close_request = _owner_comment(hosted.REQUEST_MARKER_V02, close, 3001)
        close_result = _bot_comment(_close_pass(close, begin_result), 4001)
        result = _inspect([begin_request, begin_comment, close_request, close_result])
        self.assertEqual("CLEAN_REENTRY", result["state"])
        self.assertEqual("BEGIN_NEW_CYCLE", result["nextSafeAction"])
        self.assertEqual(["PREVIOUS_CYCLE_CLOSED"], result["reasonCodes"])
        self.assertEqual("PASS", result["cycleOutcomes"][0]["state"])

    def test_work_waiting_is_legitimate_wait_without_inventing_recovery(self):
        result = _inspect([], status="WAITING")
        self.assertEqual("LEGITIMATE_WAIT", result["state"])
        self.assertEqual("WAIT", result["nextSafeAction"])
        self.assertEqual(["WORK_WAITING"], result["reasonCodes"])

    def test_hosted_waiting_is_legitimate_wait(self):
        begin_request, begin_comment, begin_result = _begin_pair()
        close = _close_command(begin_result["handle"])
        close_request = _owner_comment(hosted.REQUEST_MARKER_V02, close, 3001)
        wait_result = _bot_comment(_waiting(close, begin_result), 4001)
        result = _inspect([begin_request, begin_comment, close_request, wait_result])
        self.assertEqual("LEGITIMATE_WAIT", result["state"])
        self.assertEqual("WAIT", result["nextSafeAction"])
        self.assertIn("HOSTED_CYCLE_WAITING", result["reasonCodes"])
        self.assertIn("REMOTE_CANONICAL_RESULT", result["reasonCodes"])

    def test_pending_begin_is_insufficient_observation(self):
        command = _begin_command("pending-r0")
        request = _owner_comment(hosted.REQUEST_MARKER_V03, command, 1010)
        result = _inspect([request])
        self.assertEqual("INSUFFICIENT_OBSERVATION", result["state"])
        self.assertEqual("OBSERVE", result["nextSafeAction"])
        self.assertEqual(["HOSTED_BEGIN_PENDING"], result["reasonCodes"])

    def test_multiple_materialized_cycles_remain_insufficient_observation(self):
        a = _begin_pair()
        b = _begin_pair(request_id="begin-r0-b", begin_id=1002, result_id=2002, run_id=3002, source_hex="d")
        result = _inspect([a[0], a[1], b[0], b[1]])
        self.assertEqual("INSUFFICIENT_OBSERVATION", result["state"])
        self.assertEqual(["HOSTED_CYCLE_LINEAGE_AMBIGUOUS"], result["reasonCodes"])

    def test_close_request_without_result_is_insufficient_observation(self):
        begin_request, begin_comment, begin_result = _begin_pair()
        close = _close_command(begin_result["handle"])
        close_request = _owner_comment(hosted.REQUEST_MARKER_V02, close, 3001)
        result = _inspect([begin_request, begin_comment, close_request])
        self.assertEqual("INSUFFICIENT_OBSERVATION", result["state"])
        self.assertEqual("PENDING_CLOSE_RESULT", result["cycleOutcomes"][0]["state"])
        self.assertEqual(["HOSTED_CLOSE_RESULT_PENDING"], result["reasonCodes"])

    def test_close_failure_requires_reconciliation_not_replay(self):
        begin_request, begin_comment, begin_result = _begin_pair()
        close = _close_command(begin_result["handle"])
        close_request = _owner_comment(hosted.REQUEST_MARKER_V02, close, 3001)
        failure = _bot_comment(_failure(close), 4001)
        result = _inspect([begin_request, begin_comment, close_request, failure])
        self.assertEqual("PRIORITY_OPERATION_REQUIRED", result["state"])
        self.assertEqual("RECONCILE_FAILURE", result["nextSafeAction"])
        self.assertIn("HOSTED_AGENT_CLOSE_NOT_PASS", result["reasonCodes"])
        self.assertFalse(result["authorizesMutation"])

    def test_handoff_is_priority_operation_not_cycle_recovery(self):
        result = _inspect([], status="HANDOFF")
        self.assertEqual("PRIORITY_OPERATION_REQUIRED", result["state"])
        self.assertEqual("HONOR_HANDOFF", result["nextSafeAction"])
        self.assertEqual(["WORK_HANDOFF"], result["reasonCodes"])

    def test_done_work_needs_no_reentry_when_no_cycle_is_open(self):
        result = _inspect([], status="DONE")
        self.assertEqual("NO_REENTRY_REQUIRED", result["state"])
        self.assertEqual("NONE", result["nextSafeAction"])
        self.assertEqual(["WORK_DONE"], result["reasonCodes"])

    def test_done_work_with_open_cycle_fails_closed(self):
        begin_request, begin_comment, _ = _begin_pair()
        result = _inspect([begin_request, begin_comment], status="DONE")
        self.assertEqual("INSUFFICIENT_OBSERVATION", result["state"])
        self.assertEqual(["WORK_DONE_WITH_NONTERMINAL_CYCLE"], result["reasonCodes"])

    def test_projection_binds_authority_work_and_lineage_hashes(self):
        result = _inspect([])
        self.assertEqual(HEAD, result["workAuthorityHead"])
        self.assertEqual(continuation.state_hash(_work()), result["workStateHash"])
        self.assertEqual(result, hosted_cycle_reentry.validate_reentry(result))
        tampered = copy.deepcopy(result)
        tampered["nextSafeAction"] = "RESUME_EXACT_CYCLE"
        core = {key: copy.deepcopy(item) for key, item in tampered.items() if key != "inspectionHash"}
        tampered["inspectionHash"] = stable_hash(core)
        with self.assertRaisesRegex(RuntimeError, "TARGET_REQUIRED"):
            hosted_cycle_reentry.validate_reentry(tampered)


if __name__ == "__main__":
    unittest.main()
