import copy
import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone

from tools import coordination
from tools import lock
from tools.coordination_remote import (
    AppliedTransition,
    AuthorityObservation,
    CoordinationRemoteError,
)

NOW = datetime(2026, 8, 12, 4, 20, 0, tzinfo=timezone.utc)
HEAD0 = "1" * 40
TREE0 = "2" * 40


class FakeAuthority:
    authority_branch = "coordination/leases"

    def __init__(self, state=None):
        self.state = copy.deepcopy(state if state is not None else coordination.empty_state())
        self.head = HEAD0
        self.tree = TREE0
        self.now = NOW
        self.counter = 3

    def observe(self):
        return AuthorityObservation(
            head_sha=self.head,
            tree_sha=self.tree,
            state=copy.deepcopy(self.state),
            authority_now=self.now,
        )

    def mutate(self, planner, *, message):
        before = self.head
        candidate, event = planner(copy.deepcopy(self.state), self.now)
        candidate["revision"] = before
        coordination.validate_state(candidate)
        after = (format(self.counter, "x") * 40)[:40]
        self.counter += 1
        self.head = after
        self.state = copy.deepcopy(candidate)
        return AppliedTransition(
            before_sha=before,
            after_sha=after,
            authority_now=self.now,
            state=copy.deepcopy(candidate),
            event=copy.deepcopy(event),
        )


class UnavailableAuthority:
    authority_branch = "coordination/leases"

    def observe(self):
        raise CoordinationRemoteError("COORDINATION_REMOTE_UNAVAILABLE", "offline")


