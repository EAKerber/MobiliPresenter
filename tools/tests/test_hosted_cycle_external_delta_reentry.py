from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest

from tools import agent_failure
from tools import hosted_agent_cycle as hosted
from tools import hosted_cycle_failure_recovery as recovery
from tools.canonical import stable_hash

FIXTURE_PATH = Path(__file__).with_name("test_hosted_cycle_reentry_r0.py")
SPEC = importlib.util.spec_from_file_location(
    "hosted_cycle_reentry_r0_fixtures_e5g", FIXTURE_PATH
)
fixtures = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(fixtures)


def _external_failure(command: dict) -> dict:
    failure_core = agent_failure.build_failure_core(
        surface="AGENT_CYCLE",
        phase="CLOSE",
        status="UNKNOWN",
        causes=[
            {
                "code": "UNATTRIBUTED_DURABLE_DELTA",
                "source": "agent-cycle-close",
                "phase": "CLOSE",
            },
            {
                "code": "HOSTED_AGENT_CLOSE_NOT_PASS",
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


def _certificate(begin_result: dict, close: dict, failure: dict) -> dict:
    locator = json.loads(
        begin_result["handle"]["resumeToken"][len("hosted-v1:") :]
    )
    core = {
        "schemaVersion": recovery.RESULT_SCHEMA_V02,
        "requestId": "recover-external-e5g",
        "cycleInstanceId": begin_result["cycleInstanceId"],
        "handleHash": begin_result["handle"]["handleHash"],
        "beginRequestCommentId": locator["beginCommentId"],
        "closeRequestCommentId": 3001,
        "closeCommandHash": hosted.transport_command_hash(close),
        "failedCloseResultCommentId": 4001,
        "failedCloseFailureHash": failure["failureHash"],
        "writeLifecycleReportHash": "a" * 64,
        "authorityHead": "b" * 40,
        "state": "RECOVERED",
        "reasonCodes": [recovery.EXTERNAL_RECOVERY_REASON],
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
        "failedCloseRunId": 12345,
        "failedCloseClosureHash": "c" * 64,
        "failedCloseReceiptHash": "d" * 64,
        "nonInterferenceEvidenceHash": "e" * 64,
        "reconciledClosureHash": "f" * 64,
        "reconciledReceiptHash": "1" * 64,
    }
    return {**core, "recoveryHash": stable_hash(core)}


def _bot(marker: str, payload: dict, cid: int) -> dict:
    return {
        "id": cid,
        "author_association": "CONTRIBUTOR",
        "user": {"login": "github-actions[bot]"},
        "body": marker + "\n" + json.dumps(payload),
    }


class HostedCycleExternalDeltaReentryTests(unittest.TestCase):
    def test_v02_certificate_terminalizes_failure_as_recovered_not_pass(self):
        begin_req, begin_result_comment, begin_result = fixtures._begin_pair()
        close = fixtures._close_command(begin_result["handle"], "close-e5g")
        close_request = fixtures._owner_comment(
            hosted.REQUEST_MARKER_V02, close, 3001
        )
        failure = _external_failure(close)
        cert = recovery.validate_certificate(
            _certificate(begin_result, close, failure)
        )
        result = fixtures._inspect(
            [
                begin_req,
                begin_result_comment,
                close_request,
                fixtures._bot_comment(failure, 4001),
                _bot(recovery.RESULT_MARKER, cert, 5001),
            ]
        )
        self.assertEqual("CLEAN_REENTRY", result["state"])
        self.assertEqual("BEGIN_NEW_CYCLE", result["nextSafeAction"])
        outcome = result["cycleOutcomes"][0]
        self.assertEqual("RECOVERED", outcome["state"])
        self.assertEqual(
            [recovery.EXTERNAL_RECOVERY_REASON], outcome["reasonCodes"]
        )
        self.assertNotEqual("PASS", outcome["state"])


if __name__ == "__main__":
    unittest.main()
