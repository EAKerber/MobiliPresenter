from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from tools import hosted_agent_cycle_waiting as waiting
from tools.canonical import stable_hash


def unattributed_closure() -> dict:
    durable = [
        {
            "kind": "source-head",
            "name": "control",
            "branch": "main",
            "before": "a" * 40,
            "after": "b" * 40,
        },
        {
            "kind": "source-head",
            "name": "coordination",
            "branch": "coordination/leases",
            "before": "c" * 40,
            "after": "d" * 40,
        },
    ]
    receipt = {
        "receiptHash": "2" * 64,
        "status": "UNKNOWN",
        "blockers": ["UNATTRIBUTED_DURABLE_DELTA"],
        "delta": {"durableChanges": durable},
        "aggregateReadback": {
            "sourceHeads": {
                "control": {"branch": "main", "sha": "b" * 40},
                "coordination": {
                    "branch": "coordination/leases",
                    "sha": "d" * 40,
                },
            },
            "coveredDurableChanges": ["source-head:coordination:1"],
            "uncoveredDurableChanges": ["source-head:control:0"],
            "evidenceCount": 1,
        },
    }
    return {
        "schemaVersion": "AgentCycleClosure 0.1",
        "status": "UNKNOWN",
        "cycleId": "cycle-diagnostic",
        "closureHash": "1" * 64,
        "receipt": receipt,
    }


