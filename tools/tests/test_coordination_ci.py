import copy
import unittest
from datetime import datetime, timedelta, timezone

from tools import coordination
from tools.coordination_ci import evaluate_changes, owner_matches_pr

NOW = datetime(2026, 8, 12, 4, 25, 0, tzinfo=timezone.utc)


class CoordinationCiTests(unittest.TestCase):
    def test_owner_matches_branch_and_optional_pr(self):
        self.assertTrue(
            owner_matches_pr(
                {"role": "ui", "session": "s", "branch": "ui/live", "pr": 32},
                "ui/live",
                32,
            )
        )
        self.assertFalse(
            owner_matches_pr(
                {"role": "ui", "session": "s", "branch": "ui/live", "pr": 32},
                "ui/live",
                33,
            )
        )
        self.assertTrue(
            owner_matches_pr(
                {"role": "ui", "session": "s", "branch": "ui/live", "pr": None},
                "ui/live",
                99,
            )
        )

    def test_foreign_path_lease_blocks_matching_file(self):
        owner = {"role": "engine", "session": "engine-1", "branch": "engine/live", "pr": 44}
        state, _ = coordination.plan_acquire(
            coordination.empty_state(),
            ["path:viewer-next/src/api/**"],
            owner,
            "contract edit",
            NOW,
            "engine-path",
        )
        result = evaluate_changes(
            state,
            NOW,
            ["viewer-next/src/api/ui-contract.ts"],
            head_branch="ui/live",
            pr_number=32,
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["violations"][0]["held"], "path:viewer-next/src/api/**")
        self.assertEqual(result["violations"][0]["changed"], "file:viewer-next/src/api/ui-contract.ts")

    def test_same_branch_and_pr_is_allowed(self):
        owner = {"role": "ui", "session": "ui-secret", "branch": "ui/live", "pr": 32}
        state, _ = coordination.plan_acquire(
            coordination.empty_state(),
            ["file:viewer-next/package.json"],
            owner,
            "integration edit",
            NOW,
            "ui-package",
        )
        result = evaluate_changes(
            state,
            NOW,
            ["viewer-next/package.json"],
            head_branch="ui/live",
            pr_number=32,
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["violations"], [])

    def test_matching_branch_with_wrong_pr_is_violation(self):
        owner = {"role": "ui", "session": "old", "branch": "ui/live", "pr": 31}
        state, _ = coordination.plan_acquire(
            coordination.empty_state(),
            ["file:viewer-next/package.json"],
            owner,
            "old PR",
            NOW,
            "old-pr",
        )
        result = evaluate_changes(
            state,
            NOW,
            ["viewer-next/package.json"],
            head_branch="ui/live",
            pr_number=32,
        )
        self.assertFalse(result["ok"])

    def test_unrelated_file_remains_developable(self):
        owner = {"role": "engine", "session": "engine-1", "branch": "engine/live", "pr": 44}
        state, _ = coordination.plan_acquire(
            coordination.empty_state(),
            ["path:viewer-next/src/api/**"],
            owner,
            "contract edit",
            NOW,
            "engine-path",
        )
        result = evaluate_changes(
            state,
            NOW,
            ["viewer-next/src/ui/detail.ts"],
            head_branch="ui/live",
            pr_number=32,
        )
        self.assertTrue(result["ok"])

    def test_expired_lease_does_not_block(self):
        owner = {"role": "engine", "session": "engine-expired", "branch": "engine/live", "pr": 44}
        state, _ = coordination.plan_acquire(
            coordination.empty_state(),
            ["file:viewer-next/package.json"],
            owner,
            "short lease",
            NOW,
            "short",
            ttl_seconds=1,
        )
        result = evaluate_changes(
            state,
            NOW + timedelta(seconds=2),
            ["viewer-next/package.json"],
            head_branch="ui/live",
            pr_number=32,
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["activeLeaseCount"], 0)

    def test_foreign_branch_lease_blocks_that_branch(self):
        owner = {"role": "gitops", "session": "release-1", "branch": "ops/release", "pr": 50}
        state, _ = coordination.plan_acquire(
            coordination.empty_state(),
            ["branch:integration/viewer-parallel-v0.1"],
            owner,
            "integration promotion",
            NOW,
            "branch-lock",
        )
        result = evaluate_changes(
            state,
            NOW,
            ["viewer-next/src/ui/detail.ts"],
            head_branch="integration/viewer-parallel-v0.1",
            pr_number=32,
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["violations"][0]["changed"], "branch:integration/viewer-parallel-v0.1")

    def test_files_are_normalized_and_deduplicated(self):
        result = evaluate_changes(
            coordination.empty_state(),
            NOW,
            ["viewer-next/package.json", "viewer-next/package.json"],
            head_branch="ui/live",
            pr_number=32,
        )
        self.assertEqual(result["files"], ["file:viewer-next/package.json"])


if __name__ == "__main__":
    unittest.main()
