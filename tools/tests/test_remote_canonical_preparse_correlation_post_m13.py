from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from tools import remote_canonical_execution as bridge
from tools import remote_canonical_issue as issue_adapter
from tools.agent_tools import trace_collect
from tools.canonical import stable_hash

ACTOR = {
    "role": "manager-gitops",
    "workerId": "manager-gitops-a",
    "sessionId": "post-m13-preparse-correlation-test",
}
BEGIN = {
    "runId": 123,
    "sourceSha": "a" * 40,
    "contextHash": "b" * 64,
}


def invalid_remote_command() -> dict:
    return {
        "schemaVersion": bridge.COMMAND_SCHEMA,
        "executionId": "remote-preparse-invalid",
        "kind": "git-direct",
        "actor": copy.deepcopy(ACTOR),
        "declaredIntent": {"goal": "prove rejected-command correlation"},
        "target": {
            "operation": "update-file",
            "branch": "work/operations/post-m13-preparse-test",
            "path": "docs/preparse-test.txt",
        },
        "expected": {
            "branchHead": "c" * 40,
            "blobSha": "d" * 40,
        },
        # Deliberately omit the required commit message.
        "payload": {"content": "x\n"},
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


def event_for(command: dict, *, body: str | None = None) -> dict:
    if body is None:
        body = issue_adapter.REQUEST_MARKER + "\n" + json.dumps(command)
    return {
        "repository": {"full_name": "EAKerber/MobiliPresenter"},
        "issue": {"number": 145, "title": issue_adapter.BUS_TITLE},
        "comment": {
            "id": 101,
            "author_association": "OWNER",
            "body": body,
        },
    }


def manifest() -> dict:
    return {
        "source": {
            "runId": BEGIN["runId"],
            "sourceSha": BEGIN["sourceSha"],
            "issueNumber": 145,
            "commentId": 100,
        },
        "contextHash": BEGIN["contextHash"],
        "actor": copy.deepcopy(ACTOR),
    }


def owner_comment(comment_id: int, marker: str, payload: dict) -> dict:
    return {
        "id": comment_id,
        "author_association": "OWNER",
        "user": {"login": "EAKerber"},
        "body": marker + "\n" + json.dumps(payload),
    }


def bot_comment(comment_id: int, marker: str, payload: dict) -> dict:
    return {
        "id": comment_id,
        "author_association": "NONE",
        "user": {"login": "github-actions[bot]"},
        "body": marker + "\n```json\n" + json.dumps(payload) + "\n```",
    }


def failure_for(command: dict) -> dict:
    core = {
        "schemaVersion": issue_adapter.FAILURE_SCHEMA,
        "executionId": command["executionId"],
        "commandHash": stable_hash(command),
        "status": "BLOCKED",
        "blockers": ["REMOTE_COMMAND_PAYLOAD_INVALID"],
        "detail": "REMOTE_COMMAND_PAYLOAD_INVALID",
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**core, "failureHash": stable_hash(core)}


class RemoteCanonicalPreparseCorrelationPostM13Tests(unittest.TestCase):
    def test_public_parse_event_still_rejects_semantically_invalid_command(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "REMOTE_COMMAND_PAYLOAD_INVALID"):
            issue_adapter.parse_event(event_for(invalid_remote_command()))

    def test_main_failure_preserves_raw_command_identity_after_json_parse(self) -> None:
        command = invalid_remote_command()
        with tempfile.TemporaryDirectory() as directory:
            event_path = Path(directory) / "event.json"
            output_path = Path(directory) / "result.json"
            event_path.write_text(json.dumps(event_for(command)), encoding="utf-8")

            status = issue_adapter.main(
                ["--event", str(event_path), "--output", str(output_path)]
            )
            payload = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(status, 2)
        self.assertEqual(payload["schemaVersion"], issue_adapter.FAILURE_SCHEMA)
        self.assertEqual(payload["executionId"], command["executionId"])
        self.assertEqual(payload["commandHash"], stable_hash(command))
        self.assertEqual(payload["status"], "BLOCKED")
        self.assertEqual(payload["blockers"], ["REMOTE_COMMAND_PAYLOAD_INVALID"])
        core = {key: value for key, value in payload.items() if key != "failureHash"}
        self.assertEqual(payload["failureHash"], stable_hash(core))

    def test_trace_pairs_correlated_preparse_failure_as_terminal_blocked(self) -> None:
        command = invalid_remote_command()
        failure = failure_for(command)
        comments = [
            {
                "id": 100,
                "author_association": "OWNER",
                "user": {"login": "EAKerber"},
                "body": "begin",
            },
            owner_comment(110, trace_collect.REMOTE_REQUEST_MARKER, command),
            bot_comment(120, trace_collect.REMOTE_RESULT_MARKER, failure),
            {
                "id": 200,
                "author_association": "OWNER",
                "user": {"login": "EAKerber"},
                "body": "close",
            },
        ]

        value = trace_collect.build_trace(comments, manifest(), close_comment_id=200)

        self.assertEqual(value["traceStatus"], "PASS")
        self.assertEqual(
            value["summary"],
            {
                "attemptCount": 1,
                "matchedCount": 1,
                "passCount": 0,
                "blockedCount": 1,
                "unknownCount": 0,
            },
        )
        self.assertEqual(value["attempts"][0]["status"], "BLOCKED")
        self.assertTrue(value["attempts"][0]["matched"])
        self.assertEqual(value["attempts"][0]["resultCommentId"], 120)
        self.assertEqual(
            value["attempts"][0]["blockers"],
            ["REMOTE_COMMAND_PAYLOAD_INVALID"],
        )
        self.assertEqual(trace_collect.remote_evidence_comment_ids(value), [])

    def test_unparseable_command_json_does_not_invent_command_identity(self) -> None:
        command = invalid_remote_command()
        body = issue_adapter.REQUEST_MARKER + "\n{"
        with tempfile.TemporaryDirectory() as directory:
            event_path = Path(directory) / "event.json"
            output_path = Path(directory) / "result.json"
            event_path.write_text(
                json.dumps(event_for(command, body=body)), encoding="utf-8"
            )

            status = issue_adapter.main(
                ["--event", str(event_path), "--output", str(output_path)]
            )
            payload = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(status, 2)
        self.assertEqual(payload["blockers"], ["REMOTE_TRANSPORT_JSON_INVALID"])
        self.assertIsNone(payload["executionId"])
        self.assertIsNone(payload["commandHash"])


if __name__ == "__main__":
    unittest.main()
