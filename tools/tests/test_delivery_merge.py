from __future__ import annotations

import base64
import json
import unittest
from pathlib import Path

from tools import delivery_merge
from tools.coordination_remote import ApiResponse

WORK_HEAD = "1" * 40
WORK_TREE = "2" * 40
PR_HEAD = "3" * 40
TARGET = "4" * 40
MERGED = "5" * 40
WORK_ID = "delivery-test"
BRANCH = "work/operations/delivery-test"


def work_item(status: str = "READY") -> dict:
    remaining = ["integrate"] if status != "DONE" else []
    return {
        "schemaVersion": "ContinuationState 0.2",
        "id": WORK_ID,
        "workerId": "manager-gitops-chat",
        "status": status,
        "branch": BRANCH,
        "prNumber": 77,
        "dependsOn": [],
        "completed": [],
        "remaining": remaining,
        "nextAction": "Integrate PR" if remaining else None,
        "lastKnownGood": {"sha": None, "checkpoint": None},
        "blockers": [],
        "handoffToWorkerId": None,
    }


def request(**overrides) -> dict:
    value = {
        "schemaVersion": "HostedDeliveryMergeRequest 0.1",
        "requestId": "delivery-test-merge",
        "actor": {
            "role": "manager-gitops",
            "workerId": "manager-gitops-chat",
            "sessionId": "delivery-test-session",
        },
        "workId": WORK_ID,
        "prNumber": 77,
        "expectedWorkAuthorityHead": WORK_HEAD,
        "expectedHeadSha": PR_HEAD,
        "expectedBase": "main",
        "expectedTargetSha": TARGET,
        "mergeMethod": "squash",
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    value.update(overrides)
    return value


class FakeTransport:
    def __init__(self, *, status="READY", ci="success", agent_ops_ci=None, head=PR_HEAD, base="main", target=TARGET, changed_files=None, merge_parent=TARGET):
        self.work = work_item(status)
        self.ci = ci
        self.agent_ops_ci = ci if agent_ops_ci is None else agent_ops_ci
        self.head = head
        self.base = base
        self.target = target
        self.merged = False
        self.merge_calls = 0
        self.calls = []
        self.advance_target = True
        self.changed_files = ["tools/delivery_merge.py"] if changed_files is None else list(changed_files)
        self.merge_parent = merge_parent

    def _response(self, value):
        return ApiResponse(None, {}, json.dumps(value))

    def request(self, method, endpoint, *, payload=None, include_headers=False):
        self.calls.append((method, endpoint, payload))
        if method == "GET" and endpoint.endswith("git/ref/heads/coordination%2Fcontinuations"):
            return self._response({"object": {"sha": WORK_HEAD}})
        if method == "GET" and endpoint.endswith(f"git/commits/{WORK_HEAD}"):
            return self._response({"tree": {"sha": WORK_TREE}})
        if method == "GET" and endpoint.endswith(f"contents/ops/continuations?ref={WORK_HEAD}"):
            return self._response([{"name": f"{WORK_ID}.json"}])
        if method == "GET" and endpoint.endswith(
            f"contents/ops/continuations/{WORK_ID}.json?ref={WORK_HEAD}"
        ):
            raw = json.dumps(self.work).encode("utf-8")
            return self._response({"encoding": "base64", "content": base64.b64encode(raw).decode("ascii")})
        if method == "GET" and endpoint.endswith("pulls/77"):
            return self._response({
                "number": 77,
                "state": "closed" if self.merged else "open",
                "draft": False,
                "merged": self.merged,
                "head": {"sha": self.head, "ref": BRANCH, "repo": {"full_name": delivery_merge.REPOSITORY}},
                "base": {"ref": self.base},
                "merge_commit_sha": MERGED if self.merged else None,
            })
        if method == "GET" and endpoint.endswith("git/ref/heads/main"):
            return self._response({"object": {"sha": self.target}})
        if method == "GET" and endpoint.endswith("pulls/77/files?per_page=100&page=1"):
            return self._response([{"filename": path} for path in self.changed_files])
        if method == "GET" and "/actions/runs?" in endpoint:
            conclusion = None if self.ci == "pending" else self.ci
            status = "in_progress" if self.ci == "pending" else "completed"
            agent_conclusion = None if self.agent_ops_ci == "pending" else self.agent_ops_ci
            agent_status = "in_progress" if self.agent_ops_ci == "pending" else "completed"
            return self._response({"workflow_runs": [
                {"name": "Agent Ops", "id": 9, "status": agent_status, "conclusion": agent_conclusion},
                {"name": "Coordination Guard", "id": 10, "status": status, "conclusion": conclusion},
                {"name": "Supervisor Snapshot", "id": 11, "status": status, "conclusion": conclusion},
            ]})
        if method == "PUT" and endpoint.endswith("pulls/77/merge"):
            self.merge_calls += 1
            self.merged = True
            if self.advance_target:
                self.target = MERGED
            return self._response({"merged": True, "sha": MERGED, "message": "merged"})
        if method == "GET" and endpoint.endswith(f"git/commits/{MERGED}"):
            return self._response({"tree": {"sha": "6" * 40}, "parents": [{"sha": self.merge_parent}]})
        if method == "GET" and endpoint.endswith(f"compare/{MERGED}...{self.target}"):
            return self._response({"status": "behind", "merge_base_commit": {"sha": self.target}})
        raise AssertionError(f"unexpected request: {method} {endpoint} {payload}")


class DeliveryMergeTests(unittest.TestCase):
    def test_success_reobserves_and_returns_hash_bound_readback(self):
        transport = FakeTransport()
        dispatch = delivery_merge.prepare(request(), transport)
        self.assertEqual(dispatch["plan"]["operation"], "merge-pr")
        self.assertEqual(dispatch["plan"]["riskClass"], "integration-write")
        self.assertEqual(dispatch["ci"]["status"], "green")
        result = delivery_merge.execute(dispatch, transport)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["mergedSha"], MERGED)
        self.assertEqual(result["afterTargetSha"], MERGED)
        self.assertTrue(result["targetContainsMergedSha"])
        self.assertFalse(result["semanticAuthority"])
        self.assertFalse(result["authorizesMutation"])
        self.assertEqual(transport.merge_calls, 1)
        self.assertFalse(any(method in {"POST", "PATCH", "DELETE"} for method, _, _ in transport.calls))

    def test_terminal_work_is_rejected(self):
        with self.assertRaisesRegex(delivery_merge.DeliveryMergeError, "DELIVERY_MERGE_WORK_NOT_ACTIVE"):
            delivery_merge.prepare(request(), FakeTransport(status="DONE"))

    def test_pr_head_drift_is_rejected(self):
        with self.assertRaisesRegex(delivery_merge.DeliveryMergeError, "DELIVERY_MERGE_PR_HEAD_DRIFT"):
            delivery_merge.prepare(request(), FakeTransport(head="a" * 40))

    def test_pr_base_drift_is_rejected(self):
        with self.assertRaisesRegex(delivery_merge.DeliveryMergeError, "DELIVERY_MERGE_PR_BASE_DRIFT"):
            delivery_merge.prepare(request(), FakeTransport(base="development"))

    def test_target_drift_is_rejected(self):
        with self.assertRaisesRegex(delivery_merge.DeliveryMergeError, "DELIVERY_MERGE_TARGET_DRIFT"):
            delivery_merge.prepare(request(), FakeTransport(target="b" * 40))

    def test_non_green_ci_is_rejected(self):
        for state, expected in (("pending", "PENDING"), ("failure", "FAILED"), ("action_required", "UNKNOWN")):
            with self.subTest(state=state):
                transport = FakeTransport(ci=state)
                with self.assertRaisesRegex(delivery_merge.DeliveryMergeError, f"DELIVERY_MERGE_CI_{expected}"):
                    delivery_merge.prepare(request(), transport)
                self.assertEqual(transport.merge_calls, 0)

    def test_operations_agent_ops_is_a_required_green_gate(self):
        transport = FakeTransport(agent_ops_ci="failure")
        with self.assertRaisesRegex(delivery_merge.DeliveryMergeError, "DELIVERY_MERGE_CI_FAILED"):
            delivery_merge.prepare(request(), transport)
        self.assertEqual(transport.merge_calls, 0)

    def test_integration_boundary_violation_is_rejected(self):
        transport = FakeTransport(changed_files=["viewer-next/src/ui/forbidden.ts"])
        with self.assertRaisesRegex(delivery_merge.DeliveryMergeError, "DELIVERY_MERGE_BOUNDARY_VIOLATION"):
            delivery_merge.prepare(request(), transport)
        self.assertEqual(transport.merge_calls, 0)

    def test_squash_merge_parent_must_equal_reobserved_target(self):
        transport = FakeTransport(merge_parent="e" * 40)
        dispatch = delivery_merge.prepare(request(), transport)
        with self.assertRaisesRegex(delivery_merge.DeliveryMergeError, "DELIVERY_MERGE_TARGET_PARENT_DRIFT"):
            delivery_merge.execute(dispatch, transport)
        self.assertEqual(transport.merge_calls, 1)

    def test_dispatch_is_hash_bound(self):
        transport = FakeTransport()
        dispatch = delivery_merge.prepare(request(), transport)
        dispatch["mergeMethod"] = "merge"
        with self.assertRaisesRegex(delivery_merge.DeliveryMergeError, "DELIVERY_MERGE_DISPATCH_HASH_MISMATCH"):
            delivery_merge.execute(dispatch, transport)
        self.assertEqual(transport.merge_calls, 0)

    def test_execute_blocks_if_preconditions_drift_after_prepare(self):
        transport = FakeTransport()
        dispatch = delivery_merge.prepare(request(), transport)
        transport.target = "c" * 40
        with self.assertRaisesRegex(delivery_merge.DeliveryMergeError, "DELIVERY_MERGE_TARGET_DRIFT"):
            delivery_merge.execute(dispatch, transport)
        self.assertEqual(transport.merge_calls, 0)

    def test_main_readback_must_contain_provider_merge_sha(self):
        transport = FakeTransport()
        dispatch = delivery_merge.prepare(request(), transport)
        transport.advance_target = False
        with self.assertRaisesRegex(delivery_merge.DeliveryMergeError, "DELIVERY_MERGE_TARGET_READBACK_MISMATCH"):
            delivery_merge.execute(dispatch, transport)
        self.assertEqual(transport.merge_calls, 1)

    def test_request_is_closed_and_non_authoritative(self):
        value = request(authorizesMutation=True)
        with self.assertRaisesRegex(delivery_merge.DeliveryMergeError, "DELIVERY_MERGE_REQUEST_MUST_NOT_AUTHORIZE"):
            delivery_merge.validate_request(value)

    def test_v01_accepts_only_squash_merge(self):
        with self.assertRaisesRegex(delivery_merge.DeliveryMergeError, "DELIVERY_MERGE_METHOD_INVALID"):
            delivery_merge.validate_request(request(mergeMethod="merge"))

    def test_work_authority_is_cas_bound(self):
        with self.assertRaisesRegex(delivery_merge.DeliveryMergeError, "DELIVERY_MERGE_WORK_AUTHORITY_DRIFT"):
            delivery_merge.prepare(request(expectedWorkAuthorityHead="d" * 40), FakeTransport())

    def test_work_pr_binding_is_required(self):
        transport = FakeTransport()
        transport.work["prNumber"] = 78
        with self.assertRaisesRegex(delivery_merge.DeliveryMergeError, "DELIVERY_MERGE_WORK_BINDING_MISMATCH"):
            delivery_merge.prepare(request(), transport)

    def test_hosted_workflow_is_narrow_and_does_not_mutate_work(self):
        workflow = (Path(__file__).resolve().parents[2] / ".github/workflows/hosted-delivery-merge.yml").read_text(encoding="utf-8")
        self.assertIn("MOBILIPRESENTER_DELIVERY_MERGE_REQUEST_V0_1", workflow)
        self.assertIn("pull-requests: write", workflow)
        self.assertIn("actions: read", workflow)
        self.assertIn("python tools/hosted_delivery_merge.py", workflow)
        self.assertNotIn("coordination/continuations", workflow)
        self.assertNotIn("continuation_transition", workflow)


if __name__ == "__main__":
    unittest.main()
