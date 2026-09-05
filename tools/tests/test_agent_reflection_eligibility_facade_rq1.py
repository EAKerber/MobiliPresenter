from __future__ import annotations

import unittest
from unittest import mock

from tools import agent


class AgentReflectionEligibilityFacadeRQ1Tests(unittest.TestCase):
    def test_reflection_eligibility_is_public_toolbox_command(self):
        self.assertIn("reflection-eligibility", agent.TOOLBOX_COMMANDS)

    def test_main_routes_reflection_eligibility_through_stable_facade(self):
        runner = mock.Mock(return_value=0)
        module = mock.Mock(run=runner)
        argv = [
            "agent.py",
            "reflection-eligibility",
            "--snapshot",
            "snapshot.json",
            "--source-machine",
            "source.json",
            "--routines",
            "routines.json",
            "--readback-machine",
            "readback.json",
            "--json",
        ]
        with mock.patch.object(agent.sys, "argv", argv), mock.patch.object(
            agent.importlib, "import_module", return_value=module
        ) as imported:
            self.assertEqual(0, agent.main())
        imported.assert_called_once_with("tools.reflection_eligibility")
        runner.assert_called_once_with(argv[2:])


if __name__ == "__main__":
    unittest.main()
