from __future__ import annotations

import copy
import json
import unittest

from tools import (
    agent_cycle_identity,
    agent_write_lifecycle,
    hosted_cycle_handle,
    hosted_cycle_records,
    hosted_handle_requests,
    remote_canonical_execution,
)
from tools.agent_tools import contracts

REPOSITORY = "EAKerber/MobiliPresenter"
ACTOR = {"role": "manager-gitops", "workerId": "manager-gitops-a", "sessionId": "session-r3b0a"}
CONTEXT_HASH = "b" * 64


def manifest(*, run_id: int = 123, begin_comment_id: int = 100) -> dict:
    source = {
        "workflow": "hosted-agent-cycle",
        "runId": run_id,
        "sourceSha": "a" * 40,
        "issueNumber": 145,
        "commentId": begin_comment_id,
    }
    cycle_instance_id = agent_cycle_identity.hosted_cycle_instance_id(source, ACTOR, CONTEXT_HASH)
    return {
        "schemaVersion": "HostedAgentCycleBeginManifest 0.3",
        "requestId": f"begin-{run_id}",
        "commandHash": "c" * 64,
        "actor": copy.deepcopy(ACTOR),
        "declaredIntent": "governed-mutation",
        "machineScope": "live",
        "source": source,
        "artifactName": f"agent-cycle-begin-{run_id}",
        "cycleId": "cycle-" + ("d" if run_id == 123 else "e") * 20,
        "cycleInstanceId": cycle_instance_id,
        "contextHash": CONTEXT_HASH,
        "carrierFeatures": ["agent-write-lease-lifecycle-0.1", "execution-trace-0.1"],
        "status": "READY",
        "semanticAuthority": False,
        "authorizesMutation": False,
        "manifestHash": "f" * 64,
    }


def begin_ref(current: dict) -> dict:
    return {
        "runId": current["source"]["runId"],
        "sourceSha": current["source"]["sourceSha"],
        "contextHash": current["contextHash"],
    }


def handle_for(current: dict) -> dict:
    return agent_cycle_identity.build_handle(
        repository=REPOSITORY,
        cycle_id=current["cycleId"],
        cycle_instance_id=current["cycleInstanceId"],
        context_schema_version="AgentCycleContext 0.3",
        context_hash=current["contextHash"],
        actor=current["actor"],
        resume_token=hosted_cycle_handle.build_resume_token(current),
    )


def owner(comment_id: int, marker: str, payload: dict) -> dict:
    return {
        "id": comment_id,
        "author_association": "OWNER",
        "user": {"login": "EAKerber"},
        "body": marker + "\n" + json.dumps(payload),
    }


def bot(comment_id: int, marker: str, payload: dict) -> dict:
    return {
        "id": comment_id,
        "author_association": "NONE",
        "user": {"login": "github-actions[bot]"},
        "body": marker + "\n```json\n" + json.dumps(payload) + "\n```",
    }


def boundaries(begin_id: int = 100, close_id: int = 200) -> list[dict]:
    return [
        {"id": begin_id, "author_association": "OWNER", "user": {"login": "EAKerber"}, "body": "begin"},
        {"id": close_id, "author_association": "OWNER", "user": {"login": "EAKerber"}, "body": "close"},
    ]


def tool_inner(current: dict) -> dict:
    return contracts.validate_request({
        "schemaVersion": contracts.REQUEST_SCHEMA,
        "requestId": "tool-r3b0a",
        "begin": begin_ref(current),
        "actor": copy.deepcopy(ACTOR),
        "toolId": "project.inspect",
        "target": {},
        "input": {},
        "semanticAuthority": False,
        "authorizesMutation": False,
    })


def remote_command() -> dict:
    return remote_canonical_execution.validate_command({
        "schemaVersion": "RemoteCanonicalCommand 0.1",
        "executionId": "remote-r3b0a",
        "kind": "git-direct",
        "actor": copy.deepcopy(ACTOR),
        "declaredIntent": {"goal": "test"},
        "target": {"operation": "create-file", "branch": "work/operations/r3b0a", "path": "docs/r3b0a.txt"},
        "expected": {"branchHead": "1" * 40},
        "payload": {"content": "x", "message": "test"},
        "semanticAuthority": False,
        "authorizesMutation": False,
    })


