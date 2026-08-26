from __future__ import annotations

import copy
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest import mock

from tools import coordination
from tools import coordination_ownership
from tools import remote_canonical_execution as remote
from tools.agent_tools import admission, contracts, guard_proofs
from tools.canonical import stable_hash

NOW = datetime(2026, 8, 25, 2, 0, tzinfo=timezone.utc)
BRANCH = "work/operations/at3a-proof-test"
PATH = "docs/at3a-proof-test.json"
HEAD = "a" * 40
BLOB = "b" * 40


def actor(session: str = "at3a-session") -> dict:
    return {
        "role": "manager-gitops",
        "workerId": "manager-gitops-a",
        "sessionId": session,
    }


def owner(session: str = "at3a-session", *, branch: str = BRANCH) -> dict:
    return {
        "role": "manager-gitops",
        "session": session,
        "branch": branch,
        "pr": None,
    }


def make_plan(*, operation: str = "create-file") -> dict:
    expected = {"branchHead": HEAD}
    if operation == "mutate-files":
        payload = {
            "changes": [
                {"path": "docs/at3a-proof-a.json", "content": "{}\n"},
                {"path": "docs/at3a-proof-b.json", "delete": True},
            ],
            "message": "AT3A proof test",
        }
        target = {"operation": operation, "branch": BRANCH}
        plan_target = {"branch": BRANCH}
        tool_id = "git.files.mutate"
        adapter = "remote-git-files"
    else:
        target = {"operation": operation, "branch": BRANCH, "path": PATH}
        plan_target = {"branch": BRANCH, "path": PATH}
        tool_id = {
            "create-file": "git.file.create",
            "update-file": "git.file.update",
            "delete-file": "git.file.delete",
        }[operation]
        adapter = "remote-git-file"
    if operation in {"update-file", "delete-file"}:
        expected["blobSha"] = BLOB
    if operation != "mutate-files":
        payload = (
            {"content": "{}\n", "message": "AT3A proof test"}
            if operation in {"create-file", "update-file"}
            else {"message": "AT3A proof test"}
        )
    command = {
        "schemaVersion": remote.COMMAND_SCHEMA,
        "executionId": "agent-tool-at3a-proof-test",
        "kind": "git-direct",
        "actor": actor(),
        "declaredIntent": {"goal": "agent-tool:git.file.create", "agentToolRequestId": "at3a-proof-test"},
        "target": target,
        "expected": expected,
        "payload": payload,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    remote.validate_command(command)
    concrete = {
        "kind": "remote-canonical-command",
        "command": command,
        "commandHash": remote.command_hash(command),
        "mutationEnabled": False,
    }
    core = {
        "schemaVersion": contracts.PLAN_SCHEMA,
        "requestHash": "1" * 64,
        "begin": {"runId": 1, "sourceSha": "c" * 40, "contextHash": "2" * 64},
        "actor": actor(),
        "toolId": tool_id,
        "effectClass": "shared-durable-mutation",
        "mode": "plan-only",
        "adapter": adapter,
        "requiredCapabilities": ["remote.canonical.execute"],
        "eligibleToolSurfaces": ["github-actions-workflows", "python-module-cli"],
        "targetPolicy": "manager-non-control-git",
        "guards": ["coordination-lease-owned", "git-cas"],
        "target": plan_target,
        "input": copy.deepcopy(payload),
        "concrete": concrete,
        "status": "PLANNED",
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    plan = {**core, "planHash": stable_hash(core)}
    return contracts.validate_plan(plan)


def leased_state(*, lease_owner: dict | None = None) -> dict:
    state = coordination.empty_state()
    state, _ = coordination.plan_acquire(
        state,
        [f"branch:{BRANCH}"],
        lease_owner or owner(),
        "AT3A proof test",
        NOW,
        "at3a-proof-lease",
        900,
    )
    return state


class FakeAuthority:
    def __init__(self, state: dict):
        self.state = state
        self.observe_count = 0

    def observe(self):
        self.observe_count += 1
        return SimpleNamespace(
            state=self.state,
            head_sha="d" * 40,
            authority_now=NOW,
        )


class PositiveOwnershipTests(unittest.TestCase):
    def test_can_write_semantics_remain_conflict_guarded_without_lease(self):
        state = coordination.empty_state()
        allowed, lease = coordination.can_write(state, f"branch:{BRANCH}", owner(), NOW)
        self.assertTrue(allowed)
        self.assertIsNone(lease)
        with self.assertRaisesRegex(RuntimeError, "LEASE_REQUIRED"):
            coordination_ownership.require_owned_lease(
                state, f"branch:{BRANCH}", owner(), NOW
            )

    def test_exact_owned_lease_is_returned(self):
        lease = coordination_ownership.require_owned_lease(
            leased_state(), f"branch:{BRANCH}", owner(), NOW
        )
        self.assertEqual(lease["owner"], owner())

    def test_foreign_and_metadata_mismatch_fail_differently(self):
        with self.assertRaisesRegex(RuntimeError, "LEASE_CONFLICT"):
            coordination_ownership.require_owned_lease(
                leased_state(lease_owner=owner("foreign-session")),
                f"branch:{BRANCH}",
                owner(),
                NOW,
            )
        mismatched = owner()
        mismatched["role"] = "ui-ux"
        with self.assertRaisesRegex(RuntimeError, "LEASE_OWNER_MISMATCH"):
            coordination_ownership.require_owned_lease(
                leased_state(lease_owner=mismatched),
                f"branch:{BRANCH}",
                owner(),
                NOW,
            )


class GuardProofTests(unittest.TestCase):
    @mock.patch("tools.agent_tools.guard_proofs.git_observation.observe_file")
    def test_git_cas_proof_binds_plan_command_and_observation(self, observe_file):
        plan = make_plan()
        observe_file.return_value = {
            "repository": "EAKerber/MobiliPresenter",
            "branch": BRANCH,
            "path": PATH,
            "branchHead": HEAD,
            "blobSha": None,
            "readOnly": True,
            "semanticAuthority": False,
            "authorizesMutation": False,
        }
        proof = guard_proofs.prove_git_cas(plan, transport=object())
        self.assertEqual(proof["planHash"], plan["planHash"])
        self.assertEqual(proof["requestHash"], plan["requestHash"])
        self.assertEqual(proof["observed"]["branchHead"], HEAD)
        self.assertFalse(proof["authorizesMutation"])

    @mock.patch("tools.agent_tools.guard_proofs.git_observation.observe_file")
    def test_git_cas_detects_head_and_blob_drift(self, observe_file):
        create = make_plan()
        observe_file.return_value = {
            "branchHead": "e" * 40,
            "blobSha": None,
        }
        with self.assertRaisesRegex(RuntimeError, "AGENT_TOOL_GIT_CAS_BRANCH_DRIFT"):
            guard_proofs.prove_git_cas(create, transport=object())

        update = make_plan(operation="update-file")
        observe_file.return_value = {
            "branchHead": HEAD,
            "blobSha": "f" * 40,
        }
        with self.assertRaisesRegex(RuntimeError, "AGENT_TOOL_GIT_CAS_BLOB_DRIFT"):
            guard_proofs.prove_git_cas(update, transport=object())

    @mock.patch("tools.agent_tools.guard_proofs.git_observation.observe_branch")
    def test_multi_path_git_cas_binds_branch_head_and_all_paths(self, observe_branch):
        observe_branch.return_value = {"branchHead": HEAD}
        plan = make_plan(operation="mutate-files")
        proof = guard_proofs.prove_git_cas(plan, transport=object())
        self.assertEqual(
            proof["target"],
            {
                "branch": BRANCH,
                "paths": ["docs/at3a-proof-a.json", "docs/at3a-proof-b.json"],
            },
        )
        self.assertEqual(proof["observed"], {"branchHead": HEAD})

    @mock.patch("tools.agent_tools.guard_proofs.git_observation.observe_file")
    def test_guard_proof_set_is_complete_but_mutation_remains_not_admitted(self, observe_file):
        plan = make_plan()
        observe_file.return_value = {
            "repository": "EAKerber/MobiliPresenter",
            "branch": BRANCH,
            "path": PATH,
            "branchHead": HEAD,
            "blobSha": None,
            "readOnly": True,
            "semanticAuthority": False,
            "authorizesMutation": False,
        }
        authority = FakeAuthority(leased_state())
        proof_set = admission.collect_guard_proofs(
            plan,
            transport=object(),
            authority_factory=lambda _: authority,
        )
        self.assertEqual(set(proof_set["proofs"]), set(plan["guards"]))
        self.assertEqual(proof_set["status"], "PASS")
        guard_proofs.validate_proof_set(proof_set, plan=plan)
        with self.assertRaisesRegex(RuntimeError, "AGENT_TOOL_MUTATION_EXECUTION_NOT_ADMITTED"):
            admission.assert_execution_admitted(plan, proof_set)

    def test_admission_rejects_missing_or_mismatched_proof_set(self):
        plan = make_plan()
        with self.assertRaisesRegex(RuntimeError, "AGENT_TOOL_GUARD_PROOFS_REQUIRED"):
            admission.assert_execution_admitted(plan)
        fake = {
            "schemaVersion": guard_proofs.PROOF_SET_SCHEMA,
            "requestHash": plan["requestHash"],
            "planHash": "0" * 64,
            "actor": copy.deepcopy(plan["actor"]),
            "target": copy.deepcopy(plan["target"]),
            "proofs": {},
            "status": "PASS",
            "readOnly": True,
            "semanticAuthority": False,
            "authorizesMutation": False,
        }
        fake["proofSetHash"] = stable_hash(fake)
        with self.assertRaisesRegex(RuntimeError, "AGENT_TOOL_GUARD_PROOF_SET_PLAN_MISMATCH|AGENT_TOOL_GUARD_PROOF_SET_GUARDS_MISMATCH"):
            guard_proofs.validate_proof_set(fake, plan=plan)


if __name__ == "__main__":
    unittest.main()
