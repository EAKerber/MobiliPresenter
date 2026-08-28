from __future__ import annotations

import copy
import unittest
from unittest.mock import patch

from tools import agent_cycle_identity, hosted_cycle_artifact, hosted_cycle_handle
from tools.canonical import stable_hash

RUN_ID = 123
SOURCE_SHA = "a" * 40
CONTEXT_HASH = "b" * 64
CYCLE_ID = "cycle-" + "c" * 20
CYCLE_INSTANCE_ID = "cycle-instance-" + "d" * 24
ARTIFACT_NAME = f"agent-cycle-begin-{RUN_ID}"
ACTOR = {
    "role": "manager-gitops",
    "workerId": "manager-gitops-a",
    "sessionId": "session-r2c1",
}


def manifest() -> dict:
    return {
        "schemaVersion": "HostedAgentCycleBeginManifest 0.3",
        "requestId": "r2c1-begin",
        "commandHash": "e" * 64,
        "actor": copy.deepcopy(ACTOR),
        "declaredIntent": "inspect-and-plan",
        "machineScope": "live",
        "source": {
            "workflow": "hosted-agent-cycle",
            "sourceSha": SOURCE_SHA,
            "runId": RUN_ID,
            "issueNumber": 145,
            "commentId": 9001,
        },
        "artifactName": ARTIFACT_NAME,
        "cycleId": CYCLE_ID,
        "cycleInstanceId": CYCLE_INSTANCE_ID,
        "contextHash": CONTEXT_HASH,
        "carrierFeatures": ["agent-write-lease-lifecycle-0.1", "execution-trace-0.1"],
        "status": "READY",
        "semanticAuthority": False,
        "authorizesMutation": False,
        "manifestHash": "f" * 64,
    }


def handle() -> dict:
    value = manifest()
    return agent_cycle_identity.build_handle(
        repository="EAKerber/MobiliPresenter",
        cycle_id=CYCLE_ID,
        cycle_instance_id=CYCLE_INSTANCE_ID,
        context_schema_version="AgentCycleContext 0.3",
        context_hash=CONTEXT_HASH,
        actor=ACTOR,
        resume_token=hosted_cycle_handle.build_resume_token(value),
    )


def begin_result() -> dict:
    core = {
        "schemaVersion": hosted_cycle_artifact.LEGACY_BEGIN_RESULT_SCHEMA,
        "requestId": "r2c1-begin",
        "commandHash": "e" * 64,
        "runId": RUN_ID,
        "sourceSha": SOURCE_SHA,
        "artifactName": ARTIFACT_NAME,
        "cycleId": CYCLE_ID,
        "cycleInstanceId": CYCLE_INSTANCE_ID,
        "contextHash": CONTEXT_HASH,
        "carrierFeatures": ["agent-write-lease-lifecycle-0.1", "execution-trace-0.1"],
        "manifestHash": "f" * 64,
        "handle": handle(),
        "status": "READY",
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**core, "resultHash": stable_hash(core)}


def artifact(*, expired: bool = False, head_sha: str = SOURCE_SHA, artifact_id: int = 77) -> dict:
    return {
        "id": artifact_id,
        "name": ARTIFACT_NAME,
        "expired": expired,
        "expires_at": "2026-09-11T12:00:00Z",
        "workflow_run": {"id": RUN_ID, "head_sha": head_sha},
    }


def response(items: list[dict]) -> dict:
    return {"total_count": len(items), "artifacts": items}


