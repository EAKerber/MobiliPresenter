from __future__ import annotations

import copy
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from tools import agent_write_lifecycle as lifecycle
from tools import agent_write_lifecycle_guard as guard
from tools.canonical import stable_hash


BRANCH = "work/operations/at3c-lifecycle-test"
ACTOR = {
    "role": "manager-gitops",
    "workerId": "manager-gitops-a",
    "sessionId": "session-at3c",
}
BEGIN = {
    "runId": 123,
    "sourceSha": "a" * 40,
    "contextHash": "b" * 64,
}


def request(action: str, *, binding_hash: str | None = None) -> dict:
    return {
        "schemaVersion": lifecycle.REQUEST_SCHEMA,
        "requestId": f"request-{action}",
        "action": action,
        "begin": copy.deepcopy(BEGIN),
        "actor": copy.deepcopy(ACTOR),
        "branch": BRANCH,
        "expectedAuthorityHead": "c" * 40,
        "expectedBranchHead": "d" * 40,
        "expectedBindingHash": binding_hash,
        "ttlSeconds": 3600 if action == "acquire" else None,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


def binding(*, state: str = "ACTIVE", lease_id: str = "lease-at3c", previous: str | None = None) -> dict:
    core = {
        "schemaVersion": lifecycle.BINDING_SCHEMA,
        "cycleInstanceId": "cycle-instance-" + "1" * 24,
        "begin": copy.deepcopy(BEGIN),
        "actor": copy.deepcopy(ACTOR),
        "branch": BRANCH,
        "state": state,
        "leaseId": lease_id,
        "expiresAt": "2026-08-26T06:00:00Z" if state == "ACTIVE" else None,
        "previousBindingHash": previous,
        "authorityHead": "e" * 40,
        "dispatchHash": "f" * 64,
        "receiptHash": "0" * 64,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**core, "bindingHash": stable_hash(core)}


def lease(lease_id: str, resource: str, *, session: str = "session-at3c") -> dict:
    return {
        "leaseId": lease_id,
        "resource": resource,
        "mode": "exclusive-write",
        "owner": {
            "role": "manager-gitops",
            "session": session,
            "branch": BRANCH,
            "pr": None,
        },
        "reason": "test",
        "acquiredAt": "2026-08-26T03:00:00Z",
        "renewedAt": "2026-08-26T03:00:00Z",
        "expiresAt": "2026-08-26T06:00:00Z",
        "ttlSeconds": 3600,
    }


class AgentWriteLifecycleIdentityTests(unittest.TestCase):
    def test_acquire_requires_no_prior_binding_and_followups_require_exact_binding_hash(self) -> None:
        self.assertEqual("acquire", lifecycle.validate_request(request("acquire"))["action"])

        bad_acquire = request("acquire", binding_hash="1" * 64)
        with self.assertRaisesRegex(RuntimeError, "AGENT_WRITE_LIFECYCLE_PRIOR_BINDING_FORBIDDEN"):
            lifecycle.validate_request(bad_acquire)

        for action in ("renew", "release"):
            with self.assertRaisesRegex(RuntimeError, "AGENT_WRITE_LIFECYCLE_PRIOR_BINDING_REQUIRED"):
                lifecycle.validate_request(request(action))
            value = request(action, binding_hash="2" * 64)
            self.assertEqual("2" * 64, lifecycle.validate_request(value)["expectedBindingHash"])

    def test_released_binding_preserves_lease_identity_and_lineage(self) -> None:
        value = binding(state="RELEASED", lease_id="lease-at3c", previous="3" * 64)
        validated = lifecycle.validate_binding(value)
        self.assertEqual("RELEASED", validated["state"])
        self.assertEqual("lease-at3c", validated["leaseId"])
        self.assertEqual("3" * 64, validated["previousBindingHash"])

        tampered = copy.deepcopy(value)
        tampered["leaseId"] = None
        with self.assertRaisesRegex(RuntimeError, "AGENT_WRITE_LIFECYCLE_BINDING_INVALID"):
            lifecycle.validate_binding(tampered)

    def test_exact_guard_match_ignores_unrelated_same_session_lease(self) -> None:
        current = binding()
        exact = lease("lease-at3c", f"branch:{BRANCH}")
        unrelated = lease("lease-unrelated", "branch:work/operations/other")
        matches = guard._matching_exact_leases([exact, unrelated], binding=current)
        self.assertEqual(["lease-at3c"], [item["leaseId"] for item in matches])

    def test_release_preparation_accepts_unrelated_same_session_lease_but_renew_blocks(self) -> None:
        current = binding()
        exact = lease("lease-at3c", f"branch:{BRANCH}")
        unrelated = lease("lease-unrelated", "branch:work/operations/other")
        observation = SimpleNamespace(
            state={
                "schemaVersion": "CoordinationState 0.1",
                "revision": None,
                "intents": [],
                "leases": [exact, unrelated],
            },
            authority_now=datetime(2026, 8, 26, 4, 0, tzinfo=timezone.utc),
        )
        manifest = {"cycleInstanceId": current["cycleInstanceId"]}

        with patch.object(lifecycle, "_latest_binding_before", return_value=current):
            release_request = request("release", binding_hash=current["bindingHash"])
            previous, bound = lifecycle._prepare_previous_binding(
                release_request,
                manifest,
                observation,
                issue_number=145,
                request_comment_id=999,
                transport=object(),
            )
            self.assertEqual(current["bindingHash"], previous["bindingHash"])
            self.assertEqual("lease-at3c", bound["leaseId"])

            renew_request = request("renew", binding_hash=current["bindingHash"])
            with self.assertRaisesRegex(RuntimeError, "AGENT_WRITE_LIFECYCLE_RENEW_SCOPE_AMBIGUOUS"):
                lifecycle._prepare_previous_binding(
                    renew_request,
                    manifest,
                    observation,
                    issue_number=145,
                    request_comment_id=1000,
                    transport=object(),
                )

    def test_wrong_binding_hash_cannot_borrow_exact_lease(self) -> None:
        current = binding()
        exact = lease("lease-at3c", f"branch:{BRANCH}")
        observation = SimpleNamespace(
            state={
                "schemaVersion": "CoordinationState 0.1",
                "revision": None,
                "intents": [],
                "leases": [exact],
            },
            authority_now=datetime(2026, 8, 26, 4, 0, tzinfo=timezone.utc),
        )
        manifest = {"cycleInstanceId": current["cycleInstanceId"]}
        with patch.object(lifecycle, "_latest_binding_before", return_value=current):
            value = request("release", binding_hash="9" * 64)
            with self.assertRaisesRegex(RuntimeError, "AGENT_WRITE_LIFECYCLE_BINDING_DRIFT"):
                lifecycle._prepare_previous_binding(
                    value,
                    manifest,
                    observation,
                    issue_number=145,
                    request_comment_id=1001,
                    transport=object(),
                )


if __name__ == "__main__":
    unittest.main()
