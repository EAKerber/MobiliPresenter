from __future__ import annotations

import io
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from contextlib import redirect_stdout

from tools import agent


class R7PavedDefaultEntryTests(unittest.TestCase):
    def test_reentry_projection_uses_semantic_enter_not_direct_begin(self) -> None:
        reentry = {
            "nextSafeAction": "BEGIN_NEW_CYCLE",
            "reentryDisposition": "BEGIN_NEW_CYCLE",
            "workRef": {"workId": "r7-default-entry"},
            "reasonCodes": [],
            "targetCycle": None,
        }
        value = agent._bootstrap_projection(reentry)
        command = value["commandTemplate"]
        self.assertIn("tools/agent.py enter", command)
        self.assertIn("--work-id r7-default-entry", command)
        self.assertNotIn("tools/agent.py begin", command)

    def test_enter_requires_observed_runtime_tool_surfaces(self) -> None:
        argv = [
            "agent",
            "enter",
            "--work-id", "r7-default-entry",
            "--role", "manager-gitops",
            "--intent", "promote paved default",
            "--apply",
            "--json",
        ]
        with self.assertRaisesRegex(
            RuntimeError, "RUNTIME_TOOL_SURFACES_REQUIRED_FOR_ENTER"
        ):
            agent._run_with_runtime_tool_surfaces(argv)

    def test_enter_delegates_to_existing_journey_entry_composer(self) -> None:
        compose = Mock(return_value={
            "status": "PASS",
            "disposition": "REUSED",
            "submitted": False,
            "blockers": [],
        })
        module = SimpleNamespace(compose_entry=compose)
        argv = [
            "agent",
            "enter",
            "--work-id", "r7-default-entry",
            "--role", "manager-gitops",
            "--intent", "promote paved default",
            "--apply",
            "--json",
        ]
        with patch.object(agent.importlib, "import_module", return_value=module):
            with redirect_stdout(io.StringIO()):
                rc = agent.command_enter(
                    argv,
                    tool_surfaces=["github-connector-tools"],
                    inventory_complete=True,
                )
        self.assertEqual(0, rc)
        kwargs = compose.call_args.kwargs
        self.assertEqual("r7-default-entry", kwargs["work_id"])
        self.assertEqual("manager-gitops", kwargs["role"])
        self.assertEqual("promote paved default", kwargs["declared_intent"])
        self.assertEqual(["github-connector-tools"], kwargs["tool_surfaces"])
        self.assertTrue(kwargs["inventory_complete"])
        self.assertTrue(kwargs["submit"])

    def test_manager_role_documents_enter_as_normal_work_bound_entry(self) -> None:
        root = Path(__file__).resolve().parents[2]
        content = (
            root / "docs" / "kickstarts" / "roles" / "manager-gitops.md"
        ).read_text(encoding="utf-8")
        self.assertIn("tools/agent.py enter", content)
        self.assertIn("begin", content)
        self.assertIn("diagnóstico, testes e recovery explícito", content)


if __name__ == "__main__":
    unittest.main()
