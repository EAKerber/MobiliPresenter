from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import remote_canonical_execution as bridge
from tools import remote_canonical_issue as issue_adapter


def ui_command(*, path="viewer-next/src/runtime/escape.json"):
    return {
        "schemaVersion": bridge.COMMAND_SCHEMA,
        "executionId": "m12-s2-ui-boundary",
        "kind": "git-direct",
        "actor": {
            "role": "ui-ux",
            "workerId": "ui-ux-a",
            "sessionId": "m12-s2-ui-boundary",
        },
        "declaredIntent": {"goal": "prove role boundary before execution"},
        "target": {
            "operation": "create-file",
            "branch": "experiment/ui/m12-s2-ui-ux",
            "path": path,
        },
        "expected": {"branchHead": "a" * 40},
        "payload": {"content": "{}\n", "message": "M12-S2 UI boundary probe"},
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


def event(command):
    return {
        "repository": {"full_name": bridge.REPOSITORY},
        "issue": {"number": 145, "title": issue_adapter.BUS_TITLE},
        "comment": {
            "id": 9876,
            "author_association": "OWNER",
            "body": issue_adapter.REQUEST_MARKER + "\n" + json.dumps(command),
        },
    }


class RemoteCanonicalUiRoleBoundaryTests(unittest.TestCase):
    @mock.patch("tools.remote_canonical_issue.execute_command")
    def test_forbidden_ui_route_never_reaches_executor(self, execute_command):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            event_path = root / "event.json"
            output_path = root / "result.json"
            event_path.write_text(json.dumps(event(ui_command())), encoding="utf-8")
            rc = issue_adapter.main([
                "--event", str(event_path),
                "--output", str(output_path),
            ])
            result = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(rc, 2)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["blockers"], ["REMOTE_COMMAND_ROLE_PATH_FORBIDDEN"])
        self.assertFalse(result["authorizesMutation"])
        execute_command.assert_not_called()


if __name__ == "__main__":
    unittest.main()
