from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from tools import (
    agent_cycle_identity,
    agent_cycle_resource_collect,
    agent_cycle_resources,
    agent_write_lifecycle,
    git_mutation_plan,
    hosted_agent_cycle_trace,
    hosted_cycle_handle,
    hosted_handle_requests,
    remote_canonical_execution,
    transition_protocol,
)
from tools.agent_tools import mutation_dispatch, trace_collect
from tools.canonical import stable_hash

REPOSITORY = "EAKerber/MobiliPresenter"
ACTOR = {
    "role": "manager-gitops",
    "workerId": "manager-gitops-a",
    "sessionId": "session-1",
}
BEGIN = {"runId": 123, "sourceSha": "a" * 40, "contextHash": "b" * 64}


def manifest() -> dict[str, object]:
    source = {
        "workflow": "hosted-agent-cycle",
        "runId": 123,
        "sourceSha": "a" * 40,
        "issueNumber": 145,
        "commentId": 100,
    }
    cycle_instance_id = agent_cycle_identity.hosted_cycle_instance_id(
        source, ACTOR, BEGIN["contextHash"]
    )
    return {
        "schemaVersion": "HostedAgentCycleBeginManifest 0.3",
        "requestId": "begin-one",
        "commandHash": "c" * 64,
        "actor": copy.deepcopy(ACTOR),
        "declaredIntent": "governed-mutation",
        "machineScope": "live",
        "source": source,
        "artifactName": "agent-cycle-begin-123",
        "cycleId": "cycle-" + "d" * 20,
        "cycleInstanceId": cycle_instance_id,
        "contextHash": BEGIN["contextHash"],
        "carrierFeatures": [
            "agent-write-lease-lifecycle-0.1",
            "execution-trace-0.1",
        ],
        "status": "READY",
        "semanticAuthority": False,
        "authorizesMutation": False,
        "manifestHash": "e" * 64,
    }


def handle_for(current: dict[str, object]) -> dict[str, object]:
    return agent_cycle_identity.build_handle(
        repository=REPOSITORY,
        cycle_id=current["cycleId"],
        cycle_instance_id=current["cycleInstanceId"],
        context_schema_version="AgentCycleContext 0.3",
        context_hash=current["contextHash"],
        actor=current["actor"],
        resume_token=hosted_cycle_handle.build_resume_token(current),
    )


def owner_comment(
    comment_id: int, marker: str, payload: dict[str, object]
) -> dict[str, object]:
    return {
        "id": comment_id,
        "author_association": "OWNER",
        "user": {"login": "EAKerber"},
        "body": marker + "\n" + json.dumps(payload),
    }


def bot_comment(
    comment_id: int, marker: str, payload: dict[str, object]
) -> dict[str, object]:
    return {
        "id": comment_id,
        "author_association": "NONE",
        "user": {"login": "github-actions[bot]"},
        "body": marker + "\n```json\n" + json.dumps(payload) + "\n```",
    }


