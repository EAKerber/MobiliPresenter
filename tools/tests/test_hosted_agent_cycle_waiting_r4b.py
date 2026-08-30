from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import agent_failure
from tools import agent_write_lifecycle_guard
from tools import hosted_agent_cycle
from tools import hosted_agent_cycle_trace
from tools import hosted_agent_cycle_waiting
from tools.canonical import stable_hash


ACTOR = {
    "role": "manager-gitops",
    "workerId": "manager-gitops-a",
    "sessionId": "r4b-test-session",
}
SOURCE = {
    "workflow": "hosted-agent-cycle",
    "sourceSha": "a" * 40,
    "runId": 123,
    "issueNumber": 145,
    "commentId": 100,
}
CONTEXT_HASH = "b" * 64
BEGIN = {
    "runId": SOURCE["runId"],
    "sourceSha": SOURCE["sourceSha"],
    "contextHash": CONTEXT_HASH,
}


def close_command() -> dict:
    return {
        "schemaVersion": hosted_agent_cycle.COMMAND_SCHEMA,
        "requestId": "r4b-close",
        "action": "close",
        "actor": copy.deepcopy(ACTOR),
        "declaredIntent": "inspect-and-plan",
        "machineScope": "live",
        "begin": copy.deepcopy(BEGIN),
        "evidenceCommentIds": [],
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


def manifest() -> dict:
    core = {
        "schemaVersion": hosted_agent_cycle.BEGIN_MANIFEST_SCHEMA,
        "requestId": "r4b-begin",
        "commandHash": stable_hash(close_command()),
        "actor": copy.deepcopy(ACTOR),
        "declaredIntent": "inspect-and-plan",
        "machineScope": "live",
        "source": copy.deepcopy(SOURCE),
        "artifactName": f"agent-cycle-begin-{SOURCE['runId']}",
        "cycleId": "cycle-r4b-test",
        "cycleInstanceId": hosted_agent_cycle._cycle_instance_id(
            SOURCE, ACTOR, CONTEXT_HASH
        ),
        "contextHash": CONTEXT_HASH,
        "carrierFeatures": copy.deepcopy(hosted_agent_cycle.CURRENT_FEATURES),
        "status": "READY",
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return hosted_agent_cycle.validate_begin_manifest(
        {**core, "manifestHash": stable_hash(core)}
    )


def failure(*codes: str) -> dict:
    core = agent_failure.build_failure_core(
        surface="AGENT_CYCLE",
        phase="CLOSE",
        status="BLOCKED",
        causes=[
            {"code": code, "source": "hosted-agent-cycle-trace", "phase": "CLOSE"}
            for code in codes
        ],
        observation_retry="UNKNOWN",
        operation_replay="NOT_APPLICABLE",
        mutation_state="NOT_APPLICABLE",
        lossy_projection=False,
    )
    body = {
        "schemaVersion": agent_failure.HOSTED_CYCLE_FAILURE_SCHEMA,
        "requestId": "r4b-close",
        "commandHash": stable_hash(close_command()),
        "status": "BLOCKED",
        "failureCore": core,
    }
    return agent_failure.validate_hosted_cycle_failure(
        {**body, "failureHash": stable_hash(body)}
    )


def lifecycle_report(blockers: list[str], *, state: str = "UNKNOWN") -> dict:
    core = {
        "schemaVersion": agent_write_lifecycle_guard.REPORT_SCHEMA,
        "cycleInstanceId": manifest()["cycleInstanceId"],
        "actor": copy.deepcopy(ACTOR),
        "state": state,
        "latestBindingHash": None,
        "authorityHead": "c" * 40,
        "authorityNow": "2026-08-30T00:00:00Z",
        "matchingLeaseIds": [],
        "blockers": sorted(set(blockers)),
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return agent_write_lifecycle_guard.validate_report(
        {**core, "reportHash": stable_hash(core)}
    )


class HostedAgentCycleWaitingR4BTests(unittest.TestCase):
    def test_trace_incomplete_derives_exact_waiting_target(self):
        trace = {
            "traceStatus": "INCOMPLETE",
            "attempts": [
                {"matched": False, "kind": "agent-tool"},
                {"matched": True, "kind": "remote-canonical"},
            ],
        }
        with patch.object(
            hosted_agent_cycle_waiting.trace_collect,
            "fetch_issue_comments",
            return_value=[],
        ), patch.object(
            hosted_agent_cycle_waiting.trace_collect,
            "build_trace",
            return_value=trace,
        ):
            observed = hosted_agent_cycle_waiting.classify_waiting(
                failure(
                    "EXECUTION_TRACE_INCOMPLETE",
                    "HOSTED_AGENT_EXECUTION_TRACE_INCOMPLETE",
                ),
                meta={"commentId": 200},
                manifest=manifest(),
                output_path="/tmp/closure.json",
            )
        self.assertEqual(observed, ["AGENT_TOOL_RESULT"])

    def test_remote_receipt_gap_waits_for_remote_result(self):
        observed = hosted_agent_cycle_waiting.classify_waiting(
            failure(hosted_agent_cycle_trace.MUTATION_RECEIPT_MISSING),
            meta={"commentId": 200},
            manifest=manifest(),
            output_path="/tmp/closure.json",
        )
        self.assertEqual(observed, ["REMOTE_CANONICAL_RESULT"])

    def test_write_lease_request_without_terminal_waits_for_lease_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            closure = Path(tmp) / "closure.json"
            closure.with_name("agent-write-lifecycle-close.json").write_text(
                json.dumps(
                    lifecycle_report(["AGENT_WRITE_LIFECYCLE_REQUEST_WITHOUT_TERMINAL"])
                ),
                encoding="utf-8",
            )
            observed = hosted_agent_cycle_waiting.classify_waiting(
                failure(
                    "AGENT_WRITE_LIFECYCLE_REQUEST_WITHOUT_TERMINAL",
                    "AGENT_WRITE_LIFECYCLE_UNKNOWN_AT_CLOSE",
                ),
                meta={"commentId": 200},
                manifest=manifest(),
                output_path=str(closure),
            )
        self.assertEqual(observed, ["AGENT_WRITE_LEASE_RESULT"])

    def test_structural_or_active_lifecycle_failure_is_not_promoted(self):
        for code in (
            "AGENT_TRACE_MUTATION_RECEIPT_MISMATCH",
            "AGENT_WRITE_LIFECYCLE_ACTIVE_AT_CLOSE",
        ):
            with self.subTest(code=code):
                self.assertEqual(
                    hosted_agent_cycle_waiting.classify_waiting(
                        failure(code),
                        meta={"commentId": 200},
                        manifest=manifest(),
                        output_path="/tmp/closure.json",
                    ),
                    [],
                )

    def test_waiting_result_is_hash_bound_non_authoritative_and_non_replaying(self):
        value = hosted_agent_cycle_waiting.build_waiting(
            close_command(),
            manifest(),
            failure(
                "EXECUTION_TRACE_INCOMPLETE",
                "HOSTED_AGENT_EXECUTION_TRACE_INCOMPLETE",
            ),
            ["AGENT_TOOL_RESULT"],
        )
        self.assertEqual(value["status"], "WAITING")
        self.assertEqual(value["observationRetry"], "SAFE")
        self.assertEqual(value["operationReplay"], "NOT_APPLICABLE")
        self.assertTrue(value["readOnly"])
        self.assertFalse(value["semanticAuthority"])
        self.assertFalse(value["authorizesMutation"])
        hosted_agent_cycle_waiting.validate_waiting(value)

    def test_promote_close_result_rewrites_only_waitable_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            begin = root / "begin"
            begin.mkdir()
            (begin / "manifest.json").write_text(json.dumps(manifest()), encoding="utf-8")
            command_path = root / "command.json"
            meta_path = root / "meta.json"
            result_path = root / "result.json"
            command_path.write_text(json.dumps(close_command()), encoding="utf-8")
            meta_path.write_text(json.dumps({"commentId": 200}), encoding="utf-8")
            result_path.write_text(
                json.dumps(
                    failure(
                        "EXECUTION_TRACE_INCOMPLETE",
                        "HOSTED_AGENT_EXECUTION_TRACE_INCOMPLETE",
                    )
                ),
                encoding="utf-8",
            )
            trace = {
                "traceStatus": "INCOMPLETE",
                "attempts": [{"matched": False, "kind": "agent-tool"}],
            }
            with patch.object(
                hosted_agent_cycle_waiting.trace_collect,
                "fetch_issue_comments",
                return_value=[],
            ), patch.object(
                hosted_agent_cycle_waiting.trace_collect,
                "build_trace",
                return_value=trace,
            ):
                promoted = hosted_agent_cycle_waiting.promote_close_result(
                    command_path=str(command_path),
                    meta_path=str(meta_path),
                    begin_dir=str(begin),
                    closure_path=str(root / "closure.json"),
                    result_path=str(result_path),
                )
            self.assertTrue(promoted)
            waiting = json.loads(result_path.read_text(encoding="utf-8"))
            hosted_agent_cycle_waiting.validate_waiting(waiting)
            self.assertEqual(waiting["waitingFor"], ["AGENT_TOOL_RESULT"])

            blocked = failure("AGENT_TRACE_MUTATION_RECEIPT_MISMATCH")
            result_path.write_text(json.dumps(blocked), encoding="utf-8")
            self.assertFalse(
                hosted_agent_cycle_waiting.promote_close_result(
                    command_path=str(command_path),
                    meta_path=str(meta_path),
                    begin_dir=str(begin),
                    closure_path=str(root / "closure.json"),
                    result_path=str(result_path),
                )
            )
            self.assertEqual(
                json.loads(result_path.read_text(encoding="utf-8")),
                blocked,
            )

    def test_waiting_is_operational_but_blocked_failure_is_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "result.json"
            waiting = hosted_agent_cycle_waiting.build_waiting(
                close_command(),
                manifest(),
                failure(
                    "EXECUTION_TRACE_INCOMPLETE",
                    "HOSTED_AGENT_EXECUTION_TRACE_INCOMPLETE",
                ),
                ["AGENT_TOOL_RESULT"],
            )
            path.write_text(json.dumps(waiting), encoding="utf-8")
            hosted_agent_cycle_waiting.require_operational_result(str(path))
            path.write_text(json.dumps(failure("STRUCTURAL_MISMATCH")), encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError, "HOSTED_AGENT_OPERATIONAL_RESULT_INVALID"
            ):
                hosted_agent_cycle_waiting.require_operational_result(str(path))


if __name__ == "__main__":
    unittest.main()