class LockCliTests(unittest.TestCase):
    def run_cli(self, fake, argv, environ=None):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = lock.main(argv, authority_factory=lambda: fake, environ=environ or {})
        return code, stdout.getvalue(), stderr.getvalue()

    def test_status_requires_no_owner_and_reports_authority(self):
        fake = FakeAuthority()
        code, stdout, _ = self.run_cli(fake, ["status", "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["authorityHead"], HEAD0)
        self.assertEqual(payload["authorityBranch"], "coordination/leases")
        self.assertEqual(payload["leases"], [])

    def test_acquire_publishes_serializable_transition_and_lease(self):
        fake = FakeAuthority()
        code, stdout, _ = self.run_cli(
            fake,
            [
                "acquire",
                "file:viewer-next/package.json",
                "file:viewer-next/src/bootstrap.ts",
                "--role", "ui",
                "--session", "cli-ui-1",
                "--branch", "ui/test",
                "--pr", "32",
                "--reason", "shared integration edit",
                "--transition-id", "cli-acquire-1",
                "--json",
            ],
        )
        self.assertEqual(code, 0)
        payload = json.loads(stdout)
        self.assertEqual(payload["action"], "acquire")
        self.assertEqual(payload["beforeSha"], HEAD0)
        self.assertEqual(payload["authorityNow"], NOW.isoformat())
        self.assertEqual(len(fake.state["leases"]), 2)
        self.assertEqual(fake.state["revision"], HEAD0)

    def test_owner_can_come_from_experimental_environment(self):
        fake = FakeAuthority()
        env = {
            "MOBILIPRESENTER_AGENT_ROLE": "engine",
            "MOBILIPRESENTER_AGENT_SESSION": "engine-env-1",
            "MOBILIPRESENTER_AGENT_BRANCH": "engine/test",
            "MOBILIPRESENTER_PR_NUMBER": "41",
        }
        code, _, _ = self.run_cli(
            fake,
            [
                "acquire",
                "file:viewer-next/package.json",
                "--reason", "environment identity",
                "--transition-id", "env-acquire",
                "--json",
            ],
            environ=env,
        )
        self.assertEqual(code, 0)
        lease = fake.state["leases"][0]
        self.assertEqual(lease["owner"]["role"], "engine")
        self.assertEqual(lease["owner"]["session"], "engine-env-1")
        self.assertEqual(lease["owner"]["pr"], 41)

    def test_missing_session_fails_before_mutation(self):
        fake = FakeAuthority()
        code, stdout, _ = self.run_cli(
            fake,
            [
                "acquire",
                "file:viewer-next/package.json",
                "--role", "ui",
                "--branch", "ui/test",
                "--reason", "missing session",
                "--json",
            ],
        )
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(stdout)["error"], "OWNER_REQUIRED")
        self.assertEqual(fake.state["leases"], [])

    def test_guard_blocks_foreign_lease_with_required_error_code(self):
        foreign = {"role": "engine", "session": "engine-foreign", "branch": "engine/live", "pr": 44}
        state, _ = coordination.plan_acquire(
            coordination.empty_state(),
            ["path:viewer-next/src/api/**"],
            foreign,
            "engine contract edit",
            NOW,
            "foreign-acquire",
        )
        fake = FakeAuthority(state)
        code, stdout, _ = self.run_cli(
            fake,
            [
                "guard",
                "file:viewer-next/src/api/ui-contract.ts",
                "--role", "ui",
                "--session", "ui-local",
                "--branch", "ui/live",
                "--pr", "32",
                "--json",
            ],
        )
        self.assertEqual(code, 2)
        payload = json.loads(stdout)
        self.assertEqual(payload["error"], "WRITE_BLOCKED_BY_LEASE")
        self.assertIn("engine-foreign", payload["detail"])

    def test_guard_allows_owner_session(self):
        owner = {"role": "ui", "session": "ui-own", "branch": "ui/live", "pr": 32}
        state, _ = coordination.plan_acquire(
            coordination.empty_state(),
            ["file:viewer-next/package.json"],
            owner,
            "ui integration edit",
            NOW,
            "own-acquire",
        )
        fake = FakeAuthority(state)
        code, stdout, _ = self.run_cli(
            fake,
            [
                "guard",
                "file:viewer-next/package.json",
                "--role", "ui",
                "--session", "ui-own",
                "--branch", "ui/live",
                "--pr", "32",
                "--json",
            ],
        )
        self.assertEqual(code, 0)
        payload = json.loads(stdout)
        self.assertTrue(payload["checked"][0]["allowed"])

    def test_release_mine_removes_only_current_session(self):
        own = {"role": "ui", "session": "ui-own", "branch": "ui/live", "pr": 32}
        foreign = {"role": "engine", "session": "engine-own", "branch": "engine/live", "pr": 44}
        state, _ = coordination.plan_acquire(
            coordination.empty_state(),
            ["file:viewer-next/package.json"],
            own,
            "ui integration edit",
            NOW,
            "own-acquire",
        )
        state, _ = coordination.plan_acquire(
            state,
            ["file:viewer-next/tsconfig.json"],
            foreign,
            "engine integration edit",
            NOW,
            "foreign-acquire",
        )
        fake = FakeAuthority(state)
        code, stdout, _ = self.run_cli(
            fake,
            [
                "release",
                "--mine",
                "--role", "ui",
                "--session", "ui-own",
                "--branch", "ui/live",
                "--pr", "32",
                "--transition-id", "release-own",
                "--json",
            ],
        )
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout)["action"], "release")
        self.assertEqual(len(fake.state["leases"]), 1)
        self.assertEqual(fake.state["leases"][0]["owner"]["session"], "engine-own")

    def test_remote_unavailability_fails_closed(self):
        code, stdout, _ = self.run_cli(UnavailableAuthority(), ["status", "--json"])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(stdout)["error"], "COORDINATION_REMOTE_UNAVAILABLE")

    def test_release_rejects_resources_plus_mine(self):
        fake = FakeAuthority()
        code, stdout, _ = self.run_cli(
            fake,
            [
                "release",
                "file:viewer-next/package.json",
                "--mine",
                "--role", "ui",
                "--session", "ui-own",
                "--branch", "ui/live",
                "--json",
            ],
        )
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(stdout)["error"], "RELEASE_INVALID")


if __name__ == "__main__":
    unittest.main()
