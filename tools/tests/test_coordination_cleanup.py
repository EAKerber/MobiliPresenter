import unittest
from datetime import datetime, timezone

from tools import coordination
from tools.coordination_cleanup import plan_closed_pr_cleanup

NOW = datetime(2026, 8, 12, 4, 50, 0, tzinfo=timezone.utc)


class CoordinationCleanupTests(unittest.TestCase):
    def owner(self, role, session, branch, pr):
        return {"role": role, "session": session, "branch": branch, "pr": pr}

    def test_cleanup_removes_all_sessions_for_exact_closed_pr_and_branch(self):
        state = coordination.empty_state()
        first = self.owner("engine", "closed-a", "engine/closed", 55)
        second = self.owner("engine", "closed-b", "engine/closed", 55)
        state, _ = coordination.plan_acquire(
            state,
            ["file:ops/coordination/a.shared"],
            first,
            "first session",
            NOW,
            "acquire-a",
        )
        state, _ = coordination.plan_acquire(
            state,
            ["file:ops/coordination/b.shared"],
            second,
            "second session",
            NOW,
            "acquire-b",
        )
        state, _ = coordination.plan_intent(
            state,
            ["file:ops/coordination/c.shared"],
            second,
            "intent",
            NOW,
            "intent-b",
        )

        candidate, event = plan_closed_pr_cleanup(
            state,
            pr_number=55,
            branch="engine/closed",
            now=NOW,
            transition_id="cleanup-55",
        )

        self.assertEqual(candidate["leases"], [])
        self.assertEqual(candidate["intents"], [])
        self.assertEqual(event["action"], "cleanup-closed-pr")
        self.assertEqual(event["removedSessions"], ["closed-a", "closed-b"])

    def test_cleanup_does_not_remove_foreign_pr(self):
        closed = self.owner("engine", "closed", "engine/closed", 55)
        foreign = self.owner("ui", "foreign", "ui/live", 56)
        state, _ = coordination.plan_acquire(
            coordination.empty_state(),
            ["file:ops/coordination/a.shared"],
            closed,
            "closed",
            NOW,
            "closed-acquire",
        )
        state, _ = coordination.plan_acquire(
            state,
            ["file:ops/coordination/b.shared"],
            foreign,
            "foreign",
            NOW,
            "foreign-acquire",
        )

        candidate, _ = plan_closed_pr_cleanup(
            state,
            pr_number=55,
            branch="engine/closed",
            now=NOW,
            transition_id="cleanup-55",
        )

        self.assertEqual(len(candidate["leases"]), 1)
        self.assertEqual(candidate["leases"][0]["owner"]["session"], "foreign")

    def test_same_pr_wrong_branch_is_not_removed(self):
        owner = self.owner("engine", "other-branch", "engine/other", 55)
        state, _ = coordination.plan_acquire(
            coordination.empty_state(),
            ["file:ops/coordination/a.shared"],
            owner,
            "other branch",
            NOW,
            "other-acquire",
        )

        candidate, event = plan_closed_pr_cleanup(
            state,
            pr_number=55,
            branch="engine/closed",
            now=NOW,
            transition_id="cleanup-55",
        )

        self.assertEqual(len(candidate["leases"]), 1)
        self.assertEqual(event["removedLeaseIds"], [])

    def test_cleanup_is_idempotent_when_no_entries_match(self):
        state = coordination.empty_state()
        candidate, event = plan_closed_pr_cleanup(
            state,
            pr_number=55,
            branch="engine/closed",
            now=NOW,
            transition_id="cleanup-empty",
        )
        self.assertEqual(candidate, state)
        self.assertEqual(event["removedIntentIds"], [])
        self.assertEqual(event["removedLeaseIds"], [])

    def test_invalid_identity_fails_before_cleanup(self):
        with self.assertRaises(coordination.CoordinationError) as caught:
            plan_closed_pr_cleanup(
                coordination.empty_state(),
                pr_number=0,
                branch="engine/closed",
                now=NOW,
                transition_id="bad",
            )
        self.assertEqual(caught.exception.code, "CLEANUP_IDENTITY_INVALID")


if __name__ == "__main__":
    unittest.main()
