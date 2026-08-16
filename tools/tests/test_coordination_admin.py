import copy
import unittest
from datetime import datetime, timezone

from tools import coordination
from tools.coordination_admin import apply_break_glass
from tools.coordination_remote import AuthorityObservation, CoordinationRemoteError

NOW = datetime(2026, 8, 12, 5, 10, 0, tzinfo=timezone.utc)
HEAD0 = "1" * 40
TREE0 = "2" * 40
ADMIN = {"role": "gitops", "session": "admin-1", "branch": "ops/admin", "pr": 32}
TARGET = {"role": "engine", "session": "engine-1", "branch": "engine/live", "pr": 44}
FOREIGN = {"role": "ui", "session": "ui-1", "branch": "ui/live", "pr": 45}


class DelegatingAuthority:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def mutate(self, planner, *, message, expected_revision=None):
        self.calls.append({"message": message, "expectedRevision": expected_revision})
        if self.error is not None:
            raise self.error
        raise AssertionError("successful mutation not expected in this test")


class CoordinationAdminTests(unittest.TestCase):
    def state_with_leases(self):
        state, _ = coordination.plan_acquire(
            coordination.empty_state(),
            ["file:viewer-next/package.json"],
            TARGET,
            "engine edit",
            NOW,
            "target-acquire",
        )
        state, _ = coordination.plan_acquire(
            state,
            ["file:viewer-next/tsconfig.json"],
            FOREIGN,
            "ui edit",
            NOW,
            "foreign-acquire",
        )
        return state

    def test_break_glass_requires_gitops_role(self):
        with self.assertRaises(coordination.CoordinationError) as caught:
            coordination.plan_break_glass(
                self.state_with_leases(),
                admin_owner={"role": "ui", "session": "not-admin", "branch": "ui/live", "pr": 45},
                resources=["file:viewer-next/package.json"],
                reason="emergency",
                now=NOW,
                transition_id="break-1",
                expected_revision=HEAD0,
            )
        self.assertEqual(caught.exception.code, "BREAK_GLASS_FORBIDDEN")

    def test_break_glass_removes_only_exact_target_and_audits_owner(self):
        candidate, event = coordination.plan_break_glass(
            self.state_with_leases(),
            admin_owner=ADMIN,
            resources=["file:viewer-next/package.json"],
            reason="owner unavailable during emergency integration",
            now=NOW,
            transition_id="break-1",
            expected_revision=HEAD0,
        )
        self.assertEqual(len(candidate["leases"]), 1)
        self.assertEqual(candidate["leases"][0]["owner"]["session"], "ui-1")
        self.assertEqual(event["action"], "break-glass")
        self.assertEqual(event["expectedRevision"], HEAD0)
        self.assertEqual(event["admin"], ADMIN)
        self.assertEqual(event["removed"][0]["owner"], TARGET)
        self.assertEqual(event["removed"][0]["resource"], "file:viewer-next/package.json")

    def test_break_glass_does_not_treat_overlapping_glob_as_exact_target(self):
        state, _ = coordination.plan_acquire(
            coordination.empty_state(),
            ["path:viewer-next/src/api/**"],
            TARGET,
            "api edit",
            NOW,
            "api-acquire",
        )
        with self.assertRaises(coordination.CoordinationError) as caught:
            coordination.plan_break_glass(
                state,
                admin_owner=ADMIN,
                resources=["file:viewer-next/src/api/ui-contract.ts"],
                reason="emergency",
                now=NOW,
                transition_id="break-exact",
                expected_revision=HEAD0,
            )
        self.assertEqual(caught.exception.code, "BREAK_GLASS_TARGET_NOT_FOUND")

    def test_stale_expected_revision_is_delegated_to_canonical_writer(self):
        authority = DelegatingAuthority(
            CoordinationRemoteError("COORDINATION_EXPECTED_REVISION_MISMATCH", "stale")
        )
        with self.assertRaises(CoordinationRemoteError) as caught:
            apply_break_glass(
                authority,
                expected_revision=HEAD0,
                admin_owner=ADMIN,
                resources=["file:viewer-next/package.json"],
                reason="emergency",
                transition_id="stale-break",
            )
        self.assertEqual(caught.exception.code, "COORDINATION_EXPECTED_REVISION_MISMATCH")
        self.assertEqual(authority.calls[0]["expectedRevision"], HEAD0)

    def test_cas_drift_from_canonical_writer_is_translated(self):
        authority = DelegatingAuthority(CoordinationRemoteError("COORDINATION_REF_DRIFT", "race"))
        with self.assertRaises(CoordinationRemoteError) as caught:
            apply_break_glass(
                authority,
                expected_revision=HEAD0,
                admin_owner=ADMIN,
                resources=["file:viewer-next/package.json"],
                reason="emergency",
                transition_id="race-break",
            )
        self.assertEqual(caught.exception.code, "COORDINATION_EXPECTED_REVISION_MISMATCH")
        self.assertEqual(authority.calls[0]["message"], "coordination: break-glass race-break")



if __name__ == "__main__":
    unittest.main()
