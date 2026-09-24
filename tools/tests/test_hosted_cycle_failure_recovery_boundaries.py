from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "hosted-agent-cycle-recovery.yml"
MODULE = ROOT / "tools" / "hosted_cycle_failure_recovery.py"


class HostedCycleRecoveryBoundaryTests(unittest.TestCase):
    def test_workflow_is_read_only_against_repository_authorities(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("contents: read", text)
        self.assertIn("issues: write", text)
        self.assertNotIn("contents: write", text)
        self.assertNotIn("gh api", text)
        self.assertNotIn("git commit", text)

    def test_recovery_module_has_no_authority_writer(self):
        text = MODULE.read_text(encoding="utf-8")
        for forbidden in (
            "coordination_apply",
            "GitHubCoordinationAuthority(",
            "execute_command(",
            "mutation_host",
            "update_ref(",
            "create_commit(",
        ):
            self.assertNotIn(forbidden, text)
        self.assertIn("agent_write_lifecycle_guard.inspect_cycle(", text)


if __name__ == "__main__":
    unittest.main()