def lease_inner(current: dict) -> dict:
    return agent_write_lifecycle.validate_request({
        "schemaVersion": agent_write_lifecycle.REQUEST_SCHEMA,
        "requestId": "lease-r3b0a",
        "action": "acquire",
        "begin": begin_ref(current),
        "actor": copy.deepcopy(ACTOR),
        "branch": "work/operations/r3b0a",
        "expectedAuthorityHead": "2" * 40,
        "expectedBranchHead": "3" * 40,
        "expectedBindingHash": None,
        "ttlSeconds": 600,
        "semanticAuthority": False,
        "authorizesMutation": False,
    })


class HostedCycleRecordR3B0ATests(unittest.TestCase):
    def test_tool_v01_and_v02_normalize_to_same_inner_request(self) -> None:
        current = manifest()
        inner = tool_inner(current)
        outer = {
            "schemaVersion": hosted_handle_requests.TOOL_SCHEMA,
            "requestId": inner["requestId"],
            "handle": handle_for(current),
            "toolId": inner["toolId"],
            "target": copy.deepcopy(inner["target"]),
            "input": copy.deepcopy(inner["input"]),
            "semanticAuthority": False,
            "authorizesMutation": False,
        }
        edges = boundaries()
        legacy = hosted_cycle_records.collect(
            [edges[0], owner(110, hosted_cycle_records.AGENT_TOOL_REQUEST_MARKER, inner), edges[1]],
            current,
            close_comment_id=200,
        )
        handle_first = hosted_cycle_records.collect(
            [edges[0], owner(110, hosted_cycle_records.AGENT_TOOL_REQUEST_MARKER_V02, outer), edges[1]],
            current,
            close_comment_id=200,
        )
        left = hosted_cycle_records.records_of(legacy, "agent-tool-request", binding=hosted_cycle_records.STRONG)
        right = hosted_cycle_records.records_of(handle_first, "agent-tool-request", binding=hosted_cycle_records.STRONG)
        self.assertEqual(left[0]["normalized"], right[0]["normalized"])
        self.assertEqual(contracts.request_hash(left[0]["normalized"]), contracts.request_hash(right[0]["normalized"]))

    def test_write_lease_v01_and_v02_normalize_to_same_inner_request(self) -> None:
        current = manifest()
        inner = lease_inner(current)
        outer = {
            "schemaVersion": hosted_handle_requests.WRITE_LEASE_SCHEMA,
            "requestId": inner["requestId"],
            "handle": handle_for(current),
            "action": inner["action"],
            "branch": inner["branch"],
            "expectedAuthorityHead": inner["expectedAuthorityHead"],
            "expectedBranchHead": inner["expectedBranchHead"],
            "expectedBindingHash": None,
            "ttlSeconds": inner["ttlSeconds"],
            "semanticAuthority": False,
            "authorizesMutation": False,
        }
        edges = boundaries()
        legacy = hosted_cycle_records.collect(
            [edges[0], owner(110, agent_write_lifecycle.REQUEST_MARKER, inner), edges[1]],
            current,
            close_comment_id=200,
        )
        handle_first = hosted_cycle_records.collect(
            [edges[0], owner(110, hosted_cycle_records.WRITE_LEASE_REQUEST_MARKER_V02, outer), edges[1]],
            current,
            close_comment_id=200,
        )
        left = hosted_cycle_records.records_of(legacy, "write-lease-request", binding=hosted_cycle_records.STRONG)
        right = hosted_cycle_records.records_of(handle_first, "write-lease-request", binding=hosted_cycle_records.STRONG)
        self.assertEqual(left[0]["normalized"], right[0]["normalized"])

    def test_direct_remote_is_ambient_even_for_same_actor(self) -> None:
        current = manifest()
        edges = boundaries()
        view = hosted_cycle_records.collect(
            [edges[0], owner(120, hosted_cycle_records.REMOTE_REQUEST_MARKER, remote_command()), edges[1]],
            current,
            close_comment_id=200,
        )
        ambient = hosted_cycle_records.records_of(view, "remote-request", binding=hosted_cycle_records.AMBIENT)
        strong = hosted_cycle_records.records_of(view, "remote-request", binding=hosted_cycle_records.STRONG)
        self.assertEqual(len(ambient), 1)
        self.assertEqual(strong, [])

    def test_overlapping_same_actor_cycles_do_not_promote_ambient_remote_to_strong(self) -> None:
        first = manifest(run_id=123, begin_comment_id=100)
        second = manifest(run_id=124, begin_comment_id=105)
        command = remote_command()
        comments = [
            {"id": 100, "author_association": "OWNER", "user": {"login": "EAKerber"}, "body": "begin-1"},
            {"id": 105, "author_association": "OWNER", "user": {"login": "EAKerber"}, "body": "begin-2"},
            owner(150, hosted_cycle_records.REMOTE_REQUEST_MARKER, command),
            {"id": 200, "author_association": "OWNER", "user": {"login": "EAKerber"}, "body": "close-1"},
            {"id": 205, "author_association": "OWNER", "user": {"login": "EAKerber"}, "body": "close-2"},
        ]
        first_view = hosted_cycle_records.collect(comments, first, close_comment_id=200)
        second_view = hosted_cycle_records.collect(comments, second, close_comment_id=205)
        for view in (first_view, second_view):
            self.assertEqual(len(hosted_cycle_records.records_of(view, "remote-request", binding=hosted_cycle_records.AMBIENT)), 1)
            self.assertEqual(hosted_cycle_records.records_of(view, "remote-request", binding=hosted_cycle_records.STRONG), [])

    def test_malformed_unrelated_tool_request_is_ignored(self) -> None:
        current = manifest()
        unrelated = {
            "schemaVersion": contracts.REQUEST_SCHEMA,
            "requestId": "broken-other",
            "begin": {**begin_ref(current), "runId": 999},
            "actor": copy.deepcopy(ACTOR),
            "semanticAuthority": False,
            "authorizesMutation": False,
        }
        edges = boundaries()
        view = hosted_cycle_records.collect(
            [edges[0], owner(110, hosted_cycle_records.AGENT_TOOL_REQUEST_MARKER, unrelated), edges[1]],
            current,
            close_comment_id=200,
        )
        self.assertEqual(view["records"], [])

    def test_malformed_record_claiming_current_cycle_fails_closed(self) -> None:
        current = manifest()
        malformed = {
            "schemaVersion": contracts.REQUEST_SCHEMA,
            "requestId": "broken-current",
            "begin": begin_ref(current),
            "actor": copy.deepcopy(ACTOR),
            "semanticAuthority": False,
            "authorizesMutation": False,
        }
        edges = boundaries()
        with self.assertRaisesRegex(RuntimeError, "HOSTED_CYCLE_RECORD_TOOL_REQUEST_INVALID"):
            hosted_cycle_records.collect(
                [edges[0], owner(110, hosted_cycle_records.AGENT_TOOL_REQUEST_MARKER, malformed), edges[1]],
                current,
                close_comment_id=200,
            )

    def test_explicit_instance_mismatch_never_falls_back_to_actor(self) -> None:
        current = manifest()
        mismatched = {
            "cycleInstanceId": "cycle-instance-" + "0" * 24,
            "begin": begin_ref(current),
            "actor": copy.deepcopy(ACTOR),
        }
        edges = boundaries()
        view = hosted_cycle_records.collect(
            [edges[0], bot(110, hosted_cycle_records.AGENT_TOOL_DISPATCH_MARKER, mismatched), edges[1]],
            current,
            close_comment_id=200,
        )
        self.assertEqual(view["records"], [])

    def test_unknown_marker_never_becomes_generic_record(self) -> None:
        current = manifest()
        edges = boundaries()
        unknown = owner(110, "MOBILIPRESENTER_UNKNOWN_V0_1", {"actor": ACTOR})
        view = hosted_cycle_records.collect([edges[0], unknown, edges[1]], current, close_comment_id=200)
        self.assertEqual(view["records"], [])


if __name__ == "__main__":
    unittest.main()
