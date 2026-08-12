import base64
import copy
import json
import unittest
from datetime import datetime, timezone

from tools import coordination
from tools.coordination_remote import (
    ApiError,
    ApiResponse,
    CoordinationRemoteError,
    GhApiTransport,
    GitHubCoordinationAuthority,
)

HEAD0 = "1" * 40
HEAD1 = "2" * 40
HEAD_OTHER = "3" * 40
TREE0 = "4" * 40
TREE1 = "5" * 40
BLOB1 = "6" * 40
SERVER_DATE = "Wed, 12 Aug 2026 04:11:00 GMT"
NOW = datetime(2026, 8, 12, 4, 11, 0, tzinfo=timezone.utc)
OWNER = {"role": "ui", "session": "remote-test-ui", "branch": "ui/test", "pr": 32}


def json_response(payload, *, headers=None, status=200):
    return ApiResponse(status=status, headers=headers or {}, body=json.dumps(payload))


def state_response(state):
    encoded = base64.b64encode((json.dumps(state, indent=2) + "\n").encode("utf-8")).decode("ascii")
    return json_response({"encoding": "base64", "content": encoded})


class ScriptedTransport:
    def __init__(self, steps):
        self.steps = list(steps)
        self.calls = []

    def request(self, method, endpoint, *, payload=None, include_headers=False):
        self.calls.append(
            {
                "method": method,
                "endpoint": endpoint,
                "payload": copy.deepcopy(payload),
                "include_headers": include_headers,
            }
        )
        if not self.steps:
            raise AssertionError(f"unexpected request {method} {endpoint}")
        expected = self.steps.pop(0)
        self.assert_match(expected, method, endpoint, include_headers)
        result = expected[3]
        if isinstance(result, Exception):
            raise result
        return result

    @staticmethod
    def assert_match(expected, method, endpoint, include_headers):
        expected_method, endpoint_fragment, expected_include, _ = expected
        if method != expected_method:
            raise AssertionError(f"method {method!r} != {expected_method!r}")
        if endpoint_fragment not in endpoint:
            raise AssertionError(f"endpoint {endpoint!r} does not contain {endpoint_fragment!r}")
        if include_headers != expected_include:
            raise AssertionError(f"include_headers {include_headers!r} != {expected_include!r}")

    def assert_consumed(self):
        if self.steps:
            raise AssertionError(f"unused scripted steps: {len(self.steps)}")


def observation_steps(head, tree, state, *, date=SERVER_DATE):
    return [
        ("GET", "git/ref/heads/coordination%2Fleases", True, json_response({"object": {"sha": head}}, headers={"date": date})),
        ("GET", f"git/commits/{head}", False, json_response({"tree": {"sha": tree}})),
        ("GET", f"?ref={head}", False, state_response(state)),
    ]


