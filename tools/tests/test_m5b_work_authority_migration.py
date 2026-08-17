from __future__ import annotations

import unittest

from tools import continuation, continuation_transition as transition, transition_protocol as protocol
from tools.continuation_remote import GitHubContinuationAuthority, Observation


def terminal_v01(cid: str, actor: str = "worker-a") -> dict:
    return {
        "schemaVersion": continuation.CURRENT_SCHEMA_VERSION,
        "id": cid,
        "actor": actor,
        "status": "DONE",
        "branch": None,
        "prNumber": None,
        "completed": ["done"],
        "remaining": [],
        "nextAction": None,
        "lastKnownGood": {"sha": None, "checkpoint": "done"},
        "blockedBy": [],
        "handoffTo": None,
    }


class FakeMigrationAuthority(GitHubContinuationAuthority):
    def __init__(self, before: dict[str, dict], after: dict[str, dict], head: str):
        super().__init__(transport=object(), readback_attempts=1, readback_retry_seconds=0)
        self.before = before
        self.after = after
        self.head = head
        self.calls = 0
        self.published = None

    def observe(self):
        self.calls += 1
        if self.calls == 1:
            return Observation(self.head, "1" * 40, self.before)
        return Observation("2" * 40, "3" * 40, self.after)

    def _commit_inventory(self, observed, items, message):
        self.published = (observed, items, message)
        return "2" * 40


class WorkAuthorityMigrationTests(unittest.TestCase):
    def test_migration_is_deterministic_and_sorted(self):
        items = {"work-b": terminal_v01("work-b", "worker-b"), "work-a": terminal_v01("work-a")}
        head = "a" * 40
        plan1 = transition.migrate_schema(items, head)
        plan2 = transition.migrate_schema(dict(reversed(list(items.items()))), head)
        self.assertEqual(plan1, plan2)
        self.assertEqual([item["id"] for item in plan1["candidate"]["items"]], ["work-a", "work-b"])
        self.assertTrue(all(item["schemaVersion"] == continuation.CANDIDATE_SCHEMA_VERSION for item in plan1["candidate"]["items"]))
        transition.validate_migration_plan(plan1, items, head)

    def test_migration_refuses_active_inventory(self):
        item = terminal_v01("work-a")
        item.update(status="READY", remaining=["x"], nextAction="do x", completed=[])
        with self.assertRaisesRegex(RuntimeError, "WORK_AUTHORITY_MIGRATION_REQUIRES_TERMINAL_INVENTORY"):
            transition.migrate_schema({"work-a": item}, "a" * 40)

    def test_migration_plan_is_bound_to_authority_head(self):
        items = {"work-a": terminal_v01("work-a")}
        plan = transition.migrate_schema(items, "a" * 40)
        with self.assertRaisesRegex(RuntimeError, "WORK_AUTHORITY_MIGRATION_HEAD_STALE"):
            transition.validate_migration_plan(plan, items, "b" * 40)

    def test_apply_migration_publishes_inventory_once_and_verifies_receipt(self):
        before = {"work-a": terminal_v01("work-a"), "work-b": terminal_v01("work-b", "worker-b")}
        head = "a" * 40
        plan = transition.migrate_schema(before, head)
        after = continuation.inventory_items(plan["candidate"])
        authority = FakeMigrationAuthority(before, after, head)
        receipt = authority.apply_migration(plan, plan["planHash"])
        self.assertIsNotNone(authority.published)
        self.assertEqual(authority.published[1], after)
        self.assertEqual(authority.calls, 2)
        protocol.validate_receipt(receipt, plan)
        self.assertEqual(receipt["authorityRevision"], "2" * 40)

    def test_inventory_envelope_rejects_noncanonical_order(self):
        value = {
            "schemaVersion": continuation.INVENTORY_SCHEMA_VERSION,
            "items": [terminal_v01("work-b"), terminal_v01("work-a")],
        }
        with self.assertRaisesRegex(RuntimeError, "WORK_AUTHORITY_INVENTORY_ORDER_INVALID"):
            continuation.inventory_items(value)


if __name__ == "__main__":
    unittest.main()
