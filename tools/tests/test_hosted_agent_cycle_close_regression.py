from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import hosted_agent_cycle as hosted


def close_command():
    return {
        "schemaVersion": hosted.COMMAND_SCHEMA,
        "requestId": "hosted-cycle-close-regression",
        "action": "close",
        "actor": {
            "role": "manager-gitops",
            "workerId": "manager-gitops-a",
            "sessionId": "session-regression",
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


class HostedAgentCycleCloseRegressionTests(unittest.TestCase):
    @patch("tools.hosted_agent_cycle._source")
    @patch("tools.hosted_agent_cycle.agent_cycle_close.validate_closure")
    @patch("tools.hosted_agent_cycle.agent_cycle_close.load_evidence")
    @patch("tools.hosted_agent_cycle._run_agent")
    @patch("tools.hosted_agent_cycle._validate_close_binding")
    def test_close_validation_is_bound_to_begin_context_and_same_evidence(
        self,
        validate_binding,
        run_agent,
        load_evidence,
        validate_closure,
        source,
    ):
        context = {"context": "before"}
        manifest = {"source": {"runId": 123}, "contextHash": "b" * 64}
        closure = {
            "status": "PASS",
            "cycleId": "cycle-regression",
            "receipt": {"receiptHash": "c" * 64},
            "closureHash": "d" * 64,
        }
        evidence = [{"kind": "verified-evidence"}]
        run_agent.return_value = (0, closure)
        load_evidence.return_value = evidence
        source.return_value = {
            "workflow": "hosted-agent-cycle",
            "sourceSha": "a" * 40,
            "runId": 456,
            "issueNumber": 145,
            "commentId": 9001,
        }

        with tempfile.TemporaryDirectory() as tmp:
            begin_dir = Path(tmp) / "begin"
            begin_dir.mkdir()
            (begin_dir / "context.json").write_text(json.dumps(context), encoding="utf-8")
            (begin_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            output = Path(tmp) / "closure.json"
            result = hosted.close_from_envelope(
                close_command(),
                {"issueNumber": 145, "commentId": 9001},
                begin_dir=str(begin_dir),
                output_path=str(output),
                evidence_dir=str(Path(tmp) / "evidence"),
            )

        validate_binding.assert_called_once()
        load_evidence.assert_called_once_with([])
        validate_closure.assert_called_once_with(closure, context, evidence=evidence)
        self.assertEqual(result["status"], "PASS")

    @patch("tools.hosted_agent_cycle.close_from_envelope", side_effect=TypeError("unexpected close bug"))
    def test_cli_materializes_unexpected_close_exception_as_blocker(self, close):
        command = close_command()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            command_path = root / "command.json"
            meta_path = root / "meta.json"
            result_path = root / "result.json"
            command_path.write_text(json.dumps(command), encoding="utf-8")
            meta_path.write_text(json.dumps({"issueNumber": 145, "commentId": 9001}), encoding="utf-8")
            rc = hosted.main([
                "close",
                "--command", str(command_path),
                "--meta", str(meta_path),
                "--begin-dir", str(root / "begin"),
                "--closure", str(root / "closure.json"),
                "--evidence-dir", str(root / "evidence"),
                "--result", str(result_path),
            ])
            payload = json.loads(result_path.read_text(encoding="utf-8"))

        close.assert_called_once()
        self.assertEqual(rc, 2)
        self.assertEqual(payload["status"], "BLOCKED")
        self.assertIn("unexpected close bug", payload["detail"])
        self.assertFalse(payload["authorizesMutation"])


if __name__ == "__main__":
    unittest.main()