class CoordinationRemoteTests(unittest.TestCase):
    def test_parse_gh_included_response(self):
        response = GhApiTransport._parse_included(
            "HTTP/2 200\r\nDate: Wed, 12 Aug 2026 04:11:00 GMT\r\nX-Test: yes\r\n\r\n{\"ok\":true}\n"
        )
        self.assertEqual(response.status, 200)
        self.assertEqual(response.headers["date"], SERVER_DATE)
        self.assertEqual(json.loads(response.body), {"ok": True})

    def test_observe_reads_state_by_exact_head_and_uses_server_time(self):
        state = coordination.empty_state()
        transport = ScriptedTransport(observation_steps(HEAD0, TREE0, state))
        authority = GitHubCoordinationAuthority(transport)

        observed = authority.observe()

        self.assertEqual(observed.head_sha, HEAD0)
        self.assertEqual(observed.tree_sha, TREE0)
        self.assertEqual(observed.state, state)
        self.assertEqual(observed.authority_now, NOW)
        self.assertIn(f"?ref={HEAD0}", transport.calls[2]["endpoint"])
        transport.assert_consumed()

    def test_missing_server_date_fails_closed_before_ttl_decision(self):
        transport = ScriptedTransport(
            [
                ("GET", "git/ref/heads/coordination%2Fleases", True, json_response({"object": {"sha": HEAD0}})),
            ]
        )
        authority = GitHubCoordinationAuthority(transport)

        with self.assertRaises(CoordinationRemoteError) as caught:
            authority.observe()

        self.assertEqual(caught.exception.code, "COORDINATION_TIME_UNAVAILABLE")
        transport.assert_consumed()

    def test_invalid_remote_state_fails_closed(self):
        invalid = coordination.empty_state()
        invalid["schemaVersion"] = "wrong"
        transport = ScriptedTransport(observation_steps(HEAD0, TREE0, invalid))
        authority = GitHubCoordinationAuthority(transport)

        with self.assertRaises(coordination.CoordinationError):
            authority.observe()

        transport.assert_consumed()

    def test_mutate_builds_single_parent_commit_force_false_and_readbacks(self):
        base_state = coordination.empty_state()
        planned, planned_event = coordination.plan_intent(
            base_state,
            ["file:ops/coordination/adapter-probe.shared"],
            OWNER,
            "remote adapter test",
            NOW,
            "remote-intent-1",
        )
        expected_state = copy.deepcopy(planned)
        expected_state["revision"] = HEAD0

        steps = observation_steps(HEAD0, TREE0, base_state)
        steps.extend(
            [
                ("POST", "git/blobs", False, json_response({"sha": BLOB1})),
                ("POST", "git/trees", False, json_response({"sha": TREE1})),
                ("POST", "git/commits", False, json_response({"sha": HEAD1})),
                ("PATCH", "git/refs/heads/coordination%2Fleases", False, json_response({"object": {"sha": HEAD1}})),
            ]
        )
        steps.extend(observation_steps(HEAD1, TREE1, expected_state))
        transport = ScriptedTransport(steps)
        authority = GitHubCoordinationAuthority(transport)
        seen_now = []

        def planner(state, authority_now):
            seen_now.append(authority_now)
            return coordination.plan_intent(
                state,
                ["file:ops/coordination/adapter-probe.shared"],
                OWNER,
                "remote adapter test",
                authority_now,
                "remote-intent-1",
            )

        result = authority.mutate(planner, message="coordination: adapter probe")

        self.assertEqual(seen_now, [NOW])
        self.assertEqual(result.before_sha, HEAD0)
        self.assertEqual(result.after_sha, HEAD1)
        self.assertEqual(result.state, expected_state)
        self.assertEqual(result.event, planned_event)
        commit_call = next(call for call in transport.calls if call["method"] == "POST" and call["endpoint"].endswith("git/commits"))
        self.assertEqual(commit_call["payload"]["parents"], [HEAD0])
        patch_call = next(call for call in transport.calls if call["method"] == "PATCH")
        self.assertEqual(patch_call["payload"], {"sha": HEAD1, "force": False})
        tree_call = next(call for call in transport.calls if call["method"] == "POST" and call["endpoint"].endswith("git/trees"))
        self.assertEqual(tree_call["payload"]["base_tree"], TREE0)
        self.assertEqual(tree_call["payload"]["tree"][0]["path"], "ops/coordination/leases.json")
        transport.assert_consumed()

    def test_non_fast_forward_is_explicit_ref_drift(self):
        base_state = coordination.empty_state()
        steps = observation_steps(HEAD0, TREE0, base_state)
        steps.extend(
            [
                ("POST", "git/blobs", False, json_response({"sha": BLOB1})),
                ("POST", "git/trees", False, json_response({"sha": TREE1})),
                ("POST", "git/commits", False, json_response({"sha": HEAD1})),
                ("PATCH", "git/refs/heads/coordination%2Fleases", False, ApiError(422, "Update is not a fast forward")),
            ]
        )
        transport = ScriptedTransport(steps)
        authority = GitHubCoordinationAuthority(transport)

        def planner(state, authority_now):
            return coordination.plan_acquire(
                state,
                ["file:ops/coordination/adapter-probe.shared"],
                OWNER,
                "remote adapter drift",
                authority_now,
                "remote-acquire-drift",
            )

        with self.assertRaises(CoordinationRemoteError) as caught:
            authority.mutate(planner, message="coordination: drift probe")

        self.assertEqual(caught.exception.code, "COORDINATION_REF_DRIFT")
        transport.assert_consumed()

    def test_readback_head_mismatch_is_not_reported_as_success(self):
        base_state = coordination.empty_state()
        planned, _ = coordination.plan_intent(
            base_state,
            ["file:ops/coordination/adapter-probe.shared"],
            OWNER,
            "readback mismatch",
            NOW,
            "remote-intent-mismatch",
        )
        candidate = copy.deepcopy(planned)
        candidate["revision"] = HEAD0

        steps = observation_steps(HEAD0, TREE0, base_state)
        steps.extend(
            [
                ("POST", "git/blobs", False, json_response({"sha": BLOB1})),
                ("POST", "git/trees", False, json_response({"sha": TREE1})),
                ("POST", "git/commits", False, json_response({"sha": HEAD1})),
                ("PATCH", "git/refs/heads/coordination%2Fleases", False, json_response({"object": {"sha": HEAD1}})),
            ]
        )
        steps.extend(observation_steps(HEAD_OTHER, TREE1, candidate))
        transport = ScriptedTransport(steps)
        authority = GitHubCoordinationAuthority(transport)

        def planner(state, authority_now):
            return coordination.plan_intent(
                state,
                ["file:ops/coordination/adapter-probe.shared"],
                OWNER,
                "readback mismatch",
                authority_now,
                "remote-intent-mismatch",
            )

        with self.assertRaises(CoordinationRemoteError) as caught:
            authority.mutate(planner, message="coordination: readback mismatch")

        self.assertEqual(caught.exception.code, "COORDINATION_READBACK_MISMATCH")
        transport.assert_consumed()

    def test_planner_must_return_objects(self):
        state = coordination.empty_state()
        transport = ScriptedTransport(observation_steps(HEAD0, TREE0, state))
        authority = GitHubCoordinationAuthority(transport)

        with self.assertRaises(CoordinationRemoteError) as caught:
            authority.mutate(lambda _state, _now: (None, None), message="invalid planner")

        self.assertEqual(caught.exception.code, "COORDINATION_PLANNER_INVALID")
        transport.assert_consumed()


if __name__ == "__main__":
    unittest.main()
