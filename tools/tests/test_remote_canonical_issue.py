from __future__ import annotations

import json
import unittest

from tools import remote_canonical_execution as bridge
from tools import remote_canonical_issue as issue_adapter
from tools.canonical import stable_hash

ACTOR = {
    "role": "manager-gitops",
    "workerId": "manager-gitops-primary",
    "sessionId": "rp1b-issue-test",
}


def command():
    return {
        "schemaVersion": bridge.COMMAND_SCHEMA,
        "executionId": "rp1b-issue-command",
        "kind": "git-direct",
        "actor": ACTOR,
        "declaredIntent": {"goal": "transport-only qualification"},
        "target": {
            "operation": "create-branch",
            "branch": "work/operations/rp1b-issue-test",
        },
        "expected": {"baseSha": "a" * 40},
        "payload": {},
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


def event(*, association="OWNER", title=issue_adapter.BUS_TITLE, pull_request=False, body=None):
    issue = {"number": 17, "title": title}
    if pull_request:
        issue["pull_request"] = {"url": "https://example.invalid/pr/17"}
    return {
        "repository": {"full_name": "EAKerber/MobiliPresenter"},
        "issue": issue,
        "comment": {
            "id": 23,
            "author_association": association,
            "body": body
            if body is not None
            else issue_adapter.REQUEST_MARKER + "\n" + json.dumps(command()),
        },
    }


class RemoteCanonicalIssueTests(unittest.TestCase):
    def test_owner_comment_on_exact_bus_parses_closed_command(self):
        parsed, meta = issue_adapter.parse_event(event())
        self.assertEqual(parsed, command())
        self.assertEqual(meta, {"issueNumber": 17, "commentId": 23})

    def test_non_owner_comment_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "ACTOR_FORBIDDEN"):
            issue_adapter.parse_event(event(association="MEMBER"))

    def test_pull_request_comment_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "PR_COMMENT_FORBIDDEN"):
            issue_adapter.parse_event(event(pull_request=True))

    def test_wrong_bus_title_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "BUS_MISMATCH"):
            issue_adapter.parse_event(event(title="Another issue"))

    def test_result_comment_cannot_reenter_request_path(self):
        body = issue_adapter.RESULT_MARKER + "\n{}"
        with self.assertRaisesRegex(RuntimeError, "MARKER_INVALID"):
            issue_adapter.parse_event(event(body=body))

    def test_failure_payload_is_non_authoritative_and_hash_bound(self):
        payload = issue_adapter.failure_payload(
            bridge.RemoteCanonicalExecutionError("EXPECTED_BLOCKER"), command()
        )
        self.assertEqual(payload["status"], "BLOCKED")
        self.assertEqual(payload["blockers"], ["EXPECTED_BLOCKER"])
        self.assertFalse(payload["semanticAuthority"])
        self.assertFalse(payload["authorizesMutation"])
        core = {key: value for key, value in payload.items() if key != "failureHash"}
        self.assertEqual(payload["failureHash"], stable_hash(core))


if __name__ == "__main__":
    unittest.main()
