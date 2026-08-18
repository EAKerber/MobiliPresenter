import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class BootstrapBoundaryTests(unittest.TestCase):
    def test_current_bootstrap_has_no_retired_operational_surfaces_or_delta_chain(self):
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        current = (ROOT / "docs/kickstarts/roles/manager-gitops-current.md").read_text(encoding="utf-8")
        v05 = (ROOT / "docs/kickstarts/roles/manager-gitops-v0.5.md").read_text(encoding="utf-8")
        combined = agents + "\n" + current + "\n" + v05
        for retired in ("maintenance_live.py", "scheduler_plan.py --live", "maintenance_inspect.py --remote"):
            self.assertNotIn(retired, combined)
        self.assertIn("manager-gitops-v0.5.md", current)
        self.assertNotIn("manager-gitops-v0.4.md", current)
        self.assertNotIn("manager-gitops-v0.3.md", current)
        self.assertNotIn("manager-gitops-v0.4.md", v05)
        self.assertNotIn("manager-gitops-v0.3.md", v05)


if __name__ == "__main__":
    unittest.main()
