from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "agent-write-lease-dispatch.yml"


class AgentWriteLifecycleWorkflowEntrypointTests(unittest.TestCase):
    def test_dispatch_host_runs_as_package_module(self):
        text = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn(
            "python -m tools.agent_write_lifecycle_host inspect",
            text,
        )
        self.assertIn(
            "python -m tools.agent_write_lifecycle_host execute",
            text,
        )
        self.assertNotIn(
            "python tools/agent_write_lifecycle_host.py",
            text,
        )


if __name__ == "__main__":
    unittest.main()
