from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from tools import agent_failure
from tools import hosted_agent_cycle as hosted
from tools import hosted_cycle_failure_recovery as recovery
from tools import hosted_cycle_frontier
from tools.canonical import stable_hash

FIXTURE_PATH = Path(__file__).with_name("test_hosted_cycle_reentry_r0.py")
SPEC = importlib.util.spec_from_file_location(
    "hosted_cycle_reentry_r0_fixtures_e5d", FIXTURE_PATH
)
fixtures = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(fixtures)


def _failure_for(command: dict) -> dict:
    failure_core = agent_failure.build_failure_core(
        surface="AGENT_CYCLE",
        phase="CLOSE",
        status="BLOCKED",
        causes=[
            {
                "code": "AGENT_WRITE_LIFECYCLE_UNKNOWN_FAILURE_AT_CLOSE",
                "source": "agent-write-lifecycle-guard",
                "phase": "CLOSE",
            },
            {
                "code": "AGENT_WRITE_LIFECYCLE_UNKNOWN_AT_CLOSE",
                "source": "hosted-agent-cycle",
                "phase": "CLOSE",
            },
        ],
        observation_retry="UNKNOWN",
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


def _certificate(
    begin_result: dict,
    close: dict,
    *,
    close_id: int,
    failure_id: int,
    failure: dict,
) -> dict:
    locator = json.loads(
        begin_result["handle"]["resumeToken"][len("hosted-v1:") :]
    )
    core = {
        "schemaVersion": recovery.RESULT_SCHEMA,
        "requestId": "recover-e5d",
        "cycleInstanceId": begin_result["cycleInstanceId"],
        "handleHash": begin_result["handle"]["handleHash"],
        "beginRequestCommentId": locator["beginCommentId"],
        "closeRequestCommentId": close_id,
        "closeCommandHash": hosted.transport_command_hash(close),
        "failedCloseResultCommentId": failure_id,
        "failedCloseFailureHash": failure["failureHash"],
        "writeLifecycleReportHash": "a" * 64,
        "authorityHead": "b" * 40,
        "state": "RECOVERED",
        "reasonCodes": [recovery.RECOVERY_REASON],
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**core, "recoveryHash": stable_hash(core)}


def _bot(marker: str, payload: dict, cid: int) -> dict:
    return {
        "id": cid,
        "author_association": "CONTRIBUTOR",
        "user": {"login": "github-actions[bot]"},
        "body": marker + "\n" + json.dumps(payload),
    }


class HostedCycleRecoveryCertificateTests(unittest.TestCase):
    def test_recovery_certificate_makes_failed_cycle_terminal_without_close_pass(
        self,
    ) -> None:
        begin_req, begin_result_comment, begin_result = fixtures._begin_pair()
        close = fixtures._close_command(begin_result["handle"], "close-e5d")
        close_request = fixtures._owner_comment(
            hosted.REQUEST_MARKER_V02, close, 3001
        )
        failure_payload = _failure_for(close)
        failure_comment = fixtures._bot_comment(failure_payload, 4001)
        cert = _certificate(
            begin_result,
            close,
            close_id=3001,
            failure_id=4001,
            failure=failure_payload,
        )
        result = fixtures._inspect(
            [
                begin_req,
                begin_result_comment,
                close_request,
                failure_comment,
                _bot(recovery.RESULT_MARKER, cert, 5001),
            ]
        )
        self.assertEqual("CLEAN_REENTRY", result["state"])
        self.assertEqual("BEGIN_NEW_CYCLE", result["nextSafeAction"])
        self.assertEqual("RECOVERED", result["cycleOutcomes"][0]["state"])
        self.assertEqual(
            [begin_result["cycleInstanceId"]],
            result["cycleFrontier"]["terminalCycleIds"],
        )
        self.assertEqual([], result["cycleFrontier"]["activeCycleIds"])

    def test_close_failure_without_certificate_still_requires_reconciliation(
        self,
    ) -> None:
        begin_req, begin_result_comment, begin_result = fixtures._begin_pair()
        close = fixtures._close_command(begin_result["handle"], "close-e5d")
        close_request = fixtures._owner_comment(
            hosted.REQUEST_MARKER_V02, close, 3001
        )
        failure = fixtures._bot_comment(_failure_for(close), 4001)
        result = fixtures._inspect(
            [begin_req, begin_result_comment, close_request, failure]
        )
        self.assertEqual("RECONCILE_FAILURE", result["nextSafeAction"])

    def test_certificate_bound_to_other_failure_is_ignored(self) -> None:
        begin_req, begin_result_comment, begin_result = fixtures._begin_pair()
        close = fixtures._close_command(begin_result["handle"], "close-e5d")
        close_request = fixtures._owner_comment(
            hosted.REQUEST_MARKER_V02, close, 3001
        )
        failure_payload = _failure_for(close)
        failure = fixtures._bot_comment(failure_payload, 4001)
        cert = _certificate(
            begin_result,
            close,
            close_id=3001,
            failure_id=4001,
            failure=failure_payload,
        )
        cert["failedCloseFailureHash"] = "f" * 64
        body = {
            k: copy.deepcopy(v)
            for k, v in cert.items()
            if k != "recoveryHash"
        }
        cert["recoveryHash"] = stable_hash(body)
        result = fixtures._inspect(
            [
                begin_req,
                begin_result_comment,
                close_request,
                failure,
                _bot(recovery.RESULT_MARKER, cert, 5001),
            ]
        )
        self.assertEqual("RECONCILE_FAILURE", result["nextSafeAction"])

    def test_frontier_accepts_recovered_as_terminal(self) -> None:
        outcome = {
            "cycleInstanceId": "cycle-instance-" + "1" * 24,
            "beginRequestCommentId": 100,
            "state": "RECOVERED",
            "closeRequestCommentId": 200,
            "resultCommentIds": [300, 400],
            "resultHash": "c" * 64,
            "reasonCodes": [recovery.RECOVERY_REASON],
        }
        frontier = hosted_cycle_frontier.build_frontier([outcome])
        self.assertEqual(
            [outcome["cycleInstanceId"]], frontier["terminalCycleIds"]
        )
        self.assertEqual([], frontier["activeCycleIds"])


class HostedCycleRecoveryProducerTests(unittest.TestCase):
    @patch(
        "tools.hosted_cycle_failure_recovery.agent_write_lifecycle_guard.inspect_cycle"
    )
    @patch("tools.hosted_cycle_failure_recovery.hosted_cycle_handle.bind")
    def test_recover_requires_current_guard_to_prove_released(
        self, bind, inspect
    ) -> None:
        begin_req, begin_result_comment, begin_result = fixtures._begin_pair()
        close = fixtures._close_command(begin_result["handle"], "close-e5d")
        close_request = fixtures._owner_comment(
            hosted.REQUEST_MARKER_V02, close, 3001
        )
        failure_payload = _failure_for(close)
        failure = fixtures._bot_comment(failure_payload, 4001)
        _, locator = recovery.hosted_cycle_handle.decode_handle(
            begin_result["handle"], repository=recovery.REPOSITORY
        )
        bind.return_value = {
            "locator": locator,
            "handle": begin_result["handle"],
            "begin": {},
            "actor": fixtures.ACTOR,
        }
        inspect.return_value = {
            "schemaVersion": recovery.agent_write_lifecycle_guard.REPORT_SCHEMA,
            "cycleInstanceId": begin_result["cycleInstanceId"],
            "actor": copy.deepcopy(fixtures.ACTOR),
            "state": "RELEASED",
            "latestBindingHash": None,
            "authorityHead": "d" * 40,
            "authorityNow": "2026-09-24T14:00:00Z",
            "matchingLeaseIds": [],
            "blockers": [],
            "readOnly": True,
            "semanticAuthority": False,
            "authorizesMutation": False,
            "reportHash": "e" * 64,
        }
        with patch.object(
            recovery.agent_write_lifecycle_guard,
            "validate_report",
            side_effect=lambda value: value,
        ):
            request = {
                "schemaVersion": recovery.REQUEST_SCHEMA,
                "requestId": "recover-e5d",
                "handle": begin_result["handle"],
                "closeRequestCommentId": 3001,
                "semanticAuthority": False,
                "authorizesMutation": False,
            }
            value = recovery.recover(
                request,
                context={},
                manifest={
                    "cycleInstanceId": begin_result["cycleInstanceId"],
                    "actor": copy.deepcopy(fixtures.ACTOR),
                    "source": {
                        "issueNumber": fixtures.ISSUE_NUMBER,
                        "commentId": locator["beginCommentId"],
                    },
                },
                comments=[
                    begin_req,
                    begin_result_comment,
                    close_request,
                    failure,
                ],
                transport=object(),
            )
        self.assertEqual("RECOVERED", value["state"])
        self.assertEqual(
            failure_payload["failureHash"],
            value["failedCloseFailureHash"],
        )

    @patch(
        "tools.hosted_cycle_failure_recovery.agent_write_lifecycle_guard.inspect_cycle"
    )
    @patch("tools.hosted_cycle_failure_recovery.hosted_cycle_handle.bind")
    def test_recover_rejects_non_clean_current_guard(
        self, bind, inspect
    ) -> None:
        begin_req, begin_result_comment, begin_result = fixtures._begin_pair()
        close = fixtures._close_command(begin_result["handle"], "close-e5d")
        close_request = fixtures._owner_comment(
            hosted.REQUEST_MARKER_V02, close, 3001
        )
        failure = fixtures._bot_comment(_failure_for(close), 4001)
        _, locator = recovery.hosted_cycle_handle.decode_handle(
            begin_result["handle"], repository=recovery.REPOSITORY
        )
        bind.return_value = {"locator": locator}
        inspect.return_value = {"state": "UNKNOWN", "blockers": ["STILL_UNKNOWN"]}
        request = {
            "schemaVersion": recovery.REQUEST_SCHEMA,
            "requestId": "recover-e5d",
            "handle": begin_result["handle"],
            "closeRequestCommentId": 3001,
            "semanticAuthority": False,
            "authorizesMutation": False,
        }
        with patch.object(
            recovery.agent_write_lifecycle_guard,
            "validate_report",
            side_effect=lambda value: value,
        ):
            with self.assertRaisesRegex(
                RuntimeError, "RESIDUAL_AUTHORITY_NOT_CLEAN"
            ):
                recovery.recover(
                    request,
                    context={},
                    manifest={
                        "cycleInstanceId": begin_result["cycleInstanceId"],
                        "actor": copy.deepcopy(fixtures.ACTOR),
                        "source": {
                            "issueNumber": fixtures.ISSUE_NUMBER,
                            "commentId": locator["beginCommentId"],
                        },
                    },
                    comments=[
                        begin_req,
                        begin_result_comment,
                        close_request,
                        failure,
                    ],
                    transport=object(),
                )


if __name__ == "__main__":
    unittest.main()
