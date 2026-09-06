from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "hosted-agent-cycle.yml"


class HostedAgentCycleCloseCompatibilityRecoveryWorkflowTests(unittest.TestCase):
    def test_recovery_is_exact_read_only_and_same_cycle(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("Preserve close compatibility qualifier", text)
        self.assertIn(
            "cp tools/hosted_cycle_close_compat_recovery.py /tmp/hosted-cycle-close-compat-recovery.py",
            text,
        )
        self.assertIn("id: close_recovery_eligibility", text)
        self.assertIn(
            "python /tmp/hosted-cycle-close-compat-recovery.py --result /tmp/hosted-result.json",
            text,
        )

        # Recovery restores only the current carrier; the begin artifact remains
        # the exact historical cycle identity and is reused unchanged.
        self.assertIn("Restore current hosted-cycle carrier for compatible close observation", text)
        self.assertIn("ref: ${{ github.sha }}", text)
        self.assertIn("HOSTED_AGENT_SOURCE_SHA: ${{ github.sha }}", text)
        self.assertGreaterEqual(text.count("--begin-dir /tmp/agent-cycle-begin"), 2)
        self.assertNotIn("agent begin", text)
        self.assertNotIn("agent-write-lease-dispatch", text)

        # A recovered close is a first-class successful close for shadow review
        # and proof upload, while promotion only happens when both attempts fail.
        success = "steps.close.outcome == 'success' || steps.close_recovery.outcome == 'success'"
        self.assertGreaterEqual(text.count(success), 2)
        self.assertIn("steps.close_recovery.outcome != 'success'", text)
        self.assertIn("compatibility-recovery-source.json", text)

    def test_workflow_does_not_broaden_recovery_error_codes(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        recovery_region = text.split("Qualify observational close compatibility recovery", 1)[1]
        recovery_region = recovery_region.split("Materialize close termination review shadow", 1)[0]

        self.assertNotIn("EXECUTION_TRACE_INCOMPLETE", recovery_region)
        self.assertNotIn("HOSTED_AGENT_CLOSE_NOT_PASS", recovery_region)
        self.assertNotIn("operationReplay", recovery_region)
        self.assertNotIn("mutationState", recovery_region)


if __name__ == "__main__":
    unittest.main()
