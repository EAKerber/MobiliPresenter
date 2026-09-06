from __future__ import annotations

import copy
import json
import unittest

from tools import agent_cycle_identity, agent_write_lifecycle, hosted_cycle_records


ACTOR = {
    "role": "manager-gitops",
    "workerId": "manager-gitops-a",
    "sessionId": "session-m13-lease-failure-record",
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
    return {
        "schemaVersion": "HostedAgentCycleBeginManifest 0.3",
        "requestId": "begin-m13-lease-failure-record",
        "commandHash": "c" * 64,
        "actor": copy.deepcopy(ACTOR),
        "declaredIntent": "governed-mutation",
        "machineScope": "live",
        "source": source,
        "artifactName": "agent-cycle-begin-123",
        "cycleId": "cycle-" + "d" * 20,
        "cycleInstanceId": agent_cycle_identity.hosted_cycle_instance_id(
            source, ACTOR, CONTEXT_HASH
        ),
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


def bot(comment_id: int, marker: str, payload: dict) -> dict:
    return {
        "id": comment_id,
        "author_association": "CONTRIBUTOR",
        "user": {"login": "github-actions[bot]"},
        "body": marker + "\n```json\n" + json.dumps(payload) + "\n```",
    }


class HostedWriteLeaseFailureRecordTests(unittest.TestCase):
    def test_blocked_lease_failure_remains_a_strong_lineage_record(self) -> None:
        current = manifest()
        begin = agent_cycle_identity.begin_from_manifest(current)
        request = {
            "schemaVersion": agent_write_lifecycle.REQUEST_SCHEMA,
            "requestId": "release-m13-failure-record",
            "action": "release",
            "begin": begin,
            "actor": copy.deepcopy(ACTOR),
            "branch": "work/operations/m13-failure-record",
            "expectedAuthorityHead": "1" * 40,
            "expectedBranchHead": "2" * 40,
            "expectedBindingHash": "3" * 64,
            "ttlSeconds": None,
            "semanticAuthority": False,
            "authorizesMutation": False,
        }
        agent_write_lifecycle.validate_request(request)
        failure = agent_write_lifecycle.build_failure(
            request,
            status="BLOCKED",
            blockers=["AGENT_WRITE_LIFECYCLE_DISPATCH_HOST_VALIDATION_FAILED"],
        )
        comments = [
            {
                "id": 100,
                "author_association": "OWNER",
                "user": {"login": "EAKerber"},
                "body": "begin",
            },
            bot(
                150,
                hosted_cycle_records.WRITE_LEASE_RESULT_MARKER,
                failure,
            ),
            {
                "id": 200,
                "author_association": "OWNER",
                "user": {"login": "EAKerber"},
                "body": "observation-cutoff",
            },
        ]

        view = hosted_cycle_records.collect(
            comments,
            current,
            close_comment_id=200,
        )
        records = hosted_cycle_records.records_of(
            view,
            "write-lease-failure",
            binding=hosted_cycle_records.STRONG,
        )

        self.assertEqual(1, len(records))
        self.assertEqual("BLOCKED", records[0]["normalized"]["status"])
        self.assertEqual(failure["failureHash"], records[0]["normalized"]["failureHash"])

    def test_tampered_failure_hash_is_rejected(self) -> None:
        current = manifest()
        begin = agent_cycle_identity.begin_from_manifest(current)
        request = {
            "schemaVersion": agent_write_lifecycle.REQUEST_SCHEMA,
            "requestId": "release-m13-tampered-failure-record",
            "action": "release",
            "begin": begin,
            "actor": copy.deepcopy(ACTOR),
            "branch": "work/operations/m13-failure-record",
            "expectedAuthorityHead": "1" * 40,
            "expectedBranchHead": "2" * 40,
            "expectedBindingHash": "3" * 64,
            "ttlSeconds": None,
            "semanticAuthority": False,
            "authorizesMutation": False,
        }
        failure = agent_write_lifecycle.build_failure(
            request,
            status="UNKNOWN",
            blockers=["AGENT_WRITE_LIFECYCLE_PROVIDER_UNKNOWN"],
        )
        failure["failureHash"] = "0" * 64
        comments = [
            {
                "id": 100,
                "author_association": "OWNER",
                "user": {"login": "EAKerber"},
                "body": "begin",
            },
            bot(
                150,
                hosted_cycle_records.WRITE_LEASE_RESULT_MARKER,
                failure,
            ),
            {
                "id": 200,
                "author_association": "OWNER",
                "user": {"login": "EAKerber"},
                "body": "observation-cutoff",
            },
        ]

        with self.assertRaisesRegex(
            hosted_cycle_records.HostedCycleRecordError,
            "HOSTED_CYCLE_RECORD_LEASE_FAILURE_HASH_MISMATCH",
        ):
            hosted_cycle_records.collect(comments, current, close_comment_id=200)


if __name__ == "__main__":
    unittest.main()
