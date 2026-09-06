from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

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
                "coordination": {"branch": "coordination/leases", "sha": "d" * 40},
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
        self.assertEqual(closure["receipt"]["delta"]["durableChanges"], diagnostic["durableChanges"])
        self.assertEqual(
            ["source-head:coordination:1"], diagnostic["coveredDurableChanges"]
        )
        self.assertEqual(
            ["source-head:control:0"], diagnostic["uncoveredDurableChanges"]
        )
        self.assertEqual(1, diagnostic["evidenceCount"])
        self.assertTrue(diagnostic["readOnly"])
        self.assertFalse(diagnostic["semanticAuthority"])
        self.assertFalse(diagnostic["authorizesMutation"])
        body = {key: value for key, value in diagnostic.items() if key != "diagnosticHash"}
        self.assertEqual(stable_hash(body), diagnostic["diagnosticHash"])

    def test_projection_refuses_non_unattributed_close(self):
        closure = unattributed_closure()
        closure["receipt"]["blockers"] = ["AFTER_CONTEXT_UNKNOWN"]
        self.assertIsNone(waiting.build_close_delta_diagnostic(closure))

    def test_emission_is_log_only_and_does_not_rewrite_closure(self):
        closure = unattributed_closure()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "closure.json"
            original = json.dumps(closure, indent=2) + "\n"
            path.write_text(original, encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output):
                emitted = waiting._emit_close_delta_diagnostic(str(path))
            self.assertTrue(emitted)
            self.assertEqual(original, path.read_text(encoding="utf-8"))
            logged = json.loads(output.getvalue())
        self.assertEqual("source-head:control:0", logged["uncoveredDurableChanges"][0])
        self.assertTrue(logged["readOnly"])
        self.assertFalse(logged["semanticAuthority"])
        self.assertFalse(logged["authorizesMutation"])


if __name__ == "__main__":
    unittest.main()