def remote_create_file(actor: dict[str, str] | None = None) -> dict[str, object]:
    value = {
        "schemaVersion": "RemoteCanonicalCommand 0.1",
        "executionId": "remote-one",
        "kind": "git-direct",
        "actor": copy.deepcopy(ACTOR if actor is None else actor),
        "declaredIntent": {"goal": "test"},
        "target": {
            "operation": "create-file",
            "branch": "work/operations/example",
            "path": "docs/example.txt",
        },
        "expected": {"branchHead": "f" * 40},
        "payload": {"content": "x", "message": "test"},
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return remote_canonical_execution.validate_command(value)


def lease_request() -> dict[str, object]:
    value = {
        "schemaVersion": agent_write_lifecycle.REQUEST_SCHEMA,
        "requestId": "lease-acquire-one",
        "action": "acquire",
        "begin": copy.deepcopy(BEGIN),
        "actor": copy.deepcopy(ACTOR),
        "branch": "work/operations/example",
        "expectedAuthorityHead": "1" * 40,
        "expectedBranchHead": "2" * 40,
        "expectedBindingHash": None,
        "ttlSeconds": 600,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return agent_write_lifecycle.validate_request(value)


class AgentCycleTouchedResourceR3ATests(unittest.TestCase):
    def test_resource_identity_excludes_mutable_git_state(self):
        first = git_mutation_plan.update_file(
            branch="work/operations/example",
            path="docs/example.txt",
            branch_head="1" * 40,
            blob_sha="2" * 40,
            content_sha256="3" * 64,
            control_branch="main",
        )
        second = git_mutation_plan.update_file(
            branch="work/operations/example",
            path="docs/example.txt",
            branch_head="4" * 40,
            blob_sha="5" * 40,
            content_sha256="6" * 64,
            control_branch="main",
        )
        left = agent_cycle_resources.resources_from_git_plan(first)
        right = agent_cycle_resources.resources_from_git_plan(second)
        left_by_kind = {item["kind"]: item for item in left}
        right_by_kind = {item["kind"]: item for item in right}
        self.assertEqual(
            left_by_kind["git-path"]["resourceHash"],
            right_by_kind["git-path"]["resourceHash"],
        )
        self.assertNotEqual(
            left_by_kind["git-path"]["origins"],
            right_by_kind["git-path"]["origins"],
        )
        self.assertNotIn("branchHead", left_by_kind["git-path"]["locator"])
        self.assertNotIn("blobSha", left_by_kind["git-path"]["locator"])

    def test_pr_operations_are_not_promoted_without_a_strong_runtime_producer(self):
        create = git_mutation_plan.create_pr(
            head="work/operations/example",
            base="main",
            head_sha="1" * 40,
            title="R3B1",
            body_sha256="2" * 64,
            control_branch="main",
        )
        merge = git_mutation_plan.merge_pr(
            pr_number=77,
            head_sha="1" * 40,
            base="main",
            control_branch="main",
        )
        for plan in (create, merge):
            with self.subTest(operation=plan["operation"]):
                with self.assertRaisesRegex(
                    RuntimeError, "AGENT_CYCLE_RESOURCE_GIT_OPERATION_UNSUPPORTED"
                ):
                    agent_cycle_resources.resources_from_git_plan(plan)

    def test_transition_plan_projects_subject_not_candidate_state(self):
        plan = transition_protocol.build_plan(
            domain="continuation",
            action="advance",
            subject={"kind": "continuation", "id": "work-one"},
            authority={
                "kind": "git",
                "locator": {
                    "branch": "authority/continuations",
                    "path": "work-one.json",
                },
            },
            before={"schemaVersion": "X", "status": "READY"},
            candidate={"schemaVersion": "X", "status": "IN_PROGRESS"},
            intent={"reason": "test"},
        )
        projected = agent_cycle_resources.resources_from_transition_plan(plan)[0]
        self.assertEqual(
            projected["locator"],
            {
                "domain": "continuation",
                "subjectKind": "continuation",
                "subjectId": "work-one",
            },
        )
        self.assertNotIn("status", projected["locator"])

    def test_lease_request_projects_scope_before_lease_id_exists(self):
        projected = agent_cycle_resources.resources_from_write_lease_request(
            lease_request()
        )[0]
        self.assertEqual(projected["kind"], "lease-scope")
        self.assertEqual(
            projected["locator"],
            {
                "repository": REPOSITORY,
                "branch": "work/operations/example",
                "role": "manager-gitops",
                "sessionId": "session-1",
            },
        )
        self.assertNotIn("leaseId", projected["locator"])
        self.assertNotIn("workerId", projected["locator"])

    def test_union_is_order_independent_and_merges_provenance_without_summary(self):
        a = agent_cycle_resources.resource(
            "git-branch",
            {"repository": REPOSITORY, "branch": "work/operations/example"},
            agent_cycle_resources.origin("one", "1" * 64, "write"),
        )
        b = agent_cycle_resources.resource(
            "git-branch",
            {"repository": REPOSITORY, "branch": "work/operations/example"},
            agent_cycle_resources.origin("two", "2" * 64, "readback"),
        )
        left = agent_cycle_resources.build_resource_set(
            repository=REPOSITORY,
            cycle_instance_id="cycle-instance-" + "a" * 24,
            resources=[a, b],
        )
        right = agent_cycle_resources.build_resource_set(
            repository=REPOSITORY,
            cycle_instance_id="cycle-instance-" + "a" * 24,
            resources=[b, a],
        )
        self.assertEqual(left, right)
        self.assertNotIn("sourceSummary", left)
        self.assertEqual(len(left["resources"]), 1)
        self.assertEqual(len(left["resources"][0]["origins"]), 2)
        self.assertEqual(left["coverage"], agent_cycle_resources.coverage())
        self.assertFalse(left["semanticAuthority"])
        self.assertFalse(left["authorizesMutation"])

    def test_rehashed_projection_cannot_claim_authority(self):
        item = agent_cycle_resources.resource(
            "git-branch",
            {"repository": REPOSITORY, "branch": "work/operations/example"},
            agent_cycle_resources.origin("one", "1" * 64, "write"),
        )
        value = agent_cycle_resources.build_resource_set(
            repository=REPOSITORY,
            cycle_instance_id="cycle-instance-" + "a" * 24,
            resources=[item],
        )
        tampered = copy.deepcopy(value)
        tampered["semanticAuthority"] = True
        core = {
            key: copy.deepcopy(entry)
            for key, entry in tampered.items()
            if key != "resourceSetHash"
        }
        tampered["resourceSetHash"] = stable_hash(core)
        with self.assertRaisesRegex(
            RuntimeError, "AGENT_CYCLE_RESOURCE_SET_MISMATCH"
        ):
            agent_cycle_resources.validate_resource_set(tampered)

    def test_ambient_direct_remote_records_do_not_enter_semantic_resource_set(self):
        current = manifest()
        other_actor = copy.deepcopy(ACTOR)
        other_actor["sessionId"] = "other-session"
        comments = [
            {
                "id": 100,
                "author_association": "OWNER",
                "user": {"login": "EAKerber"},
                "body": "begin",
            },
            owner_comment(110, trace_collect.REMOTE_REQUEST_MARKER, remote_create_file()),
            owner_comment(
                120,
                trace_collect.REMOTE_REQUEST_MARKER,
                remote_create_file(other_actor),
            ),
            {
                "id": 200,
                "author_association": "OWNER",
                "user": {"login": "EAKerber"},
                "body": "close",
            },
        ]
        value = agent_cycle_resource_collect.build_resource_set(
            comments, current, close_comment_id=200
        )
        self.assertEqual(value["resources"], [])
        self.assertEqual(value["coverage"]["status"], "UNKNOWN")

    def test_agent_tool_dispatch_contributes_declared_targets_before_apply(self):
        current = manifest()
        command = remote_create_file()
        core = {
            "schemaVersion": mutation_dispatch.DISPATCH_SCHEMA,
            "cycleInstanceId": current["cycleInstanceId"],
            "requestHash": "1" * 64,
            "planHash": "2" * 64,
            "proofSetHash": "3" * 64,
            "begin": copy.deepcopy(BEGIN),
            "actor": copy.deepcopy(ACTOR),
            "toolId": "git.files.mutate",
            "targetPolicy": "manager-non-control-git",
            "command": command,
            "commandHash": remote_canonical_execution.command_hash(command),
            "source": {
                "issueNumber": 145,
                "requestCommentId": 109,
                "hostedRunId": 456,
                "semanticHostSha": BEGIN["sourceSha"],
            },
            "semanticAuthority": False,
            "authorizesMutation": False,
        }
        dispatch = {**core, "dispatchHash": stable_hash(core)}
        mutation_dispatch.validate_dispatch(dispatch)
        comments = [
            {
                "id": 100,
                "author_association": "OWNER",
                "user": {"login": "EAKerber"},
                "body": "begin",
            },
            bot_comment(110, trace_collect.AGENT_TOOL_DISPATCH_MARKER, dispatch),
            {
                "id": 200,
                "author_association": "OWNER",
                "user": {"login": "EAKerber"},
                "body": "close",
            },
        ]
        value = agent_cycle_resource_collect.build_resource_set(
            comments, current, close_comment_id=200
        )
        self.assertEqual(len(value["resources"]), 2)
        self.assertEqual(
            {
                origin["sourceKind"]
                for item in value["resources"]
                for origin in item["origins"]
            },
            {"agent-tool-mutation-dispatch"},
        )

    def test_v01_and_handle_first_lease_requests_converge_to_same_resource(self):
        current = manifest()
        inner = lease_request()
        outer = {
            "schemaVersion": hosted_handle_requests.WRITE_LEASE_SCHEMA,
            "requestId": inner["requestId"],
            "handle": handle_for(current),
            "action": inner["action"],
            "branch": inner["branch"],
            "expectedAuthorityHead": inner["expectedAuthorityHead"],
            "expectedBranchHead": inner["expectedBranchHead"],
            "expectedBindingHash": inner["expectedBindingHash"],
            "ttlSeconds": inner["ttlSeconds"],
            "semanticAuthority": False,
            "authorizesMutation": False,
        }
        hosted_handle_requests.validate_write_lease(outer, repository=REPOSITORY)
        base = [
            {
                "id": 100,
                "author_association": "OWNER",
                "user": {"login": "EAKerber"},
                "body": "begin",
            },
            {
                "id": 200,
                "author_association": "OWNER",
                "user": {"login": "EAKerber"},
                "body": "close",
            },
        ]
        legacy_comments = [
            base[0],
            owner_comment(110, agent_write_lifecycle.REQUEST_MARKER, inner),
            base[1],
        ]
        handle_comments = [
            base[0],
            owner_comment(
                110, hosted_handle_requests.WRITE_LEASE_MARKER_V02, outer
            ),
            base[1],
        ]
        legacy = agent_cycle_resource_collect.build_resource_set(
            legacy_comments, current, close_comment_id=200
        )
        handle_first = agent_cycle_resource_collect.build_resource_set(
            handle_comments, current, close_comment_id=200
        )
        self.assertEqual(legacy, handle_first)

    def test_shadow_materialization_reuses_one_trace_observation(self):
        current = manifest()
        comments = [
            {
                "id": 100,
                "author_association": "OWNER",
                "user": {"login": "EAKerber"},
                "body": "begin",
            },
            {
                "id": 200,
                "author_association": "OWNER",
                "user": {"login": "EAKerber"},
                "body": "close",
            },
        ]
        fetcher = Mock(return_value=comments)
        command = {"evidenceCommentIds": []}
        meta = {"issueNumber": 145, "commentId": 200}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "agent-cycle-touched-resources.json"
            amended, trace = hosted_agent_cycle_trace.prepare_close_stabilized(
                command,
                meta,
                current,
                {},
                repository=REPOSITORY,
                fetch_comments=fetcher,
                sleep=lambda _seconds: None,
                attempts=1,
                resource_output_path=str(path),
            )
            self.assertEqual(amended, command)
            self.assertEqual(trace["traceStatus"], "PASS")
            self.assertEqual(fetcher.call_count, 1)
            value = json.loads(path.read_text(encoding="utf-8"))
            agent_cycle_resources.validate_resource_set(value)
            self.assertEqual(value["resources"], [])
            self.assertEqual(value["coverage"]["status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
