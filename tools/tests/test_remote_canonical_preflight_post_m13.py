from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from tools import remote_canonical_execution as bridge
from tools import remote_canonical_issue as issue_adapter


ACTOR = {
    "role": "manager-gitops",
    "workerId": "manager-gitops-primary",
    "sessionId": "post-m13-r2-preflight-test",
}


def update_command() -> dict:
    return {
        "schemaVersion": bridge.COMMAND_SCHEMA,
        "executionId": "post-m13-r2-update-preflight",
        "kind": "git-direct",
        "actor": ACTOR,
        "declaredIntent": {"goal": "qualify manual RemoteCanonical preflight"},
        "target": {
            "operation": "update-file",
            "branch": "work/operations/post-m13-r2-preflight-target",
            "path": "docs/experiments/post-m13-r2-preflight-probe.txt",
        },
        "expected": {"branchHead": "a" * 40, "blobSha": "b" * 40},
        "payload": {"content": "after\n", "message": "Post-M13 R2 preflight probe"},
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


def event(comment_body: str) -> dict:
    return {
        "repository": {"full_name": "EAKerber/MobiliPresenter"},
        "issue": {"number": 145, "title": issue_adapter.BUS_TITLE},
        "comment": {
            "id": 9001,
            "author_association": "OWNER",
            "body": comment_body,
        },
    }


class RemoteCanonicalPreflightPostM13Tests(unittest.TestCase):
    def test_valid_update_renders_exact_receiver_compatible_comment(self):
        command = update_command()
        result = issue_adapter.prepare_comment(command)
        parsed, meta = issue_adapter.parse_event(event(result["commentBody"]))
        self.assertEqual(parsed, command)
        self.assertEqual(meta, {"issueNumber": 145, "commentId": 9001})
        self.assertEqual(result["commandHash"], bridge.command_hash(command))
        self.assertTrue(result["transportReady"])
        self.assertFalse(result["semanticAuthority"])
        self.assertFalse(result["authorizesMutation"])

    def test_empirical_missing_update_message_is_blocked_before_transport(self):
        command = update_command()
        del command["payload"]["message"]
        with self.assertRaisesRegex(RuntimeError, "REMOTE_COMMAND_PAYLOAD_INVALID"):
            issue_adapter.prepare_comment(command)

    def test_cli_blocked_preflight_does_not_materialize_comment_output(self):
        command = update_command()
        del command["payload"]["message"]
        with tempfile.TemporaryDirectory() as tmp:
            command_path = Path(tmp) / "command.json"
            output_path = Path(tmp) / "comment.txt"
            command_path.write_text(json.dumps(command), encoding="utf-8")
            stdout = StringIO()
            stderr = StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                status = issue_adapter.main(
                    [
                        "--preflight-command",
                        str(command_path),
                        "--comment-output",
                        str(output_path),
                    ]
                )
            self.assertEqual(status, 2)
            self.assertFalse(output_path.exists())
            failure = json.loads(stderr.getvalue())
            self.assertEqual(failure["status"], "BLOCKED")
            self.assertEqual(failure["blockers"], ["REMOTE_COMMAND_PAYLOAD_INVALID"])
            self.assertFalse(failure["transportReady"])
            self.assertEqual(stdout.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
