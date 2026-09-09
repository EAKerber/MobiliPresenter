from __future__ import annotations

import copy
import json
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from tools import agent_write_lifecycle_guard as guard


BRANCH = "work/operations/migration-close-test"
ACTOR = {
    "role": "manager-gitops",
    "workerId": "manager-gitops-chat",
    "sessionId": "migration-close-test-session",
}
SOURCE_SHA = "a" * 40


def manifest() -> dict:
    return {
        "source": {
            "runId": 123,
            "sourceSha": SOURCE_SHA,
            "issueNumber": 145,
            "commentId": 1,
        },
        "contextHash": "b" * 64,
        "actor": copy.deepcopy(ACTOR),
        "cycleInstanceId": "cycle-instance-" + "1" * 24,
    }


def binding() -> dict:
    return {
        "schemaVersion": "AgentWriteLeaseBinding 0.1",
        "cycleInstanceId": "cycle-instance-" + "1" * 24,
        "begin": {
            "runId": 123,
            "sourceSha": SOURCE_SHA,
            "contextHash": "b" * 64,
        },
        "actor": copy.deepcopy(ACTOR),
        "branch": BRANCH,
        "state": "ACTIVE",
        "leaseId": "lease-migration-close",
        "expiresAt": "2026-09-09T23:00:00Z",
        "previousBindingHash": None,
        "authorityHead": "c" * 40,
        "dispatchHash": "d" * 64,
        "receiptHash": "e" * 64,
        "semanticAuthority": False,
        "authorizesMutation": False,
        "bindingHash": "f" * 64,
    }


def expected_owner() -> dict:
    return {
        "role": ACTOR["role"],
        "session": ACTOR["sessionId"],
        "branch": BRANCH,
        "pr": None,
    }


def migration_receipt() -> dict:
    execution_id = "migration-release-test"
    owner = expected_owner()
    resource = f"branch:{BRANCH}"
    authority_revision = "1" * 40
    return {
        "schemaVersion": "RemoteCanonicalExecutionReceipt 0.1",
        "executionId": execution_id,
        "command": {
            "schemaVersion": "RemoteCanonicalCommand 0.1",
            "executionId": execution_id,
            "kind": "domain",
            "actor": copy.deepcopy(ACTOR),
            "declaredIntent": {
                "intent": guard.MIGRATION_RELEASE_INTENT,
                "sourceSemanticHost": SOURCE_SHA,
                "reason": "Finalize the exact historical lease through canonical Coordination.",
            },
            "target": {
                "domain": "coordination",
                "action": "release",
                "subject": {"kind": "coordination", "id": "leases"},
            },
            "expected": {"authorityRevision": "0" * 40},
            "payload": {
                "owner": copy.deepcopy(owner),
                "transitionId": execution_id,
                "resources": [resource],
                "mine": False,
            },
            "semanticAuthority": False,
            "authorizesMutation": False,
        },
        "commandHash": "2" * 64,
        "route": {
            "kind": "domain",
            "domain": "coordination",
            "action": "release",
        },
        "source": {
            "workflow": "remote-canonical-execution",
            "sourceSha": "3" * 40,
            "runId": "456",
            "issueNumber": 145,
            "commentId": 20,
        },
        "planHash": "4" * 64,
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
                    "owner": copy.deepcopy(owner),
                    "resources": [resource],
                    "mine": False,
                },
                "candidate": {
                    "schemaVersion": "CoordinationState 0.1",
                    "revision": "0" * 40,
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
        "receiptHash": "5" * 64,
    }


def bot_comment(comment_id: int, marker: str, payload: dict) -> dict:
    return {
        "id": comment_id,
        "user": {"login": "github-actions[bot]"},
        "author_association": "CONTRIBUTOR",
        "body": marker + "\n```json\n" + json.dumps(payload) + "\n```",
    }


def boundary_comment(comment_id: int) -> dict:
    return {
        "id": comment_id,
        "user": {"login": "EAKerber"},
        "author_association": "OWNER",
        "body": "boundary",
    }


def observation(leases: list[dict]) -> SimpleNamespace:
    return SimpleNamespace(
        state={
            "schemaVersion": "CoordinationState 0.1",
            "revision": None,
            "intents": [],
            "leases": copy.deepcopy(leases),
        },
        authority_now=datetime(2026, 9, 9, 21, 0, tzinfo=timezone.utc),
        head_sha="6" * 40,
    )


class FakeAuthority:
    def __init__(self, value: SimpleNamespace):
        self.value = value

    def observe(self) -> SimpleNamespace:
        return self.value


