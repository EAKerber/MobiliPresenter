from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "hosted-agent-cycle.yml"


class HostedAgentCycleCloseCompatibilityRecoveryWorkflowTests(unittest.TestCase):
    def test_recovery_is_exact_read_only_and_same_cycle(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("Qualify observational close compatibility recovery", text)
        self.assertIn("HOSTED_CYCLE_RECORD_LEASE_REQUEST_INVALID", text)
        self.assertIn("hosted-agent-cycle-trace", text)
        self.assertIn("AGENT_WRITE_LIFECYCLE_BINDING_AUTHORITY_MISMATCH", text)
        self.assertIn("agent-write-lifecycle-guard", text)
        self.assertIn("AGENT_WRITE_LIFECYCLE_UNKNOWN_AT_CLOSE", text)
        self.assertIn("hosted-agent-cycle", text)
        self.assertIn("recovery.get('observationRetry') == 'UNKNOWN'", text)
        self.assertIn("recovery.get('operationReplay') == 'NOT_APPLICABLE'", text)
        self.assertIn("core.get('mutationState') == 'NOT_APPLICABLE'", text)
        self.assertIn("core.get('lossyProjection') is False", text)
        self.assertIn("core.get('readOnly') is True", text)
        self.assertIn("core.get('semanticAuthority') is False", text)
        self.assertIn("core.get('authorizesMutation') is False", text)
        self.assertIn("core.get('causes') in compatible_causes", text)

        # Recovery restores only the current carrier; the begin artifact remains
        # the exact historical cycle identity and is reused unchanged.
        self.assertIn("Restore current hosted-cycle carrier for compatible close observation", text)
        self.assertIn("HOSTED_AGENT_SOURCE_SHA: ${{ github.sha }}", text)
        self.assertGreaterEqual(text.count("--begin-dir /tmp/agent-cycle-begin"), 2)
        self.assertNotIn("agent begin", text)
        self.assertNotIn("agent-write-lease-dispatch", text)
        self.assertNotIn("hosted_cycle_close_compat_recovery.py", text)

        # A recovered close is a first-class successful close for shadow review
        # and proof upload, while promotion only happens when both attempts fail.
        success = "steps.close.outcome == 'success' || steps.close_recovery.outcome == 'success'"
        self.assertGreaterEqual(text.count(success), 2)
        self.assertIn("steps.close_recovery.outcome != 'success'", text)
        self.assertIn("compatibility-recovery-source.json", text)

    def test_recovery_accepts_only_two_closed_failure_signatures(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        recovery_region = text.split("Qualify observational close compatibility recovery", 1)[1]
        recovery_region = recovery_region.split("Materialize close termination review shadow", 1)[0]

        self.assertNotIn("EXECUTION_TRACE_INCOMPLETE", recovery_region)
        self.assertNotIn("HOSTED_AGENT_CLOSE_NOT_PASS", recovery_region)
        self.assertEqual(1, recovery_region.count("HOSTED_CYCLE_RECORD_LEASE_REQUEST_INVALID"))
        self.assertEqual(
            1, recovery_region.count("AGENT_WRITE_LIFECYCLE_BINDING_AUTHORITY_MISMATCH")
        )
        self.assertEqual(1, recovery_region.count("AGENT_WRITE_LIFECYCLE_UNKNOWN_AT_CLOSE"))
        self.assertEqual(1, recovery_region.count("core.get('causes') in compatible_causes"))
        self.assertNotIn("core.get('causes') is not None", recovery_region)
        self.assertNotIn("if core.get('causes')", recovery_region)


if __name__ == "__main__":
    unittest.main()
