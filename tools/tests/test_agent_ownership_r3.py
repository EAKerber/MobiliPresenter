from __future__ import annotations

import copy
import json
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from tools import agent_ownership, coordination


BRANCH = "work/operations/r3-ownership-test"
ACTOR = {
    "role": "manager-gitops",
    "workerId": "manager-gitops-chat",
    "sessionId": "session-r3-ownership",
}
BEGIN = {
    "runId": 123,
    "sourceSha": "a" * 40,
    "contextHash": "b" * 64,
}
CYCLE_INSTANCE_ID = "cycle-instance-" + "7" * 24
LOCATOR = {
    "runId": BEGIN["runId"],
    "sourceSha": BEGIN["sourceSha"],
    "contextHash": BEGIN["contextHash"],
    "issueNumber": 145,
}
HANDLE = {"opaque": "test"}
HANDLE_VALUE = {
    "actor": copy.deepcopy(ACTOR),
    "cycleInstanceId": CYCLE_INSTANCE_ID,
}
NOW = datetime(2026, 9, 15, 0, 15, tzinfo=timezone.utc)


def owner() -> dict:
    return {
        "role": ACTOR["role"],
        "session": ACTOR["sessionId"],
        "branch": BRANCH,
        "pr": None,
    }


def lease(*, lease_id: str = "lease-r3", expires_at: str = "2026-09-15T01:15:00Z") -> dict:
    return {
        "leaseId": lease_id,
        "resource": f"branch:{BRANCH}",
        "mode": "exclusive-write",
        "owner": owner(),
        "reason": "r3 test",
        "acquiredAt": "2026-09-15T00:00:00Z",
        "renewedAt": "2026-09-15T00:00:00Z",
        "expiresAt": expires_at,
        "ttlSeconds": 3600,
    }


def binding(*, state: str = "ACTIVE", expires_at: str | None = "2026-09-15T01:15:00Z") -> dict:
    return {
        "state": state,
        "leaseId": "lease-r3",
        "bindingHash": "c" * 64,
        "expiresAt": expires_at if state == "ACTIVE" else None,
    }


def result(current: dict) -> dict:
    return {
        "schemaVersion": "AgentWriteLeaseResult 0.1",
        "begin": copy.deepcopy(BEGIN),
        "actor": copy.deepcopy(ACTOR),
        "cycleInstanceId": CYCLE_INSTANCE_ID,
        "branch": BRANCH,
        "binding": copy.deepcopy(current),
    }


def comment_for(current: dict) -> dict:
    payload = result(current)
    return {
        "id": 500,
        "user": {"login": "github-actions[bot]"},
        "body": (
            "MOBILIPRESENTER_AGENT_WRITE_LEASE_RESULT_V0_1\n```json\n"
            + json.dumps(payload)
            + "\n```"
        ),
    }


def observation(leases: list[dict]) -> SimpleNamespace:
    return SimpleNamespace(
        state={
            "schemaVersion": coordination.SCHEMA_VERSION,
            "revision": None,
            "intents": [],
            "leases": copy.deepcopy(leases),
        },
        authority_now=NOW,
        head_sha="d" * 40,
    )


class FakeAuthority:
    def __init__(self, value: SimpleNamespace):
        self.value = value

    def observe(self) -> SimpleNamespace:
        return self.value


class FakeTransport:
    def __init__(self, comments: list[dict], *, posted_comment_id: int = 900):
        self.comments = copy.deepcopy(comments)
        self.posted_comment_id = posted_comment_id
        self.posts: list[dict] = []

    def request(self, method: str, endpoint: str, *, payload=None, include_headers=False):
        del include_headers
        if method.upper() == "GET" and "/comments?" in endpoint:
            return SimpleNamespace(body=json.dumps(self.comments))
        if method.upper() == "POST" and endpoint.endswith("/comments"):
            self.posts.append(copy.deepcopy(payload))
            return SimpleNamespace(body=json.dumps({"id": self.posted_comment_id}))
        raise AssertionError((method, endpoint, payload))