class MigrationReleaseReceiptTests(unittest.TestCase):
    @patch("tools.agent_write_lifecycle_guard.remote_canonical_execution.validate_receipt")
    def test_exact_canonical_migration_release_matches(self, validate_receipt) -> None:
        value = migration_receipt()
        self.assertTrue(
            guard._migration_release_receipt_matches(
                value, manifest=manifest(), binding=binding()
            )
        )
        validate_receipt.assert_called_once_with(value)

    @patch("tools.agent_write_lifecycle_guard.remote_canonical_execution.validate_receipt")
    def test_identity_or_scope_drift_is_rejected(self, validate_receipt) -> None:
        cases = []

        wrong_actor = migration_receipt()
        wrong_actor["command"]["actor"]["sessionId"] = "other-session"
        cases.append(wrong_actor)

        wrong_host = migration_receipt()
        wrong_host["command"]["declaredIntent"]["sourceSemanticHost"] = "9" * 40
        cases.append(wrong_host)

        wrong_owner = migration_receipt()
        wrong_owner["command"]["payload"]["owner"]["branch"] = "work/operations/other"
        cases.append(wrong_owner)

        wrong_resource = migration_receipt()
        wrong_resource["command"]["payload"]["resources"] = ["branch:work/operations/other"]
        cases.append(wrong_resource)

        for value in cases:
            with self.subTest(value=value["command"]):
                self.assertFalse(
                    guard._migration_release_receipt_matches(
                        value, manifest=manifest(), binding=binding()
                    )
                )

        self.assertEqual(len(cases), validate_receipt.call_count)

    @patch("tools.agent_write_lifecycle_guard.remote_canonical_execution.validate_receipt")
    def test_candidate_that_still_contains_exact_lease_is_rejected(self, validate_receipt) -> None:
        value = migration_receipt()
        current = binding()
        value["evidence"]["plan"]["candidate"]["leases"] = [
            {
                "leaseId": current["leaseId"],
                "resource": f"branch:{current['branch']}",
                "owner": expected_owner(),
            }
        ]
        self.assertFalse(
            guard._migration_release_receipt_matches(
                value, manifest=manifest(), binding=current
            )
        )

    @patch(
        "tools.agent_write_lifecycle_guard.remote_canonical_execution.validate_receipt",
        side_effect=RuntimeError("REMOTE_RECEIPT_INVALID"),
    )
    def test_invalid_remote_receipt_is_rejected(self, validate_receipt) -> None:
        self.assertFalse(
            guard._migration_release_receipt_matches(
                migration_receipt(), manifest=manifest(), binding=binding()
            )
        )


class MigrationReleaseWindowTests(unittest.TestCase):
    @patch(
        "tools.agent_write_lifecycle_guard._migration_release_receipt_matches",
        return_value=True,
    )
    def test_receipt_after_latest_lifecycle_result_is_proven(self, matches) -> None:
        comments = [
            boundary_comment(1),
            bot_comment(10, "MOBILIPRESENTER_AGENT_WRITE_LEASE_RESULT_V0_1", {}),
            bot_comment(20, guard.REMOTE_RESULT_MARKER, migration_receipt()),
            boundary_comment(30),
        ]
        self.assertTrue(
            guard._migration_release_proven(
                comments,
                manifest(),
                close_comment_id=30,
                latest_result_comment_id=10,
                binding=binding(),
            )
        )
        matches.assert_called_once()

    @patch(
        "tools.agent_write_lifecycle_guard._migration_release_receipt_matches",
        return_value=True,
    )
    def test_receipt_before_latest_lifecycle_result_is_ignored(self, matches) -> None:
        comments = [
            boundary_comment(1),
            bot_comment(5, guard.REMOTE_RESULT_MARKER, migration_receipt()),
            bot_comment(10, "MOBILIPRESENTER_AGENT_WRITE_LEASE_RESULT_V0_1", {}),
            boundary_comment(30),
        ]
        self.assertFalse(
            guard._migration_release_proven(
                comments,
                manifest(),
                close_comment_id=30,
                latest_result_comment_id=10,
                binding=binding(),
            )
        )
        matches.assert_not_called()


class MigrationReleaseCloseStateTests(unittest.TestCase):
    @patch("tools.agent_write_lifecycle_guard._migration_release_proven", return_value=True)
    @patch("tools.agent_write_lifecycle_guard.hosted_cycle_records.collect", return_value={})
    def test_absent_exact_lease_with_proven_migration_is_released(self, collect, proven) -> None:
        current = binding()
        with (
            patch.object(guard, "_bound_results", return_value=[(10, {"binding": current})]),
            patch.object(guard, "_request_count", return_value=1),
            patch.object(guard, "_bound_agent_tool_branches", return_value={BRANCH}),
            patch.object(
                guard,
                "GitHubCoordinationAuthority",
                return_value=FakeAuthority(observation([])),
            ),
        ):
            report = guard.inspect_cycle(
                [boundary_comment(1), boundary_comment(30)],
                manifest(),
                close_comment_id=30,
                transport=object(),
            )
        self.assertEqual("RELEASED", report["state"])
        self.assertEqual([], report["blockers"])
        proven.assert_called_once()

    @patch("tools.agent_write_lifecycle_guard._migration_release_proven", return_value=True)
    @patch("tools.agent_write_lifecycle_guard.hosted_cycle_records.collect", return_value={})
    def test_materialized_exact_lease_cannot_be_overridden_by_migration_receipt(
        self, collect, proven
    ) -> None:
        current = binding()
        exact = {
            "leaseId": current["leaseId"],
            "resource": f"branch:{BRANCH}",
            "owner": expected_owner(),
        }
        with (
            patch.object(guard, "_bound_results", return_value=[(10, {"binding": current})]),
            patch.object(guard, "_request_count", return_value=1),
            patch.object(guard, "_bound_agent_tool_branches", return_value={BRANCH}),
            patch.object(
                guard,
                "GitHubCoordinationAuthority",
                return_value=FakeAuthority(observation([exact])),
            ),
        ):
            report = guard.inspect_cycle(
                [boundary_comment(1), boundary_comment(30)],
                manifest(),
                close_comment_id=30,
                transport=object(),
            )
        self.assertEqual("ACTIVE", report["state"])
        self.assertIn("AGENT_WRITE_LIFECYCLE_ACTIVE_AT_CLOSE", report["blockers"])
        proven.assert_not_called()


if __name__ == "__main__":
    unittest.main()
