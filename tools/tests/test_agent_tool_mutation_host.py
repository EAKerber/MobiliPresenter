from __future__ import annotations

import copy
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tools import remote_canonical_execution as remote
from tools.agent_tools import contracts, mutation_host
from tools.canonical import stable_hash


HEAD = "a" * 40
NEW_HEAD = "b" * 40
BRANCH = "work/operations/e3"
ACTOR = {
    "role": "manager-gitops",
    "workerId": "manager-gitops-a",
    "sessionId": "session-e3",
}


def plan():
    command = {
        "schemaVersion": remote.COMMAND_SCHEMA,
        "executionId": "agent-tool-" + "1" * 24,
        "kind": "git-direct",
        "actor": copy.deepcopy(ACTOR),
        "declaredIntent": {
            "goal": "agent-tool:git.files.mutate",
            "agentToolRequestId": "agent-tool-" + "2" * 24,
        },
        "target": {"operation": "mutate-files", "branch": BRANCH},
        "expected": {"branchHead": HEAD},
        "payload": {
            "changes": [{"path": "docs/e3.txt", "content": "x\n"}],
            "message": "E3 mutation host test",
        },
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    core = {
        "schemaVersion": contracts.PLAN_SCHEMA,
        "requestHash": "3" * 64,
        "begin": {"runId": 123, "sourceSha": "4" * 40, "contextHash": "5" * 64},
        "actor": copy.deepcopy(ACTOR),
        "toolId": "git.files.mutate",
        "effectClass": "shared-durable-mutation",
        "mode": "mutation-execute",
        "adapter": "remote-git-files",
        "requiredCapabilities": [],
        "eligibleToolSurfaces": [],
        "targetPolicy": "manager-git-mutation",
        "guards": [
            "agent-write-lifecycle-bound",
            "coordination-lease-owned",
            "git-cas",
        ],
        "target": {"branch": BRANCH},
        "input": {
            "changes": [{"path": "docs/e3.txt", "content": "x\n"}],
            "message": "E3 mutation host test",
        },
        "concrete": {
            "kind": "remote-canonical-command",
            "command": command,
            "commandHash": remote.command_hash(command),
            "mutationEnabled": False,
        },
        "status": "READY",
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**core, "planHash": stable_hash(core)}


def source():
    return remote.build_execution_source(
        kind="agent-tool-host",
        host=mutation_host.DIRECT_HOST_ID,
        source_sha="4" * 40,
        invocation_id="direct-e3",
        ref={"kind": "agent-tool-request", "value": "3" * 64},
    )


class FakeTransport:
    def request(self, method, endpoint, *, payload=None, include_headers=False):
        return SimpleNamespace(body="{}")


def proof_set(value):
    return {
        "schemaVersion": "AgentToolGuardProofSet 0.1",
        "requestHash": value["requestHash"],
        "planHash": value["planHash"],
        "actor": copy.deepcopy(value["actor"]),
        "target": copy.deepcopy(value["target"]),
        "proofs": {},
        "status": "PASS",
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
        "proofSetHash": "6" * 64,
    }


def receipt(value):
    command = value["concrete"]["command"]
    return {
        "schemaVersion": remote.RECEIPT_SCHEMA,
        "executionId": command["executionId"],
        "command": copy.deepcopy(command),
        "commandHash": remote.command_hash(command),
        "route": {"kind": "git-direct", "domain": "git", "action": "mutate-files"},
        "source": source(),
        "planHash": "7" * 64,
        "evidence": {"plan": {}},
        "aggregateReadback": {
            "kind": "git-bundle",
            "branch": BRANCH,
            "branchHead": NEW_HEAD,
            "changedPaths": ["docs/e3.txt"],
            "readbackHash": "8" * 64,
            "status": "PASS",
        },
        "status": "PASS",
        "blockers": [],
        "semanticAuthority": False,
        "authorizesMutation": False,
        "receiptHash": "9" * 64,
    }


class GovernedMutationHostTests(unittest.TestCase):
    def test_guard_failure_before_mutation_is_blocked(self):
        value = plan()
        with (
            patch.object(
                mutation_host.admission,
                "collect_guard_proofs",
                side_effect=RuntimeError("LEASE_STALE"),
            ),
            patch.object(
                mutation_host,
                "observe_branch_head",
                return_value=HEAD,
            ),
        ):
            outcome = mutation_host.execute_plan(
                value,
                source=source(),
                transport=FakeTransport(),
                lifecycle_result_context={
                    "cycleInstanceId": "cycle-instance-" + "1" * 24,
                    "lifecycleResult": {},
                    "lifecycleResultRef": {},
                },
            )
        self.assertEqual(outcome["status"], "BLOCKED")
        self.assertEqual(outcome["blockers"], ["LEASE_STALE"])
        self.assertEqual(outcome["mutableCallCount"], 0)
        self.assertIsNone(outcome["remoteReceipt"])

    def test_failure_after_mutable_call_is_unknown(self):
        value = plan()
        proofs = proof_set(value)

        def ambiguous(command, *, source, transport, authority_factory=None):
            transport.request(
                "POST",
                "repos/EAKerber/MobiliPresenter/git/trees",
                payload={},
            )
            raise RuntimeError("TRANSPORT_DROPPED_AFTER_WRITE")

        with (
            patch.object(
                mutation_host.admission,
                "collect_guard_proofs",
                return_value=proofs,
            ),
            patch.object(
                mutation_host.admission,
                "assert_execution_admitted",
            ),
            patch.object(
                mutation_host.agent_owned_git,
                "execute_agent_owned_git",
                side_effect=ambiguous,
            ),
            patch.object(
                mutation_host,
                "observe_branch_head",
                return_value=NEW_HEAD,
            ),
            patch.object(
                mutation_host.guard_proofs,
                "validate_proof_set",
                side_effect=lambda item, plan=None: item,
            ),
        ):
            outcome = mutation_host.execute_plan(
                value,
                source=source(),
                transport=FakeTransport(),
            )
        self.assertEqual(outcome["status"], "UNKNOWN")
        self.assertEqual(
            outcome["blockers"], ["TRANSPORT_DROPPED_AFTER_WRITE"]
        )
        self.assertEqual(outcome["mutableCallCount"], 1)

    def test_pass_uses_existing_agent_owned_writer_and_receipt(self):
        value = plan()
        proofs = proof_set(value)
        canonical_receipt = receipt(value)
        with (
            patch.object(
                mutation_host.admission,
                "collect_guard_proofs",
                return_value=proofs,
            ),
            patch.object(mutation_host.admission, "assert_execution_admitted"),
            patch.object(
                mutation_host.agent_owned_git,
                "execute_agent_owned_git",
                side_effect=lambda command, *, source, transport, authority_factory=None: (
                    transport.request(
                        "POST",
                        "repos/EAKerber/MobiliPresenter/git/trees",
                        payload={},
                    ),
                    transport.request(
                        "POST",
                        "repos/EAKerber/MobiliPresenter/git/commits",
                        payload={},
                    ),
                    transport.request(
                        "PATCH",
                        "repos/EAKerber/MobiliPresenter/git/refs/heads/work/operations/e3",
                        payload={},
                    ),
                    canonical_receipt,
                )[-1],
            ) as execute,
            patch.object(
                mutation_host.guard_proofs,
                "validate_proof_set",
                side_effect=lambda item, plan=None: item,
            ),
            patch.object(
                mutation_host.remote,
                "validate_receipt",
                side_effect=lambda item: item,
            ),
        ):
            outcome = mutation_host.execute_plan(
                value,
                source=source(),
                transport=FakeTransport(),
            )
        self.assertEqual(outcome["status"], "PASS")
        self.assertEqual(outcome["observedBranchHead"], NEW_HEAD)
        self.assertEqual(outcome["remoteReceipt"], canonical_receipt)
        execute.assert_called_once()

    @patch("tools.agent_tools.mutation_host.execute_plan")
    @patch("tools.agent_tools.mutation_host.resolver.resolve_request")
    @patch("tools.agent_tools.mutation_host.validate_outcome")
    def test_direct_request_uses_portable_lifecycle_and_agent_tool_source(
        self, validate_outcome, resolve, execute_plan
    ):
        value = plan()
        resolve.return_value = {"plan": value, "result": {}}
        outcome = {
            "status": "BLOCKED",
            "blockers": ["EXPECTED"],
        }
        execute_plan.return_value = outcome
        validate_outcome.return_value = outcome
        result = mutation_host.execute_request(
            {"request": "opaque"},
            {"context": "opaque"},
            cycle_instance_id="cycle-instance-" + "1" * 24,
            lifecycle_result={"resultHash": "a" * 64},
            lifecycle_result_ref={
                "kind": "provided-result",
                "value": "a" * 64,
            },
            invocation_id="direct-e3",
            transport=FakeTransport(),
        )
        self.assertEqual(result["result"]["status"], "BLOCKED")
        kwargs = execute_plan.call_args.kwargs
        self.assertEqual(kwargs["source"]["kind"], "agent-tool-host")
        self.assertEqual(
            kwargs["lifecycle_result_context"]["lifecycleResultRef"],
            {"kind": "provided-result", "value": "a" * 64},
        )


if __name__ == "__main__":
    unittest.main()