class AgentOwnershipR3Tests(unittest.TestCase):
    def run_ensure(
        self,
        *,
        comments: list[dict],
        leases: list[dict],
        expired: bool = False,
        submit: bool = False,
    ) -> tuple[dict, FakeTransport]:
        transport = FakeTransport(comments)
        with (
            patch.object(
                agent_ownership.hosted_cycle_handle,
                "decode_handle",
                return_value=(copy.deepcopy(HANDLE_VALUE), copy.deepcopy(LOCATOR)),
            ),
            patch.object(
                agent_ownership.git_observation,
                "observe_branch",
                return_value={"branchHead": "e" * 40},
            ),
            patch.object(
                agent_ownership,
                "GitHubCoordinationAuthority",
                return_value=FakeAuthority(observation(leases)),
            ),
            patch.object(
                agent_ownership.lifecycle,
                "validate_result",
                side_effect=lambda value: value,
            ),
            patch.object(
                agent_ownership.lifecycle,
                "binding_is_expired",
                return_value=expired,
            ),
        ):
            value = agent_ownership.ensure_ownership(
                handle=HANDLE,
                branch=BRANCH,
                request_id="r3-ensure-test",
                submit=submit,
                transport=transport,
            )
        return value, transport

    def test_absent_lineage_derives_existing_acquire_request(self) -> None:
        value, transport = self.run_ensure(comments=[], leases=[])

        self.assertEqual("PENDING", value["status"])
        self.assertEqual("ACQUIRE_REQUESTED", value["disposition"])
        request = value["request"]
        self.assertEqual("HostedAgentWriteLeaseRequest 0.2", request["schemaVersion"])
        self.assertEqual("acquire", request["action"])
        self.assertEqual("d" * 40, request["expectedAuthorityHead"])
        self.assertEqual("e" * 40, request["expectedBranchHead"])
        self.assertIsNone(request["expectedBindingHash"])
        self.assertEqual(coordination.DEFAULT_TTL_SECONDS, request["ttlSeconds"])
        self.assertEqual([], transport.posts)

    def test_active_exact_ownership_is_reused_without_mutation(self) -> None:
        current = binding()
        value, transport = self.run_ensure(
            comments=[comment_for(current)],
            leases=[lease()],
        )

        self.assertEqual("PASS", value["status"])
        self.assertEqual("REUSED", value["disposition"])
        self.assertIsNone(value["request"])
        self.assertEqual(current["bindingHash"], value["bindingHash"])
        self.assertEqual("lease-r3", value["leaseId"])
        self.assertTrue(value["readOnly"])
        self.assertEqual([], transport.posts)

    def test_expired_materialized_binding_derives_exact_release(self) -> None:
        current = binding(expires_at="2026-09-15T00:10:00Z")
        value, _ = self.run_ensure(
            comments=[comment_for(current)],
            leases=[lease(expires_at="2026-09-15T00:10:00Z")],
            expired=True,
        )

        self.assertEqual("PENDING", value["status"])
        self.assertEqual("RELEASE_REQUESTED", value["disposition"])
        request = value["request"]
        self.assertEqual("release", request["action"])
        self.assertEqual(current["bindingHash"], request["expectedBindingHash"])
        self.assertIsNone(request["expectedBranchHead"])
        self.assertIsNone(request["ttlSeconds"])

    def test_released_binding_requires_new_cycle_instead_of_reacquire(self) -> None:
        current = binding(state="RELEASED", expires_at=None)
        value, transport = self.run_ensure(
            comments=[comment_for(current)],
            leases=[],
        )

        self.assertEqual("BLOCKED", value["status"])
        self.assertEqual("NEW_CYCLE_REQUIRED", value["disposition"])
        self.assertEqual(
            ["AGENT_OWNERSHIP_REACQUIRE_REQUIRES_NEW_CYCLE"],
            value["blockers"],
        )
        self.assertIsNone(value["request"])
        self.assertEqual([], transport.posts)

    def test_active_binding_without_exact_authority_lease_is_unknown(self) -> None:
        current = binding()
        value, transport = self.run_ensure(
            comments=[comment_for(current)],
            leases=[],
        )

        self.assertEqual("UNKNOWN", value["status"])
        self.assertEqual("UNKNOWN", value["disposition"])
        self.assertEqual(
            ["AGENT_OWNERSHIP_BINDING_AUTHORITY_MISMATCH"],
            value["blockers"],
        )
        self.assertEqual([], transport.posts)

    def test_submit_posts_only_existing_v02_request_marker(self) -> None:
        value, transport = self.run_ensure(comments=[], leases=[], submit=True)

        self.assertEqual("PENDING", value["status"])
        self.assertEqual(900, value["requestCommentId"])
        self.assertEqual(1, len(transport.posts))
        body = transport.posts[0]["body"]
        self.assertTrue(body.startswith("MOBILIPRESENTER_AGENT_WRITE_LEASE_REQUEST_V0_2\n"))
        payload = json.loads(body.split("\n", 1)[1])
        self.assertEqual("acquire", payload["action"])
        self.assertEqual("HostedAgentWriteLeaseRequest 0.2", payload["schemaVersion"])


if __name__ == "__main__":
    unittest.main()
