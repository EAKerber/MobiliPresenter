from __future__ import annotations

import copy
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from tools import agent_write_lifecycle as lifecycle
from tools import agent_write_lifecycle_guard as guard


BRANCH = "work/operations/e5c-unknown-cleanup"
ACTOR = {
    "role": "manager-gitops",
    "workerId": "manager-gitops-chat",
    "sessionId": "e5c-session",
}
REQUEST_HASH = "1" * 64
CYCLE = "cycle-instance-" + "2" * 24


def manifest() -> dict:
    return {
        "source": {
            "runId": 123,
            "sourceSha": "a" * 40,
            "issueNumber": 145,
            "commentId": 100,
        },
        "contextHash": "b" * 64,
        "actor": copy.deepcopy(ACTOR),
        "cycleInstanceId": CYCLE,
    }


def request() -> dict:
    return {
        "schemaVersion": lifecycle.REQUEST_SCHEMA,
        "requestId": "e5c-acquire",
        "action": "acquire",
        "begin": {
            "runId": 123,
            "sourceSha": "a" * 40,
            "contextHash": "b" * 64,
        },
        "actor": copy.deepcopy(ACTOR),
        "branch": BRANCH,
        "expectedAuthorityHead": "c" * 40,
        "expectedBranchHead": "d" * 40,
        "expectedBindingHash": None,
        "ttlSeconds": 3600,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


def failure() -> dict:
    return {
        "requestHash": REQUEST_HASH,
        "status": "UNKNOWN",
    }


def owner() -> dict:
    return {
        "role": ACTOR["role"],
        "session": ACTOR["sessionId"],
        "branch": BRANCH,
        "pr": None,
    }


def release_receipt() -> dict:
    execution_id = "e5c-cleanup-release"
    authority_revision = "e" * 40
    resource = f"branch:{BRANCH}"
    return {
        "schemaVersion": guard.remote_canonical_execution.RECEIPT_SCHEMA,
        "executionId": execution_id,
        "command": {
            "schemaVersion": "RemoteCanonicalCommand 0.1",
            "executionId": execution_id,
            "kind": "domain",
            "actor": copy.deepcopy(ACTOR),
            "declaredIntent": {
                "goal": "Neutralize residual ownership after an UNKNOWN acquire."
            },
            "target": {
                "domain": "coordination",
                "action": "release",
                "subject": {"kind": "coordination", "id": "leases"},
            },
            "expected": {"authorityRevision": "f" * 40},
            "payload": {
                "owner": owner(),
                "transitionId": execution_id,
                "resources": [resource],
                "mine": False,
            },
            "semanticAuthority": False,
            "authorizesMutation": False,
        },
        "commandHash": "3" * 64,
        "route": {
            "kind": "domain",
            "domain": "coordination",
            "action": "release",
        },
        "source": guard.remote_canonical_execution.build_hosted_comment_source(
            host="remote-canonical-execution",
            source_sha="4" * 40,
            invocation_id="456",
            issue_number=145,
            comment_id=130,
        ),
        "planHash": "5" * 64,
        "evidence": {
            "kind": "transition-receipt",
            "request": {},
            "plan": {
                "schemaVersion": "TransitionPlan 0.1",
                "domain": "coordination",
                "action": "release",
                "subject": {"kind": "coordination", "id": "leases"},
                "intent": {
                    "transitionId": execution_id,
                    "owner": owner(),
                    "resources": [resource],
                    "mine": False,
                },
                "candidate": {
                    "schemaVersion": "CoordinationState 0.1",
                    "revision": "f" * 40,
                    "intents": [],
                    "leases": [],
                },
            },
            "receipt": {
                "schemaVersion": "TransitionReceipt 0.1",
                "domain": "coordination",
                "action": "release",
                "subject": {"kind": "coordination", "id": "leases"},
                "authorityRevision": authority_revision,
                "verified": True,
            },
        },
        "aggregateReadback": {
            "kind": "authority-state",
            "authorityRevision": authority_revision,
            "status": "PASS",
        },
        "status": "PASS",
        "blockers": [],
        "semanticAuthority": False,
        "authorizesMutation": False,
        "receiptHash": "6" * 64,
    }


def observation(leases: list[dict]) -> SimpleNamespace:
    return SimpleNamespace(
        state={
            "schemaVersion": "CoordinationState 0.1",
            "revision": None,
            "intents": [],
            "leases": copy.deepcopy(leases),
        },
        authority_now=datetime(2026, 9, 24, 14, 0, tzinfo=timezone.utc),
        head_sha="7" * 40,
    )


class FakeAuthority:
    def __init__(self, value: SimpleNamespace):
        self.value = value

    def observe(self) -> SimpleNamespace:
        return self.value


class UnknownAcquireCleanupReceiptTests(unittest.TestCase):
    @patch(
        "tools.agent_write_lifecycle_guard.remote_canonical_execution.validate_receipt"
    )
    def test_exact_cleanup_receipt_matches(self, validate_receipt) -> None:
        self.assertTrue(
            guard._unknown_acquire_cleanup_receipt_matches(
                release_receipt(),
                manifest=manifest(),
                request=request(),
            )
        )
        validate_receipt.assert_called_once()

    @patch(
        "tools.agent_write_lifecycle_guard.remote_canonical_execution.validate_receipt"
    )
    def test_wrong_owner_or_live_candidate_is_rejected(
        self, validate_receipt
    ) -> None:
        wrong_owner = release_receipt()
        wrong_owner["command"]["payload"]["owner"]["session"] = "other"

        live_candidate = release_receipt()
        live_candidate["evidence"]["plan"]["candidate"]["leases"] = [
            {
                "leaseId": "lease-live",
                "resource": f"branch:{BRANCH}",
                "owner": owner(),
            }
        ]

        self.assertFalse(
            guard._unknown_acquire_cleanup_receipt_matches(
                wrong_owner, manifest=manifest(), request=request()
            )
        )
        self.assertFalse(
            guard._unknown_acquire_cleanup_receipt_matches(
                live_candidate, manifest=manifest(), request=request()
            )
        )


class UnknownAcquireCleanupCloseTests(unittest.TestCase):
    def _inspect(self, *, cleanup: bool, leases: list[dict]) -> dict:
        view = {"cycleInstanceId": CYCLE}
        with (
            patch.object(
                guard.hosted_cycle_records,
                "collect",
                return_value=view,
            ),
            patch.object(guard, "_bound_results", return_value=[]),
            patch.object(
                guard,
                "_bound_requests",
                return_value=[(110, request())],
            ),
            patch.object(
                guard,
                "_bound_failures",
                return_value=[(120, failure())],
            ),
            patch.object(
                guard.lifecycle,
                "request_hash",
                return_value=REQUEST_HASH,
            ),
            patch.object(
                guard,
                "_bound_agent_tool_branches",
                return_value={BRANCH},
            ),
            patch.object(
                guard,
                "_unknown_acquire_cleanup_proven",
                return_value=cleanup,
            ) as proven,
            patch.object(
                guard,
                "GitHubCoordinationAuthority",
                return_value=FakeAuthority(observation(leases)),
            ),
        ):
            report = guard.inspect_cycle(
                [],
                manifest(),
                close_comment_id=200,
                transport=object(),
            )
        if cleanup and not leases:
            proven.assert_called_once()
        return report

    def test_unknown_acquire_with_exact_cleanup_and_clean_authority_is_released(
        self,
    ) -> None:
        report = self._inspect(cleanup=True, leases=[])
        self.assertEqual(report["state"], "RELEASED")
        self.assertEqual(report["blockers"], [])

    def test_unknown_acquire_without_cleanup_remains_unknown(self) -> None:
        report = self._inspect(cleanup=False, leases=[])
        self.assertEqual(report["state"], "UNKNOWN")
        self.assertIn(
            "AGENT_WRITE_LIFECYCLE_UNKNOWN_FAILURE_AT_CLOSE",
            report["blockers"],
        )

    def test_cleanup_cannot_override_still_active_owner_lease(self) -> None:
        report = self._inspect(
            cleanup=True,
            leases=[
                {
                    "leaseId": "lease-live",
                    "resource": f"branch:{BRANCH}",
                    "owner": owner(),
                }
            ],
        )
        self.assertEqual(report["state"], "UNKNOWN")
        self.assertIn(
            "AGENT_WRITE_LIFECYCLE_UNKNOWN_FAILURE_AT_CLOSE",
            report["blockers"],
        )


if __name__ == "__main__":
    unittest.main()
