from __future__ import annotations

import copy
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from tools import agent_write_lifecycle as lifecycle
from tools import agent_write_lifecycle_guard as guard
from tools.canonical import stable_hash


BRANCH = "work/operations/at3c-lifecycle-test"
OTHER_BRANCH = "work/operations/at3c-other"
ACTOR = {
    "role": "manager-gitops",
    "workerId": "manager-gitops-a",
    "sessionId": "session-at3c",
}
BEGIN = {
    "runId": 123,
    "sourceSha": "a" * 40,
    "contextHash": "b" * 64,
}
CYCLE_INSTANCE_ID = "cycle-instance-" + "1" * 24


def request(action: str, *, binding_hash: str | None = None) -> dict:
    return {
        "schemaVersion": lifecycle.REQUEST_SCHEMA,
        "requestId": f"request-{action}",
        "action": action,
        "begin": copy.deepcopy(BEGIN),
        "actor": copy.deepcopy(ACTOR),
        "branch": BRANCH,
        "expectedAuthorityHead": "c" * 40,
        "expectedBranchHead": "d" * 40,
        "expectedBindingHash": binding_hash,
        "ttlSeconds": 3600 if action == "acquire" else None,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


def binding(
    *,
    state: str = "ACTIVE",
    lease_id: str = "lease-at3c",
    previous: str | None = None,
    expires_at: str | None = None,
) -> dict:
    if expires_at is None and state == "ACTIVE":
        expires_at = "2026-08-26T06:00:00Z"
    core = {
        "schemaVersion": lifecycle.BINDING_SCHEMA,
        "cycleInstanceId": CYCLE_INSTANCE_ID,
        "begin": copy.deepcopy(BEGIN),
        "actor": copy.deepcopy(ACTOR),
        "branch": BRANCH,
        "state": state,
        "leaseId": lease_id,
        "expiresAt": expires_at if state == "ACTIVE" else None,
        "previousBindingHash": previous,
        "authorityHead": "e" * 40,
        "dispatchHash": "f" * 64,
        "receiptHash": "0" * 64,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**core, "bindingHash": stable_hash(core)}


def lease(
    lease_id: str,
    resource: str,
    *,
    session: str = "session-at3c",
    owner_branch: str = BRANCH,
) -> dict:
    return {
        "leaseId": lease_id,
        "resource": resource,
        "mode": "exclusive-write",
        "owner": {
            "role": "manager-gitops",
            "session": session,
            "branch": owner_branch,
            "pr": None,
        },
        "reason": "test",
        "acquiredAt": "2026-08-26T03:00:00Z",
        "renewedAt": "2026-08-26T03:00:00Z",
        "expiresAt": "2026-08-26T06:00:00Z",
        "ttlSeconds": 3600,
    }


def manifest() -> dict:
    return {
        "source": {
            "runId": BEGIN["runId"],
            "sourceSha": BEGIN["sourceSha"],
            "commentId": 1,
        },
        "contextHash": BEGIN["contextHash"],
        "actor": copy.deepcopy(ACTOR),
        "cycleInstanceId": CYCLE_INSTANCE_ID,
    }


def observation(active_leases: list[dict]) -> SimpleNamespace:
    return SimpleNamespace(
        state={
            "schemaVersion": "CoordinationState 0.1",
            "revision": None,
            "intents": [],
            "leases": active_leases,
        },
        authority_now=datetime(2026, 8, 26, 4, 0, tzinfo=timezone.utc),
        head_sha="7" * 40,
    )


class FakeAuthority:
    def __init__(self, value: SimpleNamespace):
        self.value = value

    def observe(self) -> SimpleNamespace:
        return self.value


class AgentWriteLifecycleIdentityTests(unittest.TestCase):
    def test_acquire_requires_no_prior_binding_and_followups_require_exact_binding_hash(self) -> None:
        self.assertEqual("acquire", lifecycle.validate_request(request("acquire"))["action"])

        bad_acquire = request("acquire", binding_hash="1" * 64)
        with self.assertRaisesRegex(RuntimeError, "AGENT_WRITE_LIFECYCLE_PRIOR_BINDING_FORBIDDEN"):
            lifecycle.validate_request(bad_acquire)

        for action in ("renew", "release"):
            with self.assertRaisesRegex(RuntimeError, "AGENT_WRITE_LIFECYCLE_PRIOR_BINDING_REQUIRED"):
                lifecycle.validate_request(request(action))
            value = request(action, binding_hash="2" * 64)
            self.assertEqual("2" * 64, lifecycle.validate_request(value)["expectedBindingHash"])

    def test_released_binding_preserves_lease_identity_and_lineage(self) -> None:
        value = binding(state="RELEASED", lease_id="lease-at3c", previous="3" * 64)
        validated = lifecycle.validate_binding(value)
        self.assertEqual("RELEASED", validated["state"])
        self.assertEqual("lease-at3c", validated["leaseId"])
        self.assertEqual("3" * 64, validated["previousBindingHash"])

        tampered = copy.deepcopy(value)
        tampered["leaseId"] = None
        with self.assertRaisesRegex(RuntimeError, "AGENT_WRITE_LIFECYCLE_BINDING_INVALID"):
            lifecycle.validate_binding(tampered)

    def test_exact_guard_match_ignores_unrelated_same_session_lease(self) -> None:
        current = binding()
        exact = lease("lease-at3c", f"branch:{BRANCH}")
        unrelated = lease(
            "lease-unrelated",
            f"branch:{OTHER_BRANCH}",
            owner_branch=OTHER_BRANCH,
        )
        matches = guard._matching_exact_leases([exact, unrelated], binding=current)
        self.assertEqual(["lease-at3c"], [item["leaseId"] for item in matches])

    def test_release_preparation_accepts_unrelated_same_session_lease_but_renew_blocks(self) -> None:
        current = binding()
        exact = lease("lease-at3c", f"branch:{BRANCH}")
        unrelated = lease(
            "lease-unrelated",
            f"branch:{OTHER_BRANCH}",
            owner_branch=OTHER_BRANCH,
        )
        observed = observation([exact, unrelated])
        current_manifest = {"cycleInstanceId": current["cycleInstanceId"]}

        with patch.object(lifecycle, "_latest_binding_before", return_value=current):
            release_request = request("release", binding_hash=current["bindingHash"])
            previous, bound = lifecycle._prepare_previous_binding(
                release_request,
                current_manifest,
                observed,
                issue_number=145,
                request_comment_id=999,
                transport=object(),
            )
            self.assertEqual(current["bindingHash"], previous["bindingHash"])
            self.assertEqual("lease-at3c", bound["leaseId"])

            renew_request = request("renew", binding_hash=current["bindingHash"])
            with self.assertRaisesRegex(RuntimeError, "AGENT_WRITE_LIFECYCLE_RENEW_SCOPE_AMBIGUOUS"):
                lifecycle._prepare_previous_binding(
                    renew_request,
                    current_manifest,
                    observed,
                    issue_number=145,
                    request_comment_id=1000,
                    transport=object(),
                )

    def test_wrong_binding_hash_cannot_borrow_exact_lease(self) -> None:
        current = binding()
        exact = lease("lease-at3c", f"branch:{BRANCH}")
        observed = observation([exact])
        current_manifest = {"cycleInstanceId": current["cycleInstanceId"]}
        with patch.object(lifecycle, "_latest_binding_before", return_value=current):
            value = request("release", binding_hash="9" * 64)
            with self.assertRaisesRegex(RuntimeError, "AGENT_WRITE_LIFECYCLE_BINDING_DRIFT"):
                lifecycle._prepare_previous_binding(
                    value,
                    current_manifest,
                    observed,
                    issue_number=145,
                    request_comment_id=1001,
                    transport=object(),
                )

    def test_unbound_target_lease_is_distinct_from_unrelated_same_session_lease(self) -> None:
        target = lease("lease-target", f"branch:{BRANCH}")
        unrelated = lease(
            "lease-unrelated",
            f"branch:{OTHER_BRANCH}",
            owner_branch=OTHER_BRANCH,
        )
        found = guard._unbound_target_leases(
            [target, unrelated],
            manifest=manifest(),
            branches={BRANCH},
            bound_lease_id=None,
        )
        self.assertEqual(["lease-target"], [item["leaseId"] for item in found])

    def test_close_with_unbound_target_lease_is_unknown(self) -> None:
        target = lease("lease-target", f"branch:{BRANCH}")
        current_manifest = manifest()
        with (
            patch.object(guard, "_bound_results", return_value=[]),
            patch.object(guard, "_request_count", return_value=0),
            patch.object(guard, "_bound_agent_tool_branches", return_value={BRANCH}),
            patch.object(guard, "GitHubCoordinationAuthority", return_value=FakeAuthority(observation([target]))),
        ):
            report = guard.inspect_cycle(
                [{"id": 1}, {"id": 2}],
                current_manifest,
                close_comment_id=2,
                transport=object(),
            )
        self.assertEqual("UNKNOWN", report["state"])
        self.assertIn("AGENT_WRITE_LIFECYCLE_UNBOUND_ACTIVE_LEASE", report["blockers"])

    def test_released_close_ignores_unrelated_same_session_lease(self) -> None:
        released = binding(state="RELEASED", previous="3" * 64)
        unrelated = lease(
            "lease-unrelated",
            f"branch:{OTHER_BRANCH}",
            owner_branch=OTHER_BRANCH,
        )
        current_manifest = manifest()
        with (
            patch.object(guard, "_bound_results", return_value=[(10, {"binding": released})]),
            patch.object(guard, "_request_count", return_value=2),
            patch.object(guard, "_bound_agent_tool_branches", return_value={BRANCH}),
            patch.object(guard, "GitHubCoordinationAuthority", return_value=FakeAuthority(observation([unrelated]))),
        ):
            report = guard.inspect_cycle(
                [{"id": 1}, {"id": 2}],
                current_manifest,
                close_comment_id=2,
                transport=object(),
            )
        self.assertEqual("RELEASED", report["state"])
        self.assertEqual([], report["blockers"])

    def test_active_and_expired_lifecycle_remain_visible_at_close(self) -> None:
        exact = lease("lease-at3c", f"branch:{BRANCH}")
        current_manifest = manifest()
        with (
            patch.object(guard, "_request_count", return_value=1),
            patch.object(guard, "_bound_agent_tool_branches", return_value={BRANCH}),
            patch.object(guard, "GitHubCoordinationAuthority", return_value=FakeAuthority(observation([exact]))),
        ):
            with patch.object(guard, "_bound_results", return_value=[(10, {"binding": binding()})]):
                active_report = guard.inspect_cycle(
                    [{"id": 1}, {"id": 2}],
                    current_manifest,
                    close_comment_id=2,
                    transport=object(),
                )
            self.assertEqual("ACTIVE", active_report["state"])
            self.assertIn("AGENT_WRITE_LIFECYCLE_ACTIVE_AT_CLOSE", active_report["blockers"])

        expired_binding = binding(expires_at="2026-08-26T03:30:00Z")
        with (
            patch.object(guard, "_bound_results", return_value=[(10, {"binding": expired_binding})]),
            patch.object(guard, "_request_count", return_value=1),
            patch.object(guard, "_bound_agent_tool_branches", return_value={BRANCH}),
            patch.object(guard, "GitHubCoordinationAuthority", return_value=FakeAuthority(observation([]))),
        ):
            expired_report = guard.inspect_cycle(
                [{"id": 1}, {"id": 2}],
                current_manifest,
                close_comment_id=2,
                transport=object(),
            )
        self.assertEqual("EXPIRED", expired_report["state"])
        self.assertEqual([], expired_report["blockers"])


if __name__ == "__main__":
    unittest.main()
