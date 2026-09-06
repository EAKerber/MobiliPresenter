from __future__ import annotations

import copy
import json
import unittest

from tools import (
    agent_cycle_identity,
    hosted_cycle_handle,
    hosted_cycle_records,
    hosted_handle_requests,
)

REPOSITORY = "EAKerber/MobiliPresenter"
ACTOR = {
    "role": "manager-gitops",
    "workerId": "manager-gitops-a",
    "sessionId": "session-m13-absent-branch-record",
}
CONTEXT_HASH = "b" * 64


def manifest() -> dict:
    source = {
        "workflow": "hosted-agent-cycle",
        "runId": 123,
        "sourceSha": "a" * 40,
        "issueNumber": 145,
        "commentId": 100,
    }
    cycle_instance_id = agent_cycle_identity.hosted_cycle_instance_id(
        source, ACTOR, CONTEXT_HASH
    )
    return {
        "schemaVersion": "HostedAgentCycleBeginManifest 0.3",
        "requestId": "begin-m13-absent-branch-record",
        "commandHash": "c" * 64,
        "actor": copy.deepcopy(ACTOR),
        "declaredIntent": "governed-mutation",
        "machineScope": "live",
        "source": source,
        "artifactName": "agent-cycle-begin-123",
        "cycleId": "cycle-" + "d" * 20,
        "cycleInstanceId": cycle_instance_id,
        "contextHash": CONTEXT_HASH,
        "carrierFeatures": [
            "agent-write-lease-lifecycle-0.1",
            "execution-trace-0.1",
        ],
        "status": "READY",
        "semanticAuthority": False,
        "authorizesMutation": False,
        "manifestHash": "f" * 64,
    }


def handle_for(current: dict) -> dict:
    return agent_cycle_identity.build_handle(
        repository=REPOSITORY,
        cycle_id=current["cycleId"],
        cycle_instance_id=current["cycleInstanceId"],
        context_schema_version="AgentCycleContext 0.4",
        context_hash=current["contextHash"],
        actor=current["actor"],
        resume_token=hosted_cycle_handle.build_resume_token(current),
    )


def acquire_outer(current: dict) -> dict:
    return {
        "schemaVersion": hosted_handle_requests.WRITE_LEASE_SCHEMA,
        "requestId": "lease-m13-absent-branch-record",
        "handle": handle_for(current),
        "action": "acquire",
        "branch": "work/operations/m13-absent-branch-record",
        "expectedAuthorityHead": "2" * 40,
        "expectedBranchHead": None,
        "expectedBindingHash": None,
        "ttlSeconds": 600,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


def owner(comment_id: int, marker: str, payload: dict) -> dict:
    return {
        "id": comment_id,
        "author_association": "OWNER",
        "user": {"login": "EAKerber"},
        "body": marker + "\n" + json.dumps(payload),
    }


class HostedWriteLeaseBranchReservationRecordTests(unittest.TestCase):
    def test_absent_branch_acquire_is_a_strong_hosted_record(self) -> None:
        current = manifest()
        outer = acquire_outer(current)
        comments = [
            {
                "id": 100,
                "author_association": "OWNER",
                "user": {"login": "EAKerber"},
                "body": "begin",
            },
            owner(
                110,
                hosted_cycle_records.WRITE_LEASE_REQUEST_MARKER_V02,
                outer,
            ),
            {
                "id": 200,
                "author_association": "OWNER",
                "user": {"login": "EAKerber"},
                "body": "close",
            },
        ]

        view = hosted_cycle_records.collect(
            comments,
            current,
            close_comment_id=200,
        )
        records = hosted_cycle_records.records_of(
            view,
            "write-lease-request",
            binding=hosted_cycle_records.STRONG,
        )

        self.assertEqual(1, len(records))
        self.assertIsNone(records[0]["normalized"]["expectedBranchHead"])

    def test_release_still_requires_concrete_branch_head(self) -> None:
        current = manifest()
        value = acquire_outer(current)
        value["action"] = "release"
        value["expectedBindingHash"] = "e" * 64
        value["ttlSeconds"] = None

        with self.assertRaisesRegex(
            hosted_handle_requests.HostedHandleRequestError,
            "HOSTED_HANDLE_WRITE_LEASE_HEAD_INVALID",
        ):
            hosted_handle_requests.validate_write_lease(
                value,
                repository=REPOSITORY,
            )

    def test_acquire_rejects_non_sha_non_null_branch_head(self) -> None:
        current = manifest()
        value = acquire_outer(current)
        value["expectedBranchHead"] = "not-a-sha"

        with self.assertRaisesRegex(
            hosted_handle_requests.HostedHandleRequestError,
            "HOSTED_HANDLE_WRITE_LEASE_HEAD_INVALID",
        ):
            hosted_handle_requests.validate_write_lease(
                value,
                repository=REPOSITORY,
            )


if __name__ == "__main__":
    unittest.main()
