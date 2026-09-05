from __future__ import annotations

import unittest
from unittest import mock

from tools import agent


class AgentCloseReviewFacadeR1CTests(unittest.TestCase):
    def test_close_review_is_public_toolbox_command(self):
        self.assertIn("close-review", agent.TOOLBOX_COMMANDS)

    def test_main_routes_close_review_through_stable_facade(self):
        runner = mock.Mock(return_value=0)
        module = mock.Mock(run=runner)
        argv = ["agent.py", "close-review", "--context", "cycle.json", "--json"]
        with mock.patch.object(agent.sys, "argv", argv), mock.patch.object(
            agent.importlib, "import_module", return_value=module
        ) as imported:
            self.assertEqual(0, agent.main())
        imported.assert_called_once_with("tools.agent_cycle_close_review")
        runner.assert_called_once_with(["--context", "cycle.json", "--json"])


if __name__ == "__main__":
    unittest.main()