class HostedAgentCycleCloseDeltaDiagnosticM13Tests(unittest.TestCase):
    def test_projection_copies_only_canonical_close_delta_evidence(self):
        closure = unattributed_closure()
        diagnostic = waiting.build_close_delta_diagnostic(closure)
        self.assertIsNotNone(diagnostic)
        assert diagnostic is not None
        self.assertEqual(
            "HostedAgentCycleCloseDeltaDiagnostic 0.1",
            diagnostic["schemaVersion"],
        )
        self.assertEqual(
            closure["receipt"]["delta"]["durableChanges"],
            diagnostic["durableChanges"],
        )
        self.assertEqual(
            ["source-head:coordination:1"],
            diagnostic["coveredDurableChanges"],
        )
        self.assertEqual(
            ["source-head:control:0"],
            diagnostic["uncoveredDurableChanges"],
        )
        self.assertEqual(1, diagnostic["evidenceCount"])
        self.assertTrue(diagnostic["readOnly"])
        self.assertFalse(diagnostic["semanticAuthority"])
        self.assertFalse(diagnostic["authorizesMutation"])
        body = {
            key: value
            for key, value in diagnostic.items()
            if key != "diagnosticHash"
        }
        self.assertEqual(stable_hash(body), diagnostic["diagnosticHash"])

    def test_projection_refuses_non_unattributed_close(self):
        closure = unattributed_closure()
        closure["receipt"]["blockers"] = ["AFTER_CONTEXT_UNKNOWN"]
        self.assertIsNone(waiting.build_close_delta_diagnostic(closure))

    @patch("tools.hosted_agent_cycle_waiting.agent_cycle_close.validate_closure")
    @patch("tools.hosted_agent_cycle_waiting.agent_cycle_close.load_evidence")
    @patch("tools.hosted_agent_cycle_waiting.agent_cycle_close.close_from_files")
    @patch("tools.hosted_agent_cycle_waiting.hosted_agent_cycle.normalize_remote_evidence")
    @patch("tools.hosted_agent_cycle_waiting.hosted_agent_cycle._remote_result_payload")
    @patch("tools.hosted_agent_cycle_waiting.hosted_agent_cycle.validate_transport_command")
    def test_materialization_reobserves_and_preserves_attempt_without_operational_rewrite(
        self,
        validate_command,
        remote_result,
        normalize,
        close_from_files,
        load_evidence,
        validate_closure,
    ):
        closure = unattributed_closure()
        command = {
            "action": "close",
            "evidenceCommentIds": [17],
        }
        validate_command.return_value = command
        remote_result.return_value = {"receipt": "remote"}
        normalized = {"kind": "transition-receipt", "proof": "normalized"}
        normalize.return_value = normalized
        close_from_files.return_value = closure
        load_evidence.return_value = [normalized]

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            begin_dir = root / "begin"
            close_dir = root / "close"
            begin_dir.mkdir()
            close_dir.mkdir()
            context = {"context": "before"}
            (begin_dir / "context.json").write_text(
                json.dumps(context),
                encoding="utf-8",
            )
            output = io.StringIO()
            with redirect_stdout(output):
                materialized = waiting._materialize_close_delta_diagnostic(
                    command,
                    begin_dir=str(begin_dir),
                    closure_path=str(close_dir / "closure.json"),
                )

            self.assertTrue(materialized)
            attempt = json.loads(
                (close_dir / "closure-attempt.json").read_text(encoding="utf-8")
            )
            diagnostic = json.loads(
                (close_dir / "close-delta-diagnostic.json").read_text(
                    encoding="utf-8"
                )
            )
            evidence_path = close_dir / "close-delta-evidence" / "evidence-000.json"
            self.assertEqual(closure, attempt)
            self.assertEqual(
                normalized,
                json.loads(evidence_path.read_text(encoding="utf-8")),
            )
            self.assertEqual(
                ["source-head:control:0"],
                diagnostic["uncoveredDurableChanges"],
            )
            self.assertFalse((close_dir / "closure.json").exists())
            self.assertIn(
                "HOSTED_AGENT_CLOSE_DELTA_DIAGNOSTIC ",
                output.getvalue(),
            )

        close_from_files.assert_called_once()
        kwargs = close_from_files.call_args.kwargs
        self.assertEqual("live", kwargs["machine_scope"])
        self.assertEqual(1, len(kwargs["evidence_paths"]))
        load_evidence.assert_called_once_with(kwargs["evidence_paths"])
        validate_closure.assert_called_once_with(
            closure,
            context,
            evidence=[normalized],
        )

    @patch(
        "tools.hosted_agent_cycle_waiting.agent_cycle_close.close_from_files",
        side_effect=RuntimeError("PROJECT_MACHINE_OBSERVATION_UNAVAILABLE"),
    )
    @patch("tools.hosted_agent_cycle_waiting.hosted_agent_cycle.validate_transport_command")
    def test_materialization_failure_is_unknown_and_does_not_raise(
        self,
        validate_command,
        close_from_files,
    ):
        command = {"action": "close", "evidenceCommentIds": []}
        validate_command.return_value = command
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            begin_dir = root / "begin"
            close_dir = root / "close"
            begin_dir.mkdir()
            close_dir.mkdir()
            (begin_dir / "context.json").write_text(
                json.dumps({"context": "before"}),
                encoding="utf-8",
            )
            output = io.StringIO()
            with redirect_stdout(output):
                materialized = waiting._materialize_close_delta_diagnostic(
                    command,
                    begin_dir=str(begin_dir),
                    closure_path=str(close_dir / "closure.json"),
                )
            self.assertFalse(materialized)
            self.assertFalse((close_dir / "closure-attempt.json").exists())
            error = json.loads(
                (close_dir / "close-delta-diagnostic.error.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual("UNKNOWN", error["status"])
            self.assertEqual(
                "HOSTED_AGENT_CLOSE_DELTA_DIAGNOSTIC_UNAVAILABLE",
                error["reasonCode"],
            )
            self.assertEqual(
                "PROJECT_MACHINE_OBSERVATION_UNAVAILABLE",
                error["detailCode"],
            )
            self.assertTrue(error["readOnly"])
            self.assertFalse(error["semanticAuthority"])
            self.assertFalse(error["authorizesMutation"])
            self.assertIn(
                "HOSTED_AGENT_CLOSE_DELTA_DIAGNOSTIC ",
                output.getvalue(),
            )
        close_from_files.assert_called_once()


if __name__ == "__main__":
    unittest.main()
