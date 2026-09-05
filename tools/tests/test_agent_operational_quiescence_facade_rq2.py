from __future__ import annotations

import unittest
from unittest import mock

from tools import agent


class AgentOperationalQuiescenceFacadeRQ2Tests(unittest.TestCase):
    def test_operational_quiescence_is_public_toolbox_command(self):
        self.assertIn("operational-quiescence", agent.TOOLBOX_COMMANDS)

    def test_main_routes_operational_quiescence_through_stable_facade(self):
        runner = mock.Mock(return_value=0)
        module = mock.Mock(run=runner)
        argv = [
            "agent.py",
            "operational-quiescence",
            "sample",
            "--snapshot",
            "snapshot.json",
            "--reflection",
            "reflection.json",
            "--source-machine",
            "source.json",
            "--routines",
            "routines.json",
            "--readback-machine",
            "readback.json",
            "--observation-id",
            "run:1",
            "--sequence",
            "1",
            "--json",
        ]
        with mock.patch.object(agent.sys, "argv", argv), mock.patch.object(
            agent.importlib, "import_module", return_value=module
        ) as imported:
            self.assertEqual(0, agent.main())
        imported.assert_called_once_with("tools.operational_quiescence")
        runner.assert_called_once_with(argv[2:])


if __name__ == "__main__":
    unittest.main()