def begin_command() -> dict:
    return {
        "schemaVersion": "HostedAgentCycleCommand 0.1",
        "requestId": "r2c1-begin",
        "action": "begin",
        "actor": copy.deepcopy(ACTOR),
        "declaredIntent": "inspect-and-plan",
        "machineScope": "live",
        "begin": None,
        "evidenceCommentIds": [],
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


class HostedCycleArtifactR2C1Tests(unittest.TestCase):
    def classify(self, payload: dict) -> dict:
        return hosted_cycle_artifact.classify_artifact_response(
            payload,
            run_id=RUN_ID,
            artifact_name=ARTIFACT_NAME,
            source_sha=SOURCE_SHA,
        )

    def test_exact_live_artifact_is_available(self):
        value = self.classify(response([artifact()]))
        self.assertEqual("AVAILABLE", value["state"])
        self.assertEqual(77, value["artifactId"])
        self.assertEqual(SOURCE_SHA, value["headSha"])
        self.assertEqual([], value["reasonCodes"])
        hosted_cycle_artifact.validate_projection(value)

    def test_provider_expired_bit_is_authoritative_for_expiry_classification(self):
        value = self.classify(response([artifact(expired=True)]))
        self.assertEqual("EXPIRED", value["state"])
        self.assertEqual(["HOSTED_AGENT_BEGIN_ARTIFACT_EXPIRED"], value["reasonCodes"])

    def test_local_wall_clock_is_not_used_to_override_provider_state(self):
        old = artifact(expired=False)
        old["expires_at"] = "2000-01-01T00:00:00Z"
        value = self.classify(response([old]))
        self.assertEqual("AVAILABLE", value["state"])
        self.assertEqual("2000-01-01T00:00:00Z", value["expiresAt"])

    def test_missing_ambiguous_and_head_mismatch_are_distinct(self):
        self.assertEqual("MISSING", self.classify(response([]))["state"])
        self.assertEqual(
            "AMBIGUOUS",
            self.classify(response([artifact(artifact_id=1), artifact(artifact_id=2)]))["state"],
        )
        mismatch = self.classify(response([artifact(head_sha="9" * 40)]))
        self.assertEqual("MISMATCH", mismatch["state"])
        self.assertEqual(["HOSTED_AGENT_BEGIN_ARTIFACT_MISMATCH"], mismatch["reasonCodes"])

    def test_malformed_or_truncated_provider_response_is_unknown_not_missing(self):
        malformed = hosted_cycle_artifact.classify_artifact_response(
            {"total_count": 1, "artifacts": "not-a-list"},
            run_id=RUN_ID,
            artifact_name=ARTIFACT_NAME,
            source_sha=SOURCE_SHA,
        )
        self.assertEqual("UNKNOWN", malformed["state"])
        truncated = self.classify({"total_count": 2, "artifacts": [artifact()]})
        self.assertEqual("UNKNOWN", truncated["state"])
        self.assertIn("HOSTED_AGENT_BEGIN_ARTIFACT_LIST_INCOMPLETE", truncated["reasonCodes"])

    def test_provider_observation_failure_is_unknown(self):
        with patch(
            "tools.hosted_cycle_artifact._gh_artifacts",
            side_effect=hosted_cycle_artifact.HostedCycleArtifactError(
                "HOSTED_AGENT_BEGIN_ARTIFACT_OBSERVATION_FAILED"
            ),
        ):
            value = hosted_cycle_artifact.observe_begin_artifact(
                repository="EAKerber/MobiliPresenter",
                run_id=RUN_ID,
                source_sha=SOURCE_SHA,
            )
        self.assertEqual("UNKNOWN", value["state"])
        self.assertEqual(
            ["HOSTED_AGENT_BEGIN_ARTIFACT_OBSERVATION_FAILED"],
            value["reasonCodes"],
        )

    def test_begin_result_is_promoted_without_changing_handle(self):
        observation = self.classify(response([artifact()]))
        original = begin_result()
        promoted = hosted_cycle_artifact.finalize_begin_result(
            original, manifest(), observation
        )
        self.assertEqual(hosted_cycle_artifact.BEGIN_RESULT_SCHEMA, promoted["schemaVersion"])
        self.assertEqual(original["handle"], promoted["handle"])
        self.assertEqual(observation, promoted["resumability"])
        self.assertEqual(
            stable_hash({key: item for key, item in promoted.items() if key != "resultHash"}),
            promoted["resultHash"],
        )
        self.assertEqual(
            promoted,
            hosted_cycle_artifact.finalize_begin_result(promoted, manifest(), observation),
        )

    def test_unknown_observation_uses_existing_failure_core_without_claiming_pass(self):
        observation = self.classify({"total_count": 2, "artifacts": [artifact()]})
        failure = hosted_cycle_artifact.failure_for_observation(
            begin_command(), observation
        )
        self.assertEqual("BLOCKED", failure["status"])
        self.assertEqual("UNKNOWN", failure["failureCore"]["status"])
        self.assertEqual("SAFE", failure["failureCore"]["recovery"]["observationRetry"])
        self.assertFalse(failure["failureCore"]["authorizesMutation"])

    def test_expired_observation_is_terminally_blocked_without_replay_authority(self):
        observation = self.classify(response([artifact(expired=True)]))
        failure = hosted_cycle_artifact.failure_for_observation(
            begin_command(), observation
        )
        self.assertEqual("BLOCKED", failure["failureCore"]["status"])
        self.assertEqual(
            "NOT_APPLICABLE",
            failure["failureCore"]["recovery"]["operationReplay"],
        )
        self.assertEqual("NOT_APPLICABLE", failure["failureCore"]["mutationState"])

    def test_download_failure_after_reobserved_available_is_unknown(self):
        observation = self.classify(response([artifact()]))
        failure = hosted_cycle_artifact.failure_for_observation(
            begin_command(), observation, download_failed=True
        )
        core = failure["failureCore"]
        self.assertEqual("UNKNOWN", core["status"])
        self.assertEqual("SAFE", core["recovery"]["observationRetry"])
        self.assertEqual(
            "HOSTED_AGENT_BEGIN_ARTIFACT_DOWNLOAD_UNKNOWN",
            core["causes"][0]["code"],
        )


if __name__ == "__main__":
    unittest.main()
