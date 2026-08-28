from __future__ import annotations

import copy
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tools import agent_write_lifecycle as lifecycle
from tools import agent_write_lifecycle_host as host
from tools.canonical import stable_hash


BRANCH = "work/operations/at3c-host-test"
ACTOR = {
    "role": "manager-gitops",
    "workerId": "manager-gitops-a",
    "sessionId": "session-at3c-host",
}
BEGIN = {
    "runId": 123,
    "sourceSha": "a" * 40,
    "contextHash": "b" * 64,
}
CYCLE_INSTANCE_ID = "cycle-instance-" + "7" * 24


def acquire_request() -> dict:
    return {
        "schemaVersion": lifecycle.REQUEST_SCHEMA,
        "requestId": "request-acquire-host",
        "action": "acquire",
        "begin": copy.deepcopy(BEGIN),
        "actor": copy.deepcopy(ACTOR),
        "branch": BRANCH,
        "expectedAuthorityHead": "c" * 40,
        "expectedBranchHead": "d" * 40,
        "expectedBindingHash": None,
        "ttlSeconds": 3600,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


def minimal_dispatch() -> dict:
    return {
        "requestHash": "1" * 64,
        "dispatchHash": "2" * 64,
        "begin": copy.deepcopy(BEGIN),
        "actor": copy.deepcopy(ACTOR),
        "branch": BRANCH,
        "authorityHead": "c" * 40,
        "source": {
            "issueNumber": 145,
            "requestCommentId": 900,
            "hostedRunId": 456,
            "semanticHostSha": "a" * 40,
        },
        "command": {},
    }


def bundle() -> dict:
    return {
        "request": acquire_request(),
        "dispatch": minimal_dispatch(),
        "context": {},
        "manifest": {},
    }


def attempt(dispatch: dict, *, run_id: int = 900) -> dict:
    core = {
        "schemaVersion": lifecycle.ATTEMPT_SCHEMA,
        "dispatchHash": dispatch["dispatchHash"],
        "requestHash": dispatch["requestHash"],
        "runId": run_id,
        "hostSha": dispatch["source"]["semanticHostSha"],
        "status": "STARTED",
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**core, "attemptHash": stable_hash(core)}


def bot_comment(marker: str, payload: dict, *, comment_id: int = 500) -> dict:
    return {
        "id": comment_id,
        "user": {"login": "github-actions[bot]"},
        "body": marker + "\n```json\n" + json.dumps(payload) + "\n```",
    }


class FakeTransport:
    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    def request(self, method: str, endpoint: str, *, payload=None, include_headers=False):
        self.calls.append((method.upper(), endpoint))
        return SimpleNamespace(body="{}")


class AgentWriteLifecycleHostTests(unittest.TestCase):
    @patch("tools.agent_write_lifecycle.validate_begin_binding")
    @patch("tools.agent_write_lifecycle.git_observation.observe_branch")
    def test_missing_target_branch_fails_before_coordination_observation(self, observe_branch, validate_begin):
        observe_branch.side_effect = RuntimeError("GIT_BRANCH_NOT_FOUND")
        with patch("tools.agent_write_lifecycle.GitHubCoordinationAuthority") as authority:
            with self.assertRaisesRegex(RuntimeError, "GIT_BRANCH_NOT_FOUND"):
                lifecycle.prepare_dispatch(
                    acquire_request(),
                    {},
                    {},
                    issue_number=145,
                    request_comment_id=900,
                    hosted_run_id=456,
                    transport=object(),
                )
            authority.assert_not_called()

    @patch("tools.agent_write_lifecycle.validate_begin_binding")
    @patch("tools.agent_write_lifecycle.git_observation.observe_branch")
    def test_stale_target_branch_head_fails_before_coordination_observation(self, observe_branch, validate_begin):
        observe_branch.return_value = {"branchHead": "9" * 40}
        with patch("tools.agent_write_lifecycle.GitHubCoordinationAuthority") as authority:
            with self.assertRaisesRegex(RuntimeError, "AGENT_WRITE_LIFECYCLE_BRANCH_DRIFT"):
                lifecycle.prepare_dispatch(
                    acquire_request(),
                    {},
                    {},
                    issue_number=145,
                    request_comment_id=900,
                    hosted_run_id=456,
                    transport=object(),
                )
            authority.assert_not_called()

    @patch("tools.agent_write_lifecycle.validate_begin_binding")
    @patch("tools.agent_write_lifecycle.git_observation.observe_branch", return_value={"branchHead": "d" * 40})
    def test_stale_coordination_head_fails_before_lifecycle_planning(self, observe_branch, validate_begin):
        observed = SimpleNamespace(head_sha="8" * 40)
        fake_authority = SimpleNamespace(observe=lambda: observed)
        with (
            patch("tools.agent_write_lifecycle.GitHubCoordinationAuthority", return_value=fake_authority),
            patch("tools.agent_write_lifecycle._prepare_previous_binding") as prepare_binding,
        ):
            with self.assertRaisesRegex(RuntimeError, "AGENT_WRITE_LIFECYCLE_AUTHORITY_DRIFT"):
                lifecycle.prepare_dispatch(
                    acquire_request(),
                    {},
                    {},
                    issue_number=145,
                    request_comment_id=900,
                    hosted_run_id=456,
                    transport=object(),
                )
            prepare_binding.assert_not_called()

    @patch("tools.agent_write_lifecycle_host._validate_bundle")
    @patch("tools.agent_write_lifecycle_host._comments")
    def test_prior_attempt_without_terminal_is_unknown_and_not_replayed(self, comments, validate_bundle):
        value = bundle()
        comments.return_value = [
            bot_comment(lifecycle.ATTEMPT_MARKER, attempt(value["dispatch"]))
        ]
        result = host.inspect_protocol(
            value,
            host_sha="a" * 40,
            hosted_run_id=456,
            run_id=901,
            transport=FakeTransport(),
        )
        self.assertEqual("PRIOR_ATTEMPT_UNKNOWN", result["state"])
        self.assertEqual("UNKNOWN", result["terminal"]["status"])
        self.assertIn(
            "AGENT_WRITE_LIFECYCLE_PRIOR_ATTEMPT_WITHOUT_TERMINAL",
            result["terminal"]["blockers"],
        )

    @patch("tools.agent_write_lifecycle_host._validate_bundle")
    @patch("tools.agent_write_lifecycle_host._comments")
    def test_same_request_hash_prior_attempt_fences_even_when_dispatch_changed(self, comments, validate_bundle):
        value = bundle()
        prior_dispatch = copy.deepcopy(value["dispatch"])
        prior_dispatch["dispatchHash"] = "8" * 64
        prior_dispatch["source"]["requestCommentId"] = 899
        prior_dispatch["source"]["hostedRunId"] = 455
        comments.return_value = [
            bot_comment(lifecycle.ATTEMPT_MARKER, attempt(prior_dispatch, run_id=899))
        ]
        result = host.inspect_protocol(
            value,
            host_sha="a" * 40,
            hosted_run_id=456,
            run_id=901,
            transport=FakeTransport(),
        )
        self.assertEqual("PRIOR_ATTEMPT_UNKNOWN", result["state"])
        self.assertEqual("UNKNOWN", result["terminal"]["status"])

    @patch("tools.agent_write_lifecycle.validate_begin_binding")
    @patch("tools.agent_write_lifecycle._prepare_previous_binding", return_value=(None, None))
    @patch("tools.agent_write_lifecycle.git_observation.observe_branch")
    def test_same_request_id_with_changed_precondition_gets_distinct_transition_identity(
        self, observe_branch, prepare_previous, validate_begin
    ):
        first = acquire_request()
        second = copy.deepcopy(first)
        second["expectedBranchHead"] = "e" * 40
        observe_branch.side_effect = [
            {"branchHead": first["expectedBranchHead"]},
            {"branchHead": second["expectedBranchHead"]},
        ]
        authority_observation = SimpleNamespace(head_sha=first["expectedAuthorityHead"])
        authority = SimpleNamespace(observe=lambda: authority_observation)
        with patch("tools.agent_write_lifecycle.GitHubCoordinationAuthority", return_value=authority):
            first_dispatch = lifecycle.prepare_dispatch(
                first,
                {"cycleInstanceId": CYCLE_INSTANCE_ID},
                {},
                issue_number=145,
                request_comment_id=900,
                hosted_run_id=456,
                transport=object(),
            )
            second_dispatch = lifecycle.prepare_dispatch(
                second,
                {"cycleInstanceId": CYCLE_INSTANCE_ID},
                {},
                issue_number=145,
                request_comment_id=901,
                hosted_run_id=457,
                transport=object(),
            )
        first_hash = lifecycle.request_hash(first)
        second_hash = lifecycle.request_hash(second)
        self.assertNotEqual(first_hash, second_hash)
        self.assertEqual("agent-write-" + first_hash[:24], first_dispatch["command"]["executionId"])
        self.assertEqual("agent-write-" + second_hash[:24], second_dispatch["command"]["executionId"])
        self.assertNotEqual(
            first_dispatch["command"]["executionId"],
            second_dispatch["command"]["executionId"],
        )

    @patch("tools.agent_write_lifecycle_host._validate_bundle")
    @patch("tools.agent_write_lifecycle_host._comment")
    @patch("tools.agent_write_lifecycle.validate_attempt")
    def test_failure_after_mutable_call_is_unknown(self, validate_attempt, comment, validate_bundle):
        value = bundle()
        expected_attempt = attempt(value["dispatch"], run_id=901)
        comment.return_value = bot_comment(lifecycle.ATTEMPT_MARKER, expected_attempt)
        transport = FakeTransport()

        def ambiguous(command, *, source, transport):
            transport.request(
                "POST",
                "repos/EAKerber/MobiliPresenter/git/blobs",
                payload={"content": "x"},
            )
            raise RuntimeError("TRANSPORT_DROPPED_AFTER_WRITE")

        with (
            patch("tools.agent_write_lifecycle_host.remote_canonical_issue.execute_command", side_effect=ambiguous),
            patch("tools.agent_write_lifecycle_host.GitHubCoordinationAuthority", side_effect=RuntimeError("unavailable")),
        ):
            result = host.execute_dispatch(
                value,
                host_sha="a" * 40,
                hosted_run_id=456,
                run_id=901,
                attempt_comment_id=500,
                transport=transport,
            )
        self.assertEqual("UNKNOWN", result["status"])
        self.assertIn("TRANSPORT_DROPPED_AFTER_WRITE", result["blockers"])
        self.assertTrue(any(method == "POST" for method, _ in transport.calls))


if __name__ == "__main__":
    unittest.main()
