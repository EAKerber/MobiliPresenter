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
from tools.agent_tools import trace_collect
from tools.canonical import stable_hash

REPOSITORY = "EAKerber/MobiliPresenter"
ACTOR = {
    "role": "manager-gitops",
    "workerId": "manager-gitops-a",
    "sessionId": "session-post-m13-invalid-lease",
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
        "requestId": "begin-post-m13-invalid-lease",
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
        context_schema_version="AgentCycleContext 0.3",
        context_hash=current["contextHash"],
        actor=current["actor"],
        resume_token=hosted_cycle_handle.build_resume_token(current),
    )


def lease_release(current: dict, *, ttl_seconds=None) -> dict:
    return {
        "schemaVersion": hosted_handle_requests.WRITE_LEASE_SCHEMA,
        "requestId": "release-post-m13-invalid-lease",
        "handle": handle_for(current),
        "action": "release",
        "branch": "work/operations/post-m13-invalid-lease",
        "expectedAuthorityHead": "1" * 40,
        "expectedBranchHead": "2" * 40,
        "expectedBindingHash": "3" * 64,
        "ttlSeconds": ttl_seconds,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


def owner(comment_id: int, payload: dict) -> dict:
    return {
        "id": comment_id,
        "author_association": "OWNER",
        "user": {"login": "EAKerber"},
        "body": (
            hosted_cycle_records.WRITE_LEASE_REQUEST_MARKER_V02
            + "\n"
            + json.dumps(payload)
        ),
    }


def boundary(comment_id: int, body: str) -> dict:
    return {
        "id": comment_id,
        "author_association": "OWNER",
        "user": {"login": "EAKerber"},
        "body": body,
    }


class HostedInvalidWriteLeaseRecordHardeningTests(unittest.TestCase):
    def test_exactly_bound_invalid_v02_is_diagnostic_and_does_not_poison_trace(self) -> None:
        current = manifest()
        invalid = lease_release(current, ttl_seconds=3600)
        valid = lease_release(current, ttl_seconds=None)
        valid["requestId"] = "release-post-m13-valid-lease"
        comments = [
            boundary(100, "begin"),
            owner(110, invalid),
            owner(120, valid),
            boundary(200, "close"),
        ]

        view = hosted_cycle_records.collect(
            comments, current, close_comment_id=200
        )
        invalid_records = hosted_cycle_records.records_of(
            view,
            "write-lease-invalid-request",
            binding=hosted_cycle_records.STRONG,
        )
        valid_records = hosted_cycle_records.records_of(
            view, "write-lease-request", binding=hosted_cycle_records.STRONG
        )

        self.assertEqual([item["commentId"] for item in invalid_records], [110])
        self.assertEqual([item["commentId"] for item in valid_records], [120])
        self.assertEqual(
            invalid_records[0]["normalized"],
            {
                "schemaVersion": "HostedCycleInvalidRecord 0.1",
                "recordType": "write-lease-request",
                "error": "HOSTED_HANDLE_WRITE_LEASE_CONTINUATION_INVALID",
                "payloadHash": stable_hash(invalid),
                "semanticAuthority": False,
                "authorizesMutation": False,
            },
        )
        self.assertIsNone(valid_records[0]["normalized"]["ttlSeconds"])

        trace = trace_collect.build_trace(
            comments, current, close_comment_id=200
        )
        self.assertEqual(trace["traceStatus"], "PASS")
        self.assertEqual(trace["summary"]["attemptCount"], 0)

    def test_invalid_v02_with_noncanonical_handle_remains_fatal(self) -> None:
        current = manifest()
        invalid = lease_release(current, ttl_seconds=3600)
        invalid["handle"]["resumeToken"] += "-tampered"
        comments = [
            boundary(100, "begin"),
            owner(110, invalid),
            boundary(200, "close"),
        ]

        with self.assertRaisesRegex(
            RuntimeError, "HOSTED_CYCLE_RECORD_LEASE_HANDLE_BINDING_MISMATCH"
        ):
            hosted_cycle_records.collect(
                comments, current, close_comment_id=200
            )


if __name__ == "__main__":
    unittest.main()
