import json
import unittest
from datetime import datetime, timezone

from tools.coordination_remote import (
    ApiError,
    ApiResponse,
    CoordinationRemoteError,
    GitHubCoordinationAuthority,
)

HEAD0 = "1" * 40
HEAD1 = "2" * 40
HEAD_OTHER = "3" * 40
TREE0 = "4" * 40
TREE1 = "5" * 40
COMMIT_TIME = datetime(2026, 8, 12, 5, 0, 0, tzinfo=timezone.utc)
SERVER_DATE = "Wed, 12 Aug 2026 05:00:00 GMT"


def response(payload, *, headers=None):
    return ApiResponse(status=200, headers=headers or {}, body=json.dumps(payload))


class ScriptedTransport:
    def __init__(self, steps):
        self.steps = list(steps)
        self.calls = []

    def request(self, method, endpoint, *, payload=None, include_headers=False):
        self.calls.append((method, endpoint, payload, include_headers))
        if not self.steps:
            raise AssertionError(f"unexpected call {method} {endpoint}")
        expected_method, fragment, result = self.steps.pop(0)
        if method != expected_method or fragment not in endpoint:
            raise AssertionError(f"unexpected {method} {endpoint}; expected {expected_method} *{fragment}*")
        if isinstance(result, Exception):
            raise result
        return result

    def assert_consumed(self):
        if self.steps:
            raise AssertionError(f"unused steps: {len(self.steps)}")


class CoordinationTransientTests(unittest.TestCase):
    def test_read_commit_retries_transient_503(self):
        transport = ScriptedTransport(
            [
                ("GET", f"git/commits/{HEAD0}", ApiError(503, "temporary")),
                ("GET", f"git/commits/{HEAD0}", response({"tree": {"sha": TREE0}})),
            ]
        )
        authority = GitHubCoordinationAuthority(transport, transient_retry_seconds=0)
        self.assertEqual(authority._read_commit_tree(HEAD0), TREE0)
        transport.assert_consumed()

    def test_create_commit_retry_is_deterministic_after_504(self):
        transport = ScriptedTransport(
            [
                ("POST", "git/commits", ApiError(504, "gateway timeout")),
                ("POST", "git/commits", response({"sha": HEAD1})),
            ]
        )
        authority = GitHubCoordinationAuthority(transport, transient_retry_seconds=0)

        sha = authority._create_commit(HEAD0, TREE0, "coordination: deterministic retry", COMMIT_TIME)

        self.assertEqual(sha, HEAD1)
        self.assertEqual(len(transport.calls), 2)
        first_payload = transport.calls[0][2]
        second_payload = transport.calls[1][2]
        self.assertEqual(first_payload, second_payload)
        self.assertEqual(first_payload["parents"], [HEAD0])
        self.assertEqual(first_payload["author"], first_payload["committer"])
        self.assertEqual(first_payload["author"]["date"], "2026-08-12T05:00:00Z")
        self.assertEqual(first_payload["author"]["name"], "MobiliPresenter GitOps")
        transport.assert_consumed()

    def test_patch_504_is_accepted_when_candidate_is_already_visible(self):
        transport = ScriptedTransport(
            [
                ("PATCH", "git/refs/heads/coordination%2Fleases", ApiError(504, "ambiguous")),
                (
                    "GET",
                    "git/ref/heads/coordination%2Fleases",
                    response({"object": {"sha": HEAD1}}, headers={"date": SERVER_DATE}),
                ),
            ]
        )
        authority = GitHubCoordinationAuthority(
            transport,
            transient_retry_seconds=0,
            readback_retry_seconds=0,
        )
        authority._advance_ref(HEAD1, HEAD0)
        self.assertEqual(sum(1 for call in transport.calls if call[0] == "PATCH"), 1)
        transport.assert_consumed()

    def test_patch_504_retries_only_after_parent_remains_observed(self):
        transport = ScriptedTransport(
            [
                ("PATCH", "git/refs/heads/coordination%2Fleases", ApiError(504, "ambiguous")),
                (
                    "GET",
                    "git/ref/heads/coordination%2Fleases",
                    response({"object": {"sha": HEAD0}}, headers={"date": SERVER_DATE}),
                ),
                ("PATCH", "git/refs/heads/coordination%2Fleases", response({"object": {"sha": HEAD1}})),
            ]
        )
        authority = GitHubCoordinationAuthority(
            transport,
            transient_retry_seconds=0,
            readback_retry_seconds=0,
            readback_attempts=1,
            ref_update_attempts=2,
        )
        authority._advance_ref(HEAD1, HEAD0)
        self.assertEqual(sum(1 for call in transport.calls if call[0] == "PATCH"), 2)
        transport.assert_consumed()

    def test_patch_422_after_ambiguous_retry_detects_competing_history(self):
        transport = ScriptedTransport(
            [
                ("PATCH", "git/refs/heads/coordination%2Fleases", ApiError(504, "ambiguous")),
                (
                    "GET",
                    "git/ref/heads/coordination%2Fleases",
                    response({"object": {"sha": HEAD0}}, headers={"date": SERVER_DATE}),
                ),
                ("PATCH", "git/refs/heads/coordination%2Fleases", ApiError(422, "Update is not a fast forward")),
                (
                    "GET",
                    "git/ref/heads/coordination%2Fleases",
                    response({"object": {"sha": HEAD_OTHER}}, headers={"date": SERVER_DATE}),
                ),
                (
                    "GET",
                    f"compare/{HEAD1}...{HEAD_OTHER}",
                    response({"status": "diverged", "merge_base_commit": {"sha": HEAD0}}),
                ),
                (
                    "GET",
                    f"compare/{HEAD_OTHER}...{HEAD1}",
                    response({"status": "diverged", "merge_base_commit": {"sha": HEAD0}}),
                ),
            ]
        )
        authority = GitHubCoordinationAuthority(
            transport,
            transient_retry_seconds=0,
            readback_retry_seconds=0,
            readback_attempts=1,
            ref_update_attempts=2,
        )
        with self.assertRaises(CoordinationRemoteError) as caught:
            authority._advance_ref(HEAD1, HEAD0)
        self.assertEqual(caught.exception.code, "COORDINATION_REF_DRIFT")
        transport.assert_consumed()

    def test_transient_create_commit_exhaustion_remains_fail_closed(self):
        transport = ScriptedTransport(
            [
                ("POST", "git/commits", ApiError(504, "one")),
                ("POST", "git/commits", ApiError(504, "two")),
            ]
        )
        authority = GitHubCoordinationAuthority(
            transport,
            transient_attempts=2,
            transient_retry_seconds=0,
        )
        with self.assertRaises(ApiError) as caught:
            authority._create_commit(HEAD0, TREE0, "coordination: fail closed", COMMIT_TIME)
        self.assertEqual(caught.exception.status, 504)
        transport.assert_consumed()


if __name__ == "__main__":
    unittest.main()
