from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
import unittest
from unittest import mock

from tools import agent_write_lifecycle_guard as guard


class BlockedWriteLeaseTerminalCloseTests(unittest.TestCase):
    def _inspect(self, *, failure_status: str | None) -> dict:
        request_hash = "f" * 64
        request = {
            "branch": "work/operations/r6-black-box-live-canary",
        }
        records = [
            {
                "kind": "write-lease-request",
                "commentId": 10,
                "binding": "STRONG",
                "normalized": request,
            }
        ]
        if failure_status is not None:
            records.append(
                {
                    "kind": "write-lease-failure",
                    "commentId": 11,
                    "binding": "STRONG",
                    "normalized": {
                        "requestHash": request_hash,
                        "status": failure_status,
                        "blockers": ["HOSTED_AGENT_WRITE_LEASE_PREPARE_FAILED"],
                        "branch": request["branch"],
                    },
                }
            )
        view = {
            "cycleInstanceId": "cycle-instance-" + "a" * 24,
            "records": records,
        }
        observation = SimpleNamespace(
            state={},
            authority_now=datetime(2026, 9, 19, tzinfo=timezone.utc),
            head_sha="b" * 40,
        )
        authority = mock.Mock()
        authority.observe.return_value = observation
        manifest = {
            "actor": {
                "role": "manager-gitops",
                "workerId": "manager-gitops-chat",
                "sessionId": "r6g-close-regression",
            }
        }

        with (
            mock.patch.object(
                guard.hosted_cycle_records,
                "collect",
                return_value=view,
            ),
            mock.patch.object(
                guard.lifecycle,
                "request_hash",
                return_value=request_hash,
            ),
            mock.patch.object(
                guard,
                "GitHubCoordinationAuthority",
                return_value=authority,
            ),
            mock.patch.object(
                guard.coordination,
                "active_leases",
                return_value=[],
            ),
        ):
            return guard.inspect_cycle(
                [],
                manifest,
                close_comment_id=99,
                transport=object(),
            )

    def test_blocked_failure_is_terminal_non_mutation(self) -> None:
        report = self._inspect(failure_status="BLOCKED")
        self.assertEqual(report["state"], "NONE")
        self.assertEqual(report["blockers"], [])
        self.assertIsNone(report["latestBindingHash"])

    def test_unknown_failure_remains_fail_closed(self) -> None:
        report = self._inspect(failure_status="UNKNOWN")
        self.assertEqual(report["state"], "UNKNOWN")
        self.assertEqual(
            report["blockers"],
            ["AGENT_WRITE_LIFECYCLE_UNKNOWN_FAILURE_AT_CLOSE"],
        )

    def test_request_without_terminal_remains_unknown(self) -> None:
        report = self._inspect(failure_status=None)
        self.assertEqual(report["state"], "UNKNOWN")
        self.assertEqual(
            report["blockers"],
            ["AGENT_WRITE_LIFECYCLE_REQUEST_WITHOUT_TERMINAL"],
        )


if __name__ == "__main__":
    unittest.main()
