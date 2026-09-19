import inspect
import unittest
from unittest import mock

from tools import agent_cycle_close_recovery as recovery
from tools.agent_cycle_close_recovery import hosted


def unknown_closure():
    return {
        "status": "UNKNOWN",
        "receipt": {
            "blockers": ["UNATTRIBUTED_DURABLE_DELTA"],
            "delta": {"durableChanges": []},
            "aggregateReadback": {
                "coveredDurableChanges": [],
                "uncoveredDurableChanges": [],
            },
        },
    }


class CloseRecoveryProviderDiagnosticTests(unittest.TestCase):
    def test_recovery_error_remains_fail_closed_by_default(self):
        with mock.patch.object(
            recovery,
            "noninterference_evidence",
            side_effect=RuntimeError("AGENT_CYCLE_CLOSE_NONINTERFERENCE_TEST_FAILURE"),
        ):
            self.assertIsNone(
                recovery.recovery_evidence(
                    unknown_closure(),
                    context_path="unused.json",
                    transport=object(),
                )
            )

    def test_strict_recovery_propagates_exact_diagnostic(self):
        with mock.patch.object(
            recovery,
            "noninterference_evidence",
            side_effect=RuntimeError("AGENT_CYCLE_CLOSE_NONINTERFERENCE_TEST_FAILURE"),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "AGENT_CYCLE_CLOSE_NONINTERFERENCE_TEST_FAILURE",
            ):
                recovery.recovery_evidence(
                    unknown_closure(),
                    context_path="unused.json",
                    transport=object(),
                    raise_on_error=True,
                )

    def test_hosted_recovery_injects_provider_and_requests_strict_diagnostics(self):
        source = inspect.getsource(hosted.close_with_compatibility_recovery)
        self.assertIn("carrier = GhApiTransport()", source)
        self.assertIn("transport=carrier", source)
        self.assertIn("raise_on_recovery_error=True", source)
        self.assertIn('"AgentCycleCloseRecoveryDiagnostic 0.1"', source)
        self.assertIn('"authorizesMutation": False', source)


if __name__ == "__main__":
    unittest.main()
