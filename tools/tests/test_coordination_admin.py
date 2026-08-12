import copy
import unittest
from datetime import datetime, timezone

from tools import coordination
from tools.coordination_admin import apply_break_glass, plan_break_glass
from tools.coordination_remote import AuthorityObservation, CoordinationRemoteError

NOW = datetime(2026, 8, 12, 5, 10, 0, tzinfo=timezone.utc)
HEAD0 = "1" * 40
TREE0 = "2" * 40
ADMIN = {"role": "gitops", "session": "admin-1", "branch": "ops/admin", "pr": 32}
TARGET = {"role": "engine", "session": "engine-1", "branch": "engine/live", "pr": 44}
FOREIGN = {"role": "ui", "session": "ui-1", "branch": "ui/live", "pr": 45}


class ObserveOnlyAuthority:
    def __init__(self, head):
        self.head = head

    def observe(self):
        return AuthorityObservation(
            head_sha=self.head,
            tree_sha=TREE0,
            state=coordination.empty_state(),
            authority_now=NOW,
        )


class DriftAuthority:
    def __init__(self, state):
        self.state = copy.deepcopy(state)
        self.created = []

    def observe(self):
        return AuthorityObservation(
            head_sha=HEAD0,
            tree_sha=TREE0,
            state=copy.deepcopy(self.state),
            authority_now=NOW,
        )

    def _create_blob(self, content):
        self.created.append(("blob", content))
        return "3" * 40

    def _create_tree(self, base_tree, blob):
        self.created.append(("tree", base_tree, blob))
        return "4" * 40

    def _create_commit(self, parent, tree, message, authority_now):
        self.created.append(("commit", parent, tree, message, authority_now))
        return "5" * 40

    def _advance_ref(self, commit, parent):
        raise CoordinationRemoteError("COORDINATION_REF_DRIFT", "race")

    def _verify_published_transition(self, commit, candidate):
        raise AssertionError("must not verify after drift")


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
            plan_break_glass(
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
        candidate, event = plan_break_glass(
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
            plan_break_glass(
                state,
                admin_owner=ADMIN,
                resources=["file:viewer-next/src/api/ui-contract.ts"],
                reason="emergency",
                now=NOW,
                transition_id="break-exact",
                expected_revision=HEAD0,
            )
        self.assertEqual(caught.exception.code, "BREAK_GLASS_TARGET_NOT_FOUND")

    def test_stale_expected_revision_fails_before_object_creation(self):
        authority = ObserveOnlyAuthority("9" * 40)
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

    def test_cas_drift_during_break_is_translated_to_expected_revision_mismatch(self):
        authority = DriftAuthority(self.state_with_leases())
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
        self.assertTrue(any(item[0] == "commit" for item in authority.created))


if __name__ == "__main__":
    unittest.main()
