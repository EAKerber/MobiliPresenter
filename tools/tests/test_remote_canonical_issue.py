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
UI_ACTOR = {
    "role": "ui-ux",
    "workerId": "ui-ux-a",
    "sessionId": "m12-s2-ui-test",
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


def ui_command(
    *,
    operation="create-file",
    branch="experiment/ui/m12-s2-ui-ux",
    path="viewer-next/src/ui/__m12_s2_probe__/scheduled-write.json",
):
    target = {"operation": operation, "branch": branch}
    expected = {}
    payload = {}
    if operation == "create-branch":
        expected = {"baseSha": "a" * 40}
    else:
        target["path"] = path
        if operation == "create-file":
            expected = {"branchHead": "a" * 40}
            payload = {"content": "{}\n", "message": "M12-S2 UI write probe"}
        elif operation == "update-file":
            expected = {"branchHead": "a" * 40, "blobSha": "b" * 40}
            payload = {"content": "{}\n", "message": "M12-S2 UI update probe"}
        else:
            expected = {"branchHead": "a" * 40, "blobSha": "b" * 40}
            payload = {"message": "M12-S2 UI delete probe"}
    return {
        "schemaVersion": bridge.COMMAND_SCHEMA,
        "executionId": f"m12-s2-ui-{operation}",
        "kind": "git-direct",
        "actor": UI_ACTOR,
        "declaredIntent": {"goal": "bounded role-scoped UI mutation"},
        "target": target,
        "expected": expected,
        "payload": payload,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


def ui_domain_command():
    return {
        "schemaVersion": bridge.COMMAND_SCHEMA,
        "executionId": "m12-s2-ui-domain-forbidden",
        "kind": "domain",
        "actor": UI_ACTOR,
        "declaredIntent": {"goal": "must remain forbidden"},
        "target": {
            "domain": "continuation",
            "action": "create",
            "subject": {"kind": "continuation", "id": "ui-forbidden"},
        },
        "expected": {"authorityRevision": "a" * 40},
        "payload": {},
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


def event(
    *,
    association="OWNER",
    title=issue_adapter.BUS_TITLE,
    pull_request=False,
    body=None,
    command_value=None,
):
    issue = {"number": 17, "title": title}
    if pull_request:
        issue["pull_request"] = {"url": "https://example.invalid/pr/17"}
    if body is None:
        body = issue_adapter.REQUEST_MARKER + "\n" + json.dumps(command_value or command())
    return {
        "repository": {"full_name": "EAKerber/MobiliPresenter"},
        "issue": issue,
        "comment": {
            "id": 23,
            "author_association": association,
            "body": body,
        },
    }


class RemoteCanonicalIssueTests(unittest.TestCase):
    def test_owner_comment_on_exact_bus_parses_closed_command(self):
        parsed, meta = issue_adapter.parse_event(event())
        self.assertEqual(parsed, command())
        self.assertEqual(meta, {"issueNumber": 17, "commentId": 23})

    def test_ui_role_can_use_confined_git_file_route(self):
        value = ui_command()
        parsed, meta = issue_adapter.parse_event(event(command_value=value))
        self.assertEqual(parsed, value)
        self.assertEqual(meta, {"issueNumber": 17, "commentId": 23})

    def test_ui_role_cannot_use_domain_route(self):
        with self.assertRaisesRegex(RuntimeError, "ROLE_ROUTE_FORBIDDEN"):
            issue_adapter.parse_event(event(command_value=ui_domain_command()))

    def test_ui_role_cannot_create_branch(self):
        with self.assertRaisesRegex(RuntimeError, "ROLE_OPERATION_FORBIDDEN"):
            issue_adapter.parse_event(event(command_value=ui_command(operation="create-branch")))

    def test_ui_role_cannot_write_non_ui_branch(self):
        with self.assertRaisesRegex(RuntimeError, "ROLE_BRANCH_FORBIDDEN"):
            issue_adapter.parse_event(
                event(command_value=ui_command(branch="work/operations/m12-s2-ui-escape"))
            )

    def test_ui_role_cannot_write_outside_owned_path(self):
        with self.assertRaisesRegex(RuntimeError, "ROLE_PATH_FORBIDDEN"):
            issue_adapter.parse_event(
                event(command_value=ui_command(path="viewer-next/src/runtime/escape.json"))
            )

    def test_unknown_role_is_rejected(self):
        value = ui_command()
        value["actor"] = {
            "role": "engine",
            "workerId": "engine-a",
            "sessionId": "unknown-role-test",
        }
        with self.assertRaisesRegex(RuntimeError, "ROLE_UNSUPPORTED"):
            issue_adapter.parse_event(event(command_value=value))

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
