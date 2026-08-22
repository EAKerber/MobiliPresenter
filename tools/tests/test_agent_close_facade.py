import unittest
from unittest import mock

from tools import agent


class AgentCloseFacadeTests(unittest.TestCase):
    def test_close_is_public_toolbox_command(self):
        self.assertIn("close", agent.TOOLBOX_COMMANDS)

    def test_main_routes_close_without_entering_legacy_parser(self):
        with mock.patch.object(agent.sys, "argv", ["agent.py", "close", "--context", "cycle.json", "--json"]), mock.patch.object(agent.agent_cycle_close, "main", return_value=0) as close:
            self.assertEqual(agent.main(), 0)
        close.assert_called_once_with(["--context", "cycle.json", "--json"])


if __name__ == "__main__":
    unittest.main()
