from __future__ import annotations

import copy
import inspect
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from tools import agent_write_lifecycle_guard as guard
from tools.canonical import stable_hash


NOW = datetime(2026, 9, 22, 0, 0, tzinfo=timezone.utc)
CYCLE_ID = "cycle-instance-" + "1" * 24
BRANCH = "work/operations/e2-portable-write-lifecycle-proof"
ACTOR = {
    "role": "manager-gitops",
    "workerId": "manager-gitops-a",
    "sessionId": "session-e2",
}
BEGIN = {
    "runId": 123,
    "sourceSha": "a" * 40,
    "contextHash": "b" * 64,
}


def plan() -> dict:
    return {
        "requestHash": "c" * 64,
        "planHash": "d" * 64,
        "begin": copy.deepcopy(BEGIN),
        "actor": copy.deepcopy(ACTOR),
        "target": {"branch": BRANCH},
    }


def lifecycle_result(*, state: str = "ACTIVE", branch: str = BRANCH) -> dict:
    binding = {
        "state": state,
        "cycleInstanceId": CYCLE_ID,
        "begin": copy.deepcopy(BEGIN),
        "actor": copy.deepcopy(ACTOR),
        "branch": branch,
        "leaseId": "lease-e2",
        "expiresAt": "2026-09-22T01:00:00Z" if state == "ACTIVE" else None,
        "bindingHash": "e" * 64,
    }
    return {
        "schemaVersion": "AgentWriteLeaseResult 0.1",
        "cycleInstanceId": CYCLE_ID,
        "begin": copy.deepcopy(BEGIN),
        "actor": copy.deepcopy(ACTOR),
        "branch": branch,
        "binding": binding,
        "resultHash": "f" * 64,
    }


def matching_lease() -> dict:
    return {
        "leaseId": "lease-e2",
        "resource": f"branch:{BRANCH}",
        "owner": {
            "role": ACTOR["role"],
            "session": ACTOR["sessionId"],
            "branch": BRANCH,
            "pr": None,
        },
    }


class FakeAuthority:
    def observe(self):
        return SimpleNamespace(
            state={"schemaVersion": "CoordinationState 0.1"},
            head_sha="1" * 40,
            authority_now=NOW,
        )


class PortableLifecycleProofTests(unittest.TestCase):
    def _prove(self, result=None, *, leases=None, expired=False):
        result = lifecycle_result() if result is None else result
        leases = [matching_lease()] if leases is None else leases
        with (
            patch.object(guard.lifecycle, "validate_result", side_effect=lambda value: value),
            patch.object(guard.lifecycle, "binding_is_expired", return_value=expired),
            patch.object(guard.coordination, "active_leases", return_value=leases),
        ):
            return guard.prove_binding_result(
                plan(),
                cycle_instance_id=CYCLE_ID,
                lifecycle_result=result,
                lifecycle_result_ref={
                    "kind": "provided-result",
                    "value": result["resultHash"],
                },
                authority=FakeAuthority(),
            )

    def test_portable_result_produces_current_proof_without_hosted_metadata(self):
        proof = self._prove()
        self.assertEqual(proof["schemaVersion"], guard.PROOF_SCHEMA)
        self.assertEqual(
            proof["lifecycleResultRef"],
            {"kind": "provided-result", "value": "f" * 64},
        )
        self.assertNotIn("lifecycleResultCommentId", proof)
        self.assertEqual(proof["leaseId"], "lease-e2")
        self.assertEqual(
            guard.validate_active_binding_proof(proof),
            proof,
        )

    def test_portable_verifier_rejects_result_binding_mismatch(self):
        with self.assertRaisesRegex(
            RuntimeError, "AGENT_WRITE_LIFECYCLE_RESULT_BINDING_MISMATCH"
        ):
            self._prove(lifecycle_result(branch="work/operations/other"))

    def test_portable_verifier_rejects_released_or_expired_binding(self):
        with self.assertRaisesRegex(RuntimeError, "AGENT_WRITE_LIFECYCLE_NOT_ACTIVE"):
            self._prove(lifecycle_result(state="RELEASED"))
        with self.assertRaisesRegex(
            RuntimeError, "AGENT_WRITE_LIFECYCLE_BINDING_EXPIRED"
        ):
            self._prove(expired=True)

    def test_portable_verifier_requires_exact_single_authority_lease(self):
        with self.assertRaisesRegex(
            RuntimeError, "AGENT_WRITE_LIFECYCLE_BINDING_AUTHORITY_MISMATCH"
        ):
            self._prove(leases=[])
        with self.assertRaisesRegex(
            RuntimeError, "AGENT_WRITE_LIFECYCLE_BINDING_AUTHORITY_MISMATCH"
        ):
            self._prove(leases=[matching_lease(), matching_lease()])

    def test_legacy_v01_proof_remains_readable(self):
        proof = self._prove()
        legacy = copy.deepcopy(proof)
        legacy["schemaVersion"] = guard.LEGACY_PROOF_SCHEMA
        legacy.pop("lifecycleResultRef")
        legacy["lifecycleResultCommentId"] = 321
        body = {key: value for key, value in legacy.items() if key != "proofHash"}
        legacy["proofHash"] = stable_hash(body)
        self.assertEqual(guard.validate_active_binding_proof(legacy), legacy)

    def test_hosted_adapter_only_discovers_result_and_supplies_provenance(self):
        result = lifecycle_result()
        expected = {"schemaVersion": guard.PROOF_SCHEMA, "proofHash": "0" * 64}
        with (
            patch.object(guard, "_comments", return_value=[{"id": 321, "body": "x"}]),
            patch.object(guard.hosted_cycle_records, "result_comment_allowed", return_value=True),
            patch.object(guard, "_payload", return_value=result),
            patch.object(guard.lifecycle, "validate_result", side_effect=lambda value: value),
            patch.object(guard.hosted_cycle_records, "comment_id", return_value=321),
            patch.object(guard, "prove_binding_result", return_value=expected) as prove,
        ):
            actual = guard.prove_active_binding(
                plan(),
                cycle_instance_id=CYCLE_ID,
                issue_number=145,
                before_comment_id=None,
                transport=object(),
            )
        self.assertEqual(actual, expected)
        kwargs = prove.call_args.kwargs
        self.assertEqual(kwargs["lifecycle_result"], result)
        self.assertEqual(
            kwargs["lifecycle_result_ref"],
            {"kind": "hosted-comment", "value": "321"},
        )

    def test_portable_verifier_source_has_no_hosted_discovery_contract(self):
        source = inspect.getsource(guard.prove_binding_result)
        for forbidden in (
            "issue_number",
            "comment_id",
            "hosted_cycle_records",
            "_comments(",
            "REQUEST_MARKER",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
