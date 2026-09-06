from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import hosted_agent_cycle as hosted
from tools.canonical import stable_hash


def close_command() -> dict:
    return {
        "schemaVersion": hosted.COMMAND_SCHEMA,
        "requestId": "m13-close-proof-persistence",
        "action": "close",
        "actor": {
            "role": "manager-gitops",
            "workerId": "m13-close-proof-test",
            "sessionId": "m13-close-proof-session",
        },
        "declaredIntent": "inspect-and-plan",
        "machineScope": "live",
        "begin": {
            "runId": 123,
            "sourceSha": "a" * 40,
            "contextHash": "b" * 64,
        },
        "evidenceCommentIds": [],
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


def legacy_manifest() -> dict:
    command = close_command()
    core = {
        "schemaVersion": hosted.LEGACY_BEGIN_MANIFEST_SCHEMA,
        "requestId": "m13-close-proof-begin",
        "commandHash": "e" * 64,
        "actor": copy.deepcopy(command["actor"]),
        "declaredIntent": command["declaredIntent"],
        "machineScope": "live",
        "source": {
            "workflow": "hosted-agent-cycle",
            "sourceSha": "a" * 40,
            "runId": 123,
            "issueNumber": 145,
            "commentId": 100,
        },
        "artifactName": "agent-cycle-begin-123",
        "cycleId": "cycle-" + "c" * 20,
        "contextHash": "b" * 64,
        "status": "READY",
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**core, "manifestHash": stable_hash(core)}


def begin_dir(root: Path, context: dict) -> Path:
    path = root / "begin"
    path.mkdir()
    (path / "context.json").write_text(json.dumps(context), encoding="utf-8")
    (path / "manifest.json").write_text(json.dumps(legacy_manifest()), encoding="utf-8")
    return path


class HostedAgentCycleNonPassPersistenceM13Tests(unittest.TestCase):
    @patch("tools.hosted_agent_cycle.agent_cycle_close.validate_closure")
    @patch("tools.hosted_agent_cycle.agent_cycle_close.load_evidence", return_value=[])
    @patch("tools.hosted_agent_cycle._run_agent")
    @patch("tools.hosted_agent_cycle._validate_close_binding")
    def test_valid_unknown_closure_is_preserved_before_failure_wrapper(
        self,
        validate_binding,
        run_agent,
        load_evidence,
        validate_closure,
    ):
        context = {"context": "before"}
        closure = {
            "schemaVersion": "AgentCycleClosure 0.1",
            "status": "UNKNOWN",
            "receipt": {"blockers": ["UNATTRIBUTED_DURABLE_DELTA"]},
            "closureHash": "f" * 64,
        }
        run_agent.return_value = (1, closure)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "closure.json"
            with self.assertRaisesRegex(
                hosted.HostedAgentCycleError, "HOSTED_AGENT_CLOSE_NOT_PASS"
            ) as raised:
                hosted.close_from_envelope(
                    close_command(),
                    {"issueNumber": 145, "commentId": 9001},
                    begin_dir=str(begin_dir(root, context)),
                    output_path=str(output),
                    evidence_dir=str(root / "evidence"),
                )
            persisted = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(closure, persisted)
        self.assertEqual("UNKNOWN", raised.exception.failure_core["status"])
        self.assertEqual(
            ["UNATTRIBUTED_DURABLE_DELTA", "HOSTED_AGENT_CLOSE_NOT_PASS"],
            [item["code"] for item in raised.exception.failure_core["causes"]],
        )
        validate_closure.assert_called_once_with(closure, context, evidence=[])
        validate_binding.assert_called_once()
        load_evidence.assert_called_once_with([])

    @patch(
        "tools.hosted_agent_cycle.agent_cycle_close.validate_closure",
        side_effect=RuntimeError("AGENT_CYCLE_CLOSURE_INVALID"),
    )
    @patch("tools.hosted_agent_cycle.agent_cycle_close.load_evidence", return_value=[])
    @patch("tools.hosted_agent_cycle._run_agent")
    @patch("tools.hosted_agent_cycle._validate_close_binding")
    def test_invalid_nonpass_payload_is_not_preserved(
        self,
        validate_binding,
        run_agent,
        load_evidence,
        validate_closure,
    ):
        context = {"context": "before"}
        invalid = {"status": "UNKNOWN", "not": "a closure"}
        run_agent.return_value = (1, invalid)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "closure.json"
            with self.assertRaisesRegex(
                hosted.HostedAgentCycleError, "HOSTED_AGENT_CLOSE_NOT_PASS"
            ):
                hosted.close_from_envelope(
                    close_command(),
                    {"issueNumber": 145, "commentId": 9001},
                    begin_dir=str(begin_dir(root, context)),
                    output_path=str(output),
                    evidence_dir=str(root / "evidence"),
                )
            self.assertFalse(output.exists())

        validate_closure.assert_called_once_with(invalid, context, evidence=[])
        validate_binding.assert_called_once()
        load_evidence.assert_called_once_with([])

    @patch("tools.hosted_agent_cycle._source")
    @patch("tools.hosted_agent_cycle.agent_cycle_close.validate_closure")
    @patch("tools.hosted_agent_cycle.agent_cycle_close.load_evidence", return_value=[])
    @patch("tools.hosted_agent_cycle._run_agent")
    @patch("tools.hosted_agent_cycle._validate_close_binding")
    def test_pass_path_still_persists_and_returns_pass(
        self,
        validate_binding,
        run_agent,
        load_evidence,
        validate_closure,
        source,
    ):
        context = {"context": "before"}
        closure = {
            "status": "PASS",
            "cycleId": "cycle-pass",
            "receipt": {"receiptHash": "c" * 64},
            "closureHash": "d" * 64,
        }
        run_agent.return_value = (0, closure)
        source.return_value = {
            "workflow": "hosted-agent-cycle",
            "sourceSha": "a" * 40,
            "runId": 456,
            "issueNumber": 145,
            "commentId": 9001,
        }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "closure.json"
            result = hosted.close_from_envelope(
                close_command(),
                {"issueNumber": 145, "commentId": 9001},
                begin_dir=str(begin_dir(root, context)),
                output_path=str(output),
                evidence_dir=str(root / "evidence"),
            )
            persisted = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(closure, persisted)
        self.assertEqual("PASS", result["status"])
        self.assertEqual(closure["closureHash"], result["closureHash"])
        self.assertGreaterEqual(validate_closure.call_count, 2)
        validate_binding.assert_called_once()
        load_evidence.assert_called_once_with([])


if __name__ == "__main__":
    unittest.main()
