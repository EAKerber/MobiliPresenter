import copy
import importlib.util
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "coordination.py"
spec = importlib.util.spec_from_file_location("coordination", MODULE_PATH)
coord = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(coord)


NOW = datetime(2026, 8, 12, 0, 0, tzinfo=timezone.utc)


class CoordinationCoreTests(unittest.TestCase):
    def owner(self, session="ui-1", branch="ui/test", pr=101, role="ui"):
        return {"role": role, "session": session, "branch": branch, "pr": pr}

    def acquire(self, state, resources, session="ui-1", transition="tx-1", ttl=3600):
        return coord.plan_acquire(
            state,
            resources,
            self.owner(session=session),
            "test acquisition",
            NOW,
            transition,
            ttl,
        )

    def test_empty_state_is_valid(self):
        state = coord.empty_state()
        coord.validate_state(state)
        self.assertEqual(state["leases"], [])

    def test_runtime_rejects_unknown_fields_and_empty_revision(self):
        root = coord.empty_state()
        with self.assertRaisesRegex(coord.CoordinationError, "root fields are invalid"):
            coord.validate_state(dict(root, unexpected=True))
        with self.assertRaisesRegex(coord.CoordinationError, "revision must be null or a non-empty string"):
            coord.validate_state(coord.empty_state(""))
        owner = {"role": "ui", "session": "s", "branch": None, "pr": None, "unexpected": True}
        with self.assertRaisesRegex(coord.CoordinationError, "owner fields are invalid"):
            coord.validate_owner(owner)

    def test_resource_normalization_and_order_are_deterministic(self):
        observed = coord.normalize_resources(
            ["file:viewer-next/index.html", "path:viewer-next/src/api/**", "file:viewer-next/index.html"]
        )
        self.assertEqual(
            observed,
            ["file:viewer-next/index.html", "path:viewer-next/src/api/**"],
        )

    def test_invalid_relative_path_is_rejected(self):
        with self.assertRaisesRegex(coord.CoordinationError, "RESOURCE_INVALID"):
            coord.normalize_resource("file:viewer-next/../AGENTS.md")

    def test_same_file_conflicts(self):
        self.assertTrue(
            coord.resources_conflict(
                "file:viewer-next/src/bootstrap.ts",
                "file:viewer-next/src/bootstrap.ts",
            )
        )

    def test_file_glob_conflict(self):
        self.assertTrue(
            coord.resources_conflict(
                "file:viewer-next/src/api/ui-contract.ts",
                "path:viewer-next/src/api/**",
            )
        )
        self.assertFalse(
            coord.resources_conflict(
                "file:viewer-next/src/ui/shell.ts",
                "path:viewer-next/src/api/**",
            )
        )

    def test_glob_glob_disjoint_literal_prefix_is_proven(self):
        self.assertFalse(
            coord.resources_conflict(
                "path:viewer-next/src/api/**",
                "path:viewer-next/src/ui/**",
            )
        )

    def test_glob_glob_uncertain_intersection_fails_closed(self):
        self.assertTrue(
            coord.resources_conflict(
                "path:viewer-next/src/**/shared-*",
                "path:viewer-next/src/api/**",
            )
        )

    def test_branch_namespace_is_separate(self):
        self.assertTrue(
            coord.resources_conflict(
                "branch:integration/viewer-parallel-v0.1",
                "branch:integration/viewer-parallel-v0.1",
            )
        )
        self.assertFalse(
            coord.resources_conflict(
                "branch:integration/viewer-parallel-v0.1",
                "file:viewer-next/src/bootstrap.ts",
            )
        )

    def test_batch_acquire_is_all_or_nothing(self):
        state = coord.empty_state()
        occupied, _ = self.acquire(state, ["file:shared/b.ts"], session="engine-1", transition="eng-1")
        before = copy.deepcopy(occupied)
        with self.assertRaisesRegex(coord.CoordinationError, "LEASE_CONFLICT"):
            self.acquire(
                occupied,
                ["file:shared/a.ts", "file:shared/b.ts"],
                session="ui-1",
                transition="ui-1",
            )
        self.assertEqual(occupied, before)
        self.assertFalse(any(lease["resource"] == "file:shared/a.ts" for lease in occupied["leases"]))

    def test_resource_input_order_does_not_change_acquire_result_shape(self):
        state = coord.empty_state()
        first, _ = self.acquire(
            state,
            ["file:shared/b.ts", "file:shared/a.ts"],
            transition="same-transition",
        )
        second, _ = self.acquire(
            state,
            ["file:shared/a.ts", "file:shared/b.ts"],
            transition="same-transition",
        )
        self.assertEqual(first, second)

    def test_expired_lease_does_not_block(self):
        state, _ = self.acquire(coord.empty_state(), ["file:shared/a.ts"], ttl=60)
        later = NOW + timedelta(seconds=61)
        candidate, _ = coord.plan_acquire(
            state,
            ["file:shared/a.ts"],
            self.owner(session="engine-1", branch="engine/test", pr=102, role="engine"),
            "after expiry",
            later,
            "eng-2",
            3600,
        )
        active = coord.active_leases(candidate, later)
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["owner"]["session"], "engine-1")

    def test_renew_mine_extends_only_same_session(self):
        state, _ = self.acquire(coord.empty_state(), ["file:shared/a.ts"], session="ui-1", transition="ui")
        state, _ = coord.plan_acquire(
            state,
            ["file:shared/b.ts"],
            self.owner(session="engine-1", branch="engine/test", pr=102, role="engine"),
            "engine",
            NOW,
            "engine",
            3600,
        )
        later = NOW + timedelta(minutes=10)
        renewed, _ = coord.plan_renew_mine(state, self.owner(session="ui-1"), later, "renew-ui")
        by_resource = {lease["resource"]: lease for lease in renewed["leases"]}
        self.assertEqual(by_resource["file:shared/a.ts"]["renewedAt"], "2026-08-12T00:10:00Z")
        self.assertEqual(by_resource["file:shared/b.ts"]["renewedAt"], "2026-08-12T00:00:00Z")

    def test_release_mine_removes_only_same_session(self):
        state, _ = self.acquire(coord.empty_state(), ["file:shared/a.ts"], session="ui-1", transition="ui")
        state, _ = coord.plan_acquire(
            state,
            ["file:shared/b.ts"],
            self.owner(session="engine-1", branch="engine/test", pr=102, role="engine"),
            "engine",
            NOW,
            "engine",
            3600,
        )
        released, _ = coord.plan_release(
            state,
            self.owner(session="ui-1"),
            NOW,
            "release-ui",
            mine=True,
        )
        self.assertEqual([lease["resource"] for lease in released["leases"]], ["file:shared/b.ts"])

    def test_foreign_session_cannot_release(self):
        state, _ = self.acquire(coord.empty_state(), ["file:shared/a.ts"], session="ui-1")
        with self.assertRaisesRegex(coord.CoordinationError, "LEASE_NOT_OWNER"):
            coord.plan_release(
                state,
                self.owner(session="engine-1", branch="engine/test", pr=102, role="engine"),
                NOW,
                "release-engine",
                resources=["file:shared/a.ts"],
            )

    def test_same_session_write_is_allowed(self):
        state, _ = self.acquire(coord.empty_state(), ["path:viewer-next/src/api/**"], session="ui-1")
        allowed, lease = coord.can_write(
            state,
            "file:viewer-next/src/api/ui-contract.ts",
            self.owner(session="ui-1"),
            NOW,
        )
        self.assertTrue(allowed)
        self.assertIsNotNone(lease)

    def test_foreign_session_write_is_blocked(self):
        state, _ = self.acquire(coord.empty_state(), ["path:viewer-next/src/api/**"], session="ui-1")
        allowed, lease = coord.can_write(
            state,
            "file:viewer-next/src/api/ui-contract.ts",
            self.owner(session="engine-1", branch="engine/test", pr=102, role="engine"),
            NOW,
        )
        self.assertFalse(allowed)
        self.assertEqual(lease["owner"]["session"], "ui-1")

    def test_intent_never_blocks_acquire(self):
        state, _ = coord.plan_intent(
            coord.empty_state(),
            ["file:shared/a.ts"],
            self.owner(session="ui-1"),
            "maybe later",
            NOW,
            "intent-ui",
        )
        acquired, _ = coord.plan_acquire(
            state,
            ["file:shared/a.ts"],
            self.owner(session="engine-1", branch="engine/test", pr=102, role="engine"),
            "engine writes now",
            NOW,
            "acquire-engine",
        )
        self.assertEqual(len(acquired["leases"]), 1)
        self.assertEqual(acquired["leases"][0]["owner"]["session"], "engine-1")


if __name__ == "__main__":
    unittest.main()
