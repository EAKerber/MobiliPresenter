from __future__ import annotations

import copy
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tools import agent_cycle_identity, agent_delivery, agent_write_lifecycle, delivery_merge
from tools.canonical import stable_hash
from tools.continuation_remote import Observation

REPOSITORY = "EAKerber/MobiliPresenter"
BRANCH = "work/operations/r5-delivery-test"
WORK_ID = "r5-delivery-test"
PR_NUMBER = 300
HEAD = "c" * 40
MAIN = "d" * 40
AUTHORITY = "e" * 40
ACTOR = {
    "role": "manager-gitops",
    "workerId": "manager-gitops-chat",
    "sessionId": "session-r5-delivery",
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
RESUME_TOKEN = "hosted-v1:" + json.dumps(LOCATOR, sort_keys=True, separators=(",", ":"))
HANDLE = agent_cycle_identity.build_handle(
    repository=REPOSITORY,
    cycle_id="cycle-" + "6" * 20,
    cycle_instance_id=CYCLE_INSTANCE_ID,
    context_schema_version="AgentCycleContext 0.4",
    context_hash=CONTEXT_HASH,
    actor=ACTOR,
    resume_token=RESUME_TOKEN,
)


def work(status="IN_PROGRESS"):
    return {
        "schemaVersion": "ContinuationState 0.2",
        "id": WORK_ID,
        "workerId": "manager-gitops-chat",
        "status": status,
        "branch": BRANCH,
        "prNumber": PR_NUMBER,
        "dependsOn": [],
        "completed": ["implemented"],
        "remaining": [] if status == "DONE" else ["integrate"],
        "nextAction": None if status == "DONE" else "integrate",
        "lastKnownGood": {"sha": None, "checkpoint": None},
        "blockers": [],
        "handoffToWorkerId": None,
    }


class FakeTransport:
    def __init__(self):
        self.calls = []

    def request(self, method, endpoint, *, payload=None, include_headers=False):
        del include_headers
        self.calls.append((method, endpoint, copy.deepcopy(payload)))
        if method == "GET" and endpoint.endswith(f"/pulls/{PR_NUMBER}"):
            value = {
                "number": PR_NUMBER,
                "state": "open",
                "draft": False,
                "merged": False,
                "head": {"sha": HEAD, "ref": BRANCH, "repo": {"full_name": REPOSITORY}},
                "base": {"ref": "main"},
            }
            return SimpleNamespace(body=json.dumps(value))
        if method == "GET" and endpoint.endswith("/git/ref/heads/main"):
            return SimpleNamespace(body=json.dumps({"object": {"sha": MAIN}}))
        if method == "POST" and endpoint.endswith("/issues/145/comments"):
            return SimpleNamespace(body=json.dumps({"id": 900}))
        raise AssertionError((method, endpoint, payload))


def delivery_result(active_work=None):
    snapshot = active_work or work()
    core = {
        "schemaVersion": delivery_merge.RESULT_SCHEMA,
        "repository": REPOSITORY,
        "requestId": "r5-delivery",
        "requestHash": "1" * 64,
        "dispatchHash": "2" * 64,
        "planHash": "3" * 64,
        "work": {
            "authorityHead": AUTHORITY,
            "id": snapshot["id"],
            "workerId": snapshot["workerId"],
            "status": "IN_PROGRESS",
            "branch": snapshot["branch"],
            "prNumber": snapshot["prNumber"],
            "stateHash": "4" * 64,
        },
        "prNumber": PR_NUMBER,
        "expectedHeadSha": HEAD,
        "beforeTargetSha": MAIN,
        "mergedSha": "f" * 40,
        "afterTargetSha": "f" * 40,
        "mergedCommitParentSha": MAIN,
        "targetContainsMergedSha": True,
        "mergeMethod": "squash",
        "ci": {"status": "green"},
        "status": "PASS",
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**core, "resultHash": stable_hash(core)}


def released_result():
    binding_core = {
        "schemaVersion": agent_write_lifecycle.BINDING_SCHEMA,
        "cycleInstanceId": CYCLE_INSTANCE_ID,
        "begin": {"runId": 123, "sourceSha": "a" * 40, "contextHash": CONTEXT_HASH},
        "actor": ACTOR,
        "branch": BRANCH,
        "state": "RELEASED",
        "leaseId": "lease-r5",
        "expiresAt": None,
        "previousBindingHash": "5" * 64,
        "authorityHead": "6" * 40,
        "dispatchHash": "7" * 64,
        "receiptHash": "8" * 64,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    binding = {**binding_core, "bindingHash": stable_hash(binding_core)}
    result = {
        "schemaVersion": agent_write_lifecycle.RESULT_SCHEMA,
        "requestId": "release-r5",
        "requestHash": "9" * 64,
        "action": "release",
        "begin": binding["begin"],
        "cycleInstanceId": CYCLE_INSTANCE_ID,
        "actor": ACTOR,
        "branch": BRANCH,
        "dispatchHash": "7" * 64,
        "binding": binding,
        "remoteReceipt": {"opaque": "validated-by-mock"},
        "remoteReceiptHash": "8" * 64,
        "status": "PASS",
        "blockers": [],
        "semanticAuthority": False,
        "authorizesMutation": False,
        "resultHash": "a" * 64,
    }
    return result


class AgentDeliveryR5Tests(unittest.TestCase):
    def test_build_derives_existing_delivery_request_from_live_work_pr_and_main(self):
        transport = FakeTransport()
        authority = SimpleNamespace(observe=lambda: Observation(AUTHORITY, "0" * 40, {WORK_ID: work()}))
        with patch.object(agent_delivery, "GitHubContinuationAuthority", return_value=authority):
            request = agent_delivery.build_delivery_request(
                handle=HANDLE,
                work_id=WORK_ID,
                request_id="r5-delivery-test",
                transport=transport,
            )
        self.assertEqual("HostedDeliveryMergeRequest 0.1", request["schemaVersion"])
        self.assertEqual(AUTHORITY, request["expectedWorkAuthorityHead"])
        self.assertEqual(PR_NUMBER, request["prNumber"])
        self.assertEqual(HEAD, request["expectedHeadSha"])
        self.assertEqual("main", request["expectedBase"])
        self.assertEqual(MAIN, request["expectedTargetSha"])
        self.assertEqual("squash", request["mergeMethod"])
        self.assertEqual(ACTOR, request["actor"])
        self.assertFalse(request["semanticAuthority"])
        self.assertFalse(request["authorizesMutation"])
        self.assertTrue(all(call[0] == "GET" for call in transport.calls))

    def test_submit_uses_only_existing_delivery_marker_and_never_merges(self):
        transport = FakeTransport()
        authority = SimpleNamespace(observe=lambda: Observation(AUTHORITY, "0" * 40, {WORK_ID: work()}))
        with patch.object(agent_delivery, "GitHubContinuationAuthority", return_value=authority):
            value = agent_delivery.compose_delivery(
                handle=HANDLE,
                work_id=WORK_ID,
                request_id="r5-delivery-submit",
                submit=True,
                transport=transport,
            )
        self.assertEqual(900, value["requestCommentId"])
        post = [call for call in transport.calls if call[0] == "POST"]
        self.assertEqual(1, len(post))
        self.assertTrue(post[0][2]["body"].startswith("MOBILIPRESENTER_DELIVERY_MERGE_REQUEST_V0_1\n"))
        self.assertFalse(any(call[0] == "PUT" for call in transport.calls))

    def test_work_pr_branch_mismatch_fails_closed(self):
        transport = FakeTransport()
        bad = work(); bad["branch"] = "work/operations/other"
        authority = SimpleNamespace(observe=lambda: Observation(AUTHORITY, "0" * 40, {WORK_ID: bad}))
        with patch.object(agent_delivery, "GitHubContinuationAuthority", return_value=authority):
            with self.assertRaisesRegex(agent_delivery.AgentDeliveryError, "WORK_BRANCH_MISMATCH"):
                agent_delivery.build_delivery_request(
                    handle=HANDLE, work_id=WORK_ID, request_id="r5-mismatch", transport=transport
                )

    def test_finalization_requires_semantic_work_completion_first(self):
        projection = agent_delivery.project_finalization(
            handle=HANDLE,
            delivery_result=delivery_result(),
            work=work(),
        )
        self.assertEqual(agent_delivery.FINALIZATION_ORDER, projection["finalizationOrder"])
        self.assertEqual("COMPLETE_WORK", projection["nextSafeAction"])
        self.assertEqual([], projection["automaticTransitions"])
        self.assertFalse(projection["executesActions"])
        self.assertTrue(projection["readOnly"])
        self.assertFalse(projection["semanticAuthority"])
        self.assertFalse(projection["authorizesMutation"])

    def test_finalization_requires_release_after_work_done(self):
        projection = agent_delivery.project_finalization(
            handle=HANDLE,
            delivery_result=delivery_result(),
            work=work("DONE"),
        )
        self.assertEqual("RELEASE_OWNERSHIP", projection["nextSafeAction"])
        self.assertEqual("DONE", projection["steps"][0]["disposition"])
        self.assertEqual("REQUIRED", projection["steps"][1]["disposition"])
        self.assertEqual("BLOCKED_BY_PREVIOUS", projection["steps"][2]["disposition"])

    def test_finalization_projects_cycle_close_only_after_release(self):
        release = released_result()
        with patch.object(agent_delivery.agent_write_lifecycle, "validate_result", return_value=release):
            projection = agent_delivery.project_finalization(
                handle=HANDLE,
                delivery_result=delivery_result(),
                work=work("DONE"),
                ownership_result=release,
            )
        self.assertEqual("CLOSE_AGENT_CYCLE", projection["nextSafeAction"])
        self.assertEqual("DONE", projection["steps"][1]["disposition"])
        self.assertEqual("REQUIRED", projection["steps"][2]["disposition"])
        self.assertEqual([], projection["automaticTransitions"])

    def test_release_before_work_completion_is_order_violation(self):
        release = released_result()
        with patch.object(agent_delivery.agent_write_lifecycle, "validate_result", return_value=release):
            with self.assertRaisesRegex(agent_delivery.AgentDeliveryError, "ORDER_VIOLATION"):
                agent_delivery.project_finalization(
                    handle=HANDLE,
                    delivery_result=delivery_result(),
                    work=work(),
                    ownership_result=release,
                )


if __name__ == "__main__":
    unittest.main()
