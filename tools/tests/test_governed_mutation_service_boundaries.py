from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "governed-mutation-service.yml"
SERVICE = ROOT / "tools" / "governed_mutation_service.py"


class GovernedMutationServiceBoundaryTests(unittest.TestCase):
    def test_workflow_is_thin_service_carrier(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("governed_mutation_service.py prepare", text)
        self.assertIn("semantic-host/tools/governed_mutation_service.py execute", text)
        self.assertIn("actions/download-artifact@v4", text)
        self.assertIn("MOBILIPRESENTER_GOVERNED_MUTATION_INSPECT_V0_1", text)
        self.assertIn("parse-inspection-event", text)
        self.assertIn("inspect-artifact", text)
        self.assertNotIn("gh api", text)
        self.assertNotIn("git commit", text)
        self.assertNotIn("git update-ref", text)

    def test_service_does_not_reimplement_git_writer_or_authority(self):
        text = SERVICE.read_text(encoding="utf-8")
        for forbidden in (
            "create_tree(",
            "create_commit(",
            "update_ref(",
            "coordination_apply.apply(",
            "GitHubCoordinationAuthority(",
        ):
            self.assertNotIn(forbidden, text)
        self.assertIn("mutation_host.execute_plan(", text)
        self.assertIn("observe_turnover_context(", text)
        self.assertIn("hosted_cycle_handle.bind(", text)

    def test_kitchen_window_reader_is_read_only(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        reader = text.split("  inspect_window:", 1)[1]
        self.assertIn("contents: read", reader)
        self.assertIn("actions: read", reader)
        self.assertNotIn("contents: write", reader)
        self.assertNotIn("mutation_host.execute_plan", reader)


if __name__ == "__main__":
    unittest.main()
