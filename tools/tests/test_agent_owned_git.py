from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest import mock

from tools import coordination
from tools import remote_canonical_execution as bridge
from tools import remote_canonical_issue as issue_adapter
from tools.agent_commands import agent_owned_git

NOW = datetime(2026, 8, 23, 22, 0, tzinfo=timezone.utc)
HEAD = "a" * 40
BRANCH = "work/operations/agent-owned-write-test"
PATH = "docs/ui/owned-write-test.json"


def actor(*, role="manager-gitops", session="manager-session"):
    return {
        "role": role,
        "workerId": "manager-gitops-a" if role == "manager-gitops" else "ui-ux-a",
        "sessionId": session,
    }


def command(*, role="manager-gitops", session="manager-session"):
    return {
        "schemaVersion": bridge.COMMAND_SCHEMA,
        "executionId": "agent-owned-write-test",
        "kind": "git-direct",
        "actor": actor(role=role, session=session),
        "declaredIntent": {"goal": "qualify agent-owned direct Git"},
        "target": {
            "operation": "create-file",
            "branch": BRANCH if role == "manager-gitops" else "work/ui/agent-owned-write-test",
            "path": PATH if role == "manager-gitops" else "docs/ui/owned-write-test.json",
        },
        "expected": {"branchHead": HEAD},
        "payload": {"content": "{}\n", "message": "agent-owned write test"},
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


def owner_for(value):
    return {
        "role": value["actor"]["role"],
        "session": value["actor"]["sessionId"],
        "branch": value["target"]["branch"],
        "pr": None,
    }


def state_with_leases(value, *entries):
    state = coordination.empty_state()
    for index, (resources, owner) in enumerate(entries):
        state, _ = coordination.plan_acquire(
            state,
            list(resources),
            owner,
            f"lease {index}",
            NOW,
            f"lease-{index}",
            900,
        )
    return state


class FakeAuthority:
    def __init__(self, state):
        self.state = state
        self.observe_count = 0

    def observe(self):
        self.observe_count += 1
        return SimpleNamespace(state=self.state, head_sha="c" * 40, authority_now=NOW)


class RecordingTransport:
    def __init__(self):
        self.calls = []

    def request(self, method, endpoint, *, payload=None, include_headers=False):
        self.calls.append((method, endpoint, payload, include_headers))
        return SimpleNamespace(body="{}", status=200, headers={})


class AgentOwnedGitTests(unittest.TestCase):
    def test_missing_branch_lease_is_blocked(self):
        value = command()
        authority = FakeAuthority(coordination.empty_state())
        with self.assertRaisesRegex(RuntimeError, "REMOTE_AGENT_WRITE_LEASE_REQUIRED"):
            agent_owned_git.require_agent_write_ownership(value, authority)

    def test_foreign_branch_lease_is_blocked(self):
        value = command()
        foreign = {
            "role": "manager-gitops",
            "session": "other-session",
            "branch": value["target"]["branch"],
            "pr": None,
        }
        state = state_with_leases(value, ([f"branch:{value['target']['branch']}"], foreign))
        with self.assertRaisesRegex(RuntimeError, "REMOTE_AGENT_WRITE_LEASE_CONFLICT"):
            agent_owned_git.require_agent_write_ownership(value, FakeAuthority(state))

    def test_same_session_branch_lease_proves_ownership(self):
        value = command()
        state = state_with_leases(
            value,
            ([f"branch:{value['target']['branch']}"], owner_for(value)),
        )
        proof = agent_owned_git.require_agent_write_ownership(value, FakeAuthority(state))
        self.assertEqual(proof["status"], "PASS")
        self.assertEqual(
            proof["requiredOwnedResources"],
            [f"branch:{value['target']['branch']}"],
        )
        self.assertEqual(proof["conflictCheckedResources"], [f"file:{value['target']['path']}"])
        self.assertFalse(proof["semanticAuthority"])
        self.assertFalse(proof["authorizesMutation"])
        self.assertEqual(len(proof["proofHash"]), 64)

    def test_foreign_path_lease_blocks_even_with_owned_branch(self):
        value = command()
        state = state_with_leases(
            value,
            ([f"branch:{value['target']['branch']}"], owner_for(value)),
            (["path:docs/ui/**"], {
                "role": "ui-ux",
                "session": "ui-session",
                "branch": "work/ui/other",
                "pr": None,
            }),
        )
        with self.assertRaisesRegex(RuntimeError, "REMOTE_AGENT_WRITE_LEASE_CONFLICT"):
            agent_owned_git.require_agent_write_ownership(value, FakeAuthority(state))

    def test_transport_checks_only_mutable_calls_and_rechecks_each_mutation(self):
        value = command()
        state = state_with_leases(
            value,
            ([f"branch:{value['target']['branch']}"], owner_for(value)),
        )
        authority = FakeAuthority(state)
        base = RecordingTransport()
        guarded = agent_owned_git.LeaseEnforcingTransport(
            base,
            value,
            authority_factory=lambda _: authority,
        )
        guarded.request("GET", "read-only")
        self.assertEqual(authority.observe_count, 0)
        guarded.request("POST", "mutable-one", payload={})
        guarded.request("PATCH", "mutable-two", payload={})
        self.assertEqual(authority.observe_count, 2)
        self.assertEqual(len(guarded.proofs), 2)
        self.assertEqual([call[0] for call in base.calls], ["GET", "POST", "PATCH"])

    @mock.patch("tools.remote_canonical_issue.execute_agent_owned_git")
    @mock.patch("tools.remote_canonical_issue.execute_remote_command")
    def test_issue_adapter_routes_manager_git_direct_through_owned_guard(
        self, execute_remote_command, execute_agent_owned_git
    ):
        value = command()
        execute_agent_owned_git.return_value = {"status": "PASS"}
        observed = issue_adapter.execute_command(value, source={"source": "test"})
        self.assertEqual(observed, {"status": "PASS"})
        execute_agent_owned_git.assert_called_once()
        execute_remote_command.assert_not_called()

    @mock.patch("tools.remote_canonical_issue.execute_agent_owned_git")
    @mock.patch("tools.remote_canonical_issue.execute_remote_command")
    def test_ui_route_remains_on_existing_role_scoped_path_until_owned_facade_exists(
        self, execute_remote_command, execute_agent_owned_git
    ):
        value = command(role="ui-ux", session="ui-session")
        execute_remote_command.return_value = {"status": "PASS"}
        observed = issue_adapter.execute_command(value, source={"source": "test"})
        self.assertEqual(observed, {"status": "PASS"})
        execute_remote_command.assert_called_once()
        execute_agent_owned_git.assert_not_called()


if __name__ == "__main__":
    unittest.main()
