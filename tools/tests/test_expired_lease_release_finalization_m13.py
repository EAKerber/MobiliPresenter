from __future__ import annotations

import copy
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tools import agent_write_lifecycle as lifecycle
from tools import coordination
from tools.canonical import stable_hash


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "hosted-agent-write-lease.yml"
BRANCH = "work/operations/m13-expired-finalization-test"
ACTOR = {
    "role": "manager-gitops",
    "workerId": "m13-expired-finalization",
    "sessionId": "session-m13-expired-finalization",
}
BEGIN = {
    "runId": 123,
    "sourceSha": "a" * 40,
    "contextHash": "b" * 64,
}
CYCLE_INSTANCE_ID = "cycle-instance-" + "1" * 24
NOW = datetime(2026, 9, 6, 10, 0, tzinfo=timezone.utc)


def owner(*, session: str = ACTOR["sessionId"], branch: str = BRANCH) -> dict:
    return {
        "role": ACTOR["role"],
        "session": session,
        "branch": branch,
        "pr": None,
    }


def lease(
    lease_id: str,
    resource: str,
    *,
    session: str = ACTOR["sessionId"],
    branch: str = BRANCH,
    expires_at: str = "2026-09-06T09:00:00Z",
) -> dict:
    return {
        "leaseId": lease_id,
        "resource": resource,
        "mode": "exclusive-write",
        "owner": owner(session=session, branch=branch),
        "reason": "expired finalization test",
        "acquiredAt": "2026-09-06T07:00:00Z",
        "renewedAt": "2026-09-06T08:00:00Z",
        "expiresAt": expires_at,
        "ttlSeconds": 3600,
    }


def binding(*, lease_id: str = "lease-m13-expired") -> dict:
    core = {
        "schemaVersion": lifecycle.BINDING_SCHEMA,
        "cycleInstanceId": CYCLE_INSTANCE_ID,
        "begin": copy.deepcopy(BEGIN),
        "actor": copy.deepcopy(ACTOR),
        "branch": BRANCH,
        "state": "ACTIVE",
        "leaseId": lease_id,
        "expiresAt": "2026-09-06T09:00:00Z",
        "previousBindingHash": None,
        "authorityHead": "e" * 40,
        "dispatchHash": "f" * 64,
        "receiptHash": "0" * 64,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**core, "bindingHash": stable_hash(core)}


def request(action: str, current: dict) -> dict:
    return {
        "schemaVersion": lifecycle.REQUEST_SCHEMA,
        "requestId": f"m13-{action}",
        "action": action,
        "begin": copy.deepcopy(BEGIN),
        "actor": copy.deepcopy(ACTOR),
        "branch": BRANCH,
        "expectedAuthorityHead": "c" * 40,
        "expectedBranchHead": "d" * 40,
        "expectedBindingHash": current["bindingHash"],
        "ttlSeconds": None,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


def observation(entries: list[dict]) -> SimpleNamespace:
    return SimpleNamespace(
        state={
            "schemaVersion": coordination.SCHEMA_VERSION,
            "revision": None,
            "intents": [],
            "leases": copy.deepcopy(entries),
        },
        authority_now=NOW,
        head_sha="c" * 40,
    )


class CoordinationExpiredReleaseTests(unittest.TestCase):
    def test_exact_resource_release_finalizes_expired_target_without_compacting_unrelated(self) -> None:
        target = lease("lease-target", f"branch:{BRANCH}")
        other_branch = "work/operations/m13-unrelated-expired"
        unrelated = lease(
            "lease-unrelated",
            f"branch:{other_branch}",
            session="other-session",
            branch=other_branch,
        )
        state = {
            "schemaVersion": coordination.SCHEMA_VERSION,
            "revision": None,
            "intents": [],
            "leases": [target, unrelated],
        }

        candidate, event = coordination.plan_release(
            state,
            owner(),
            NOW,
            "release-expired-target",
            resources=[f"branch:{BRANCH}"],
        )

        self.assertEqual([unrelated], candidate["leases"])
        self.assertEqual([f"branch:{BRANCH}"], event["resources"])
        self.assertEqual("release", event["action"])

    def test_foreign_session_cannot_finalize_expired_exact_resource(self) -> None:
        target = lease("lease-target", f"branch:{BRANCH}")
        state = {
            "schemaVersion": coordination.SCHEMA_VERSION,
            "revision": None,
            "intents": [],
            "leases": [target],
        }
        with self.assertRaisesRegex(coordination.CoordinationError, "LEASE_NOT_OWNER"):
            coordination.plan_release(
                state,
                owner(session="other-session"),
                NOW,
                "release-expired-foreign",
                resources=[f"branch:{BRANCH}"],
            )


class LifecycleExpiredReleaseTests(unittest.TestCase):
    def test_release_binds_exact_materialized_expired_lease_but_renew_does_not(self) -> None:
        current = binding()
        expired = lease(current["leaseId"], f"branch:{BRANCH}")
        observed = observation([expired])
        manifest = {"cycleInstanceId": CYCLE_INSTANCE_ID}

        with patch.object(lifecycle, "_latest_binding_before", return_value=current):
            release_request = request("release", current)
            previous, bound = lifecycle._prepare_previous_binding(
                release_request,
                manifest,
                observed,
                issue_number=145,
                request_comment_id=100,
                transport=object(),
            )
            self.assertEqual(current["bindingHash"], previous["bindingHash"])
            self.assertEqual(current["leaseId"], bound["leaseId"])

            renew_request = request("renew", current)
            with self.assertRaisesRegex(
                RuntimeError,
                "AGENT_WRITE_LIFECYCLE_BOUND_LEASE_NOT_FOUND",
            ):
                lifecycle._prepare_previous_binding(
                    renew_request,
                    manifest,
                    observed,
                    issue_number=145,
                    request_comment_id=101,
                    transport=object(),
                )

    def test_release_still_requires_exact_lease_identity_owner_and_resource(self) -> None:
        current = binding()
        wrong_owner = lease(
            current["leaseId"],
            f"branch:{BRANCH}",
            session="other-session",
        )
        observed = observation([wrong_owner])
        with patch.object(lifecycle, "_latest_binding_before", return_value=current):
            with self.assertRaisesRegex(
                RuntimeError,
                "AGENT_WRITE_LIFECYCLE_BOUND_LEASE_NOT_FOUND",
            ):
                lifecycle._prepare_previous_binding(
                    request("release", current),
                    {"cycleInstanceId": CYCLE_INSTANCE_ID},
                    observed,
                    issue_number=145,
                    request_comment_id=102,
                    transport=object(),
                )


class HostedExpiredReleaseRecoveryWorkflowTests(unittest.TestCase):
    def test_recovery_is_post_failure_release_only_and_expired_only(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("Checkout exact begin semantic host", text)
        self.assertIn("ref: ${{ steps.parse.outputs.begin_source_sha }}", text)
        self.assertIn("Restore current carrier for expired release recovery", text)
        self.assertIn("steps.prepare.outcome != 'success'", text)
        self.assertIn("ref: ${{ github.sha }}", text)
        self.assertIn("if request.get('action') != 'release':", text)
        self.assertIn("HOSTED_AGENT_WRITE_LEASE_RECOVERY_RELEASE_ONLY", text)
        self.assertIn("lifecycle._matching_exact_leases", text)
        self.assertIn("coordination._is_expired", text)
        self.assertIn("HOSTED_AGENT_WRITE_LEASE_RECOVERY_LEASE_NOT_EXPIRED", text)
        self.assertIn("steps.prepare_recovery.outcome != 'success'", text)


if __name__ == "__main__":
    unittest.main()
