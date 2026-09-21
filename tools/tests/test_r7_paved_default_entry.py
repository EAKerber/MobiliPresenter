from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from tools import agent, agent_commands


class R7PavedDefaultEntryTests(unittest.TestCase):
    def test_direct_begin_is_no_longer_advertised_as_public_toolbox_surface(self) -> None:
        self.assertNotIn("begin", agent.TOOLBOX_COMMANDS)
        self.assertIn("continue", agent.TOOLBOX_COMMANDS)

    def test_direct_begin_is_retired_from_public_agent_cli(self) -> None:
        with mock.patch("sys.argv", ["agent", "begin"]):
            with self.assertRaises(SystemExit) as raised:
                agent_commands.main()
        self.assertEqual(2, raised.exception.code)

    def test_runtime_surface_binding_no_longer_accepts_direct_begin(self) -> None:
        with self.assertRaisesRegex(
            RuntimeError,
            "RUNTIME_TOOL_SURFACES_REQUIRE_CONTINUE_OR_DOCTOR",
        ):
            agent._runtime_surface_base(
                ["agent", "begin"],
                ["github-connector-tools"],
                inventory_complete=True,
            )

    def test_bootstrap_without_work_requires_work_observation(self) -> None:
        value = agent._bootstrap_projection()
        self.assertEqual("OBSERVE_WORK", value["nextSafeAction"])
        self.assertEqual(
            "python3 tools/agent.py status --work-id <work-id> --json",
            value["commandTemplate"],
        )
        self.assertIsNone(value["pavedEntry"])
        self.assertNotIn("legacyDirectBegin", value)

    def test_work_bound_new_cycle_projects_host_provider_semantic_entry(self) -> None:
        reentry = {
            "nextSafeAction": "BEGIN_NEW_CYCLE",
            "reentryDisposition": "BEGIN_NEW_CYCLE",
            "workRef": {"workId": "r7-default-entry"},
            "reasonCodes": [],
            "targetCycle": None,
        }
        value = agent._bootstrap_projection(reentry)
        self.assertIsNone(value["commandTemplate"])
        self.assertEqual(
            {
                "surface": "journey-entry",
                "implementation": "tools.agent_tools.journey_entry.compose_entry",
                "executionBoundary": "host-provider",
                "toolSurface": "github-connector-tools",
                "workId": "r7-default-entry",
            },
            value["pavedEntry"],
        )
        self.assertNotIn("legacyDirectBegin", value)

    def test_manager_role_demotes_direct_begin(self) -> None:
        root = Path(__file__).resolve().parents[2]
        content = (
            root / "docs" / "kickstarts" / "roles" / "manager-gitops.md"
        ).read_text(encoding="utf-8")
        self.assertIn("bootstrap.pavedEntry", content)
        self.assertIn("journey-entry", content)
        self.assertIn("foi retirado em R8", content)
        self.assertIn("Hosted Agent Cycle", content)


if __name__ == "__main__":
    unittest.main()
