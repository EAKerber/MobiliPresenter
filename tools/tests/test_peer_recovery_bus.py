import copy
import unittest
from tools import peer_recovery_bus as bus


HEADS = {"control": "1" * 40, "coordination": "2" * 40, "continuation": "3" * 40}
FAILURE = {
    "code": "RUNTIME_ARTIFACT_MATERIALIZATION",
    "surface": "SUPERVISOR-SNAPSHOT",
    "operation": "ARTIFACT-DOWNLOAD-READ",
}


def observation(worker, *, state="HEALTHY", failure=None, count=0):
    return {
        "schemaVersion": "WorkerObservation 0.1",
        "workerId": worker,
        "roleId": "manager-gitops",
        "state": state,
        "authoritySource": "git-observed",
        "authorityHeads": copy.deepcopy(HEADS),
        "failure": copy.deepcopy(failure),
        "failureSource": "runtime-observed" if failure else None,
        "consecutiveFailureCount": count,
        "lastKnownGood": None,
        "events": [],
    }


def recovery_input():
    return {
        "schemaVersion": "PeerRecoveryInput 0.1",
        "roleId": "manager-gitops",
        "observer": observation("manager-gitops-a"),
        "peer": observation("manager-gitops-b", state="DEGRADED", failure=FAILURE, count=3),
        "reproduction": {
            "schemaVersion": "PeerReproduction 0.1",
            "attempted": True,
            "actorWorkerId": "manager-gitops-a",
            "mode": "read-only",
            "surface": "SUPERVISOR-SNAPSHOT",
            "outcome": "PASS",
            "failure": None,
            "sideEffects": False,
            "remediation": {
                "code": "USE_DEDICATED_WORKFLOW_ARTIFACT_DOWNLOAD",
                "scope": "peer-runtime",
                "validated": True,
                "authorityBasis": "none",
            },
        },
        "recoveryContext": {"correlationId": "case-b", "attemptCount": 0},
    }


class PeerRecoveryBusTests(unittest.TestCase):
    def test_initial_health_event_is_deterministic(self):
        first = bus.build_health_event(observation("manager-gitops-a"))
        second = bus.build_health_event(observation("manager-gitops-a"))
        self.assertTrue(first["shouldEmit"])
        self.assertEqual(first, second)
        self.assertEqual(first["event"]["type"], "worker.health")
        self.assertFalse(first["event"].get("task_control_allowed", False))

    def test_same_transition_is_not_reemitted(self):
        first = bus.build_health_event(observation("manager-gitops-a"))
        repeated = bus.build_health_event(observation("manager-gitops-a"), first["event"])
        self.assertFalse(repeated["shouldEmit"])
        self.assertEqual(repeated["existingEventId"], first["event"]["event_id"])

    def test_repeated_failure_reporting_is_bounded(self):
        first = bus.build_health_event(observation("manager-gitops-b", state="DEGRADED", failure=FAILURE, count=1))
        second = bus.build_health_event(observation("manager-gitops-b", state="DEGRADED", failure=FAILURE, count=2), first["event"])
        third = bus.build_health_event(observation("manager-gitops-b", state="DEGRADED", failure=FAILURE, count=3), second["event"])
        fourth = bus.build_health_event(observation("manager-gitops-b", state="DEGRADED", failure=FAILURE, count=4), third["event"])
        self.assertTrue(first["shouldEmit"])
        self.assertTrue(second["shouldEmit"])
        self.assertTrue(third["shouldEmit"])
        self.assertFalse(fourth["shouldEmit"])

    def test_recovery_event_is_deterministic_and_targets_peer(self):
        first = bus.build_recovery_event(recovery_input())
        second = bus.build_recovery_event(recovery_input())
        self.assertEqual(first, second)
        self.assertTrue(first["shouldEmit"])
        event = first["event"]
        self.assertEqual(event["type"], "peer.recovery")
        self.assertEqual(event["target_worker"], "manager-gitops-b")
        self.assertEqual(event["classification"], "PEER_RUNTIME_ASYMMETRY")
        self.assertEqual(event["action"], "REQUEST_RETRY")
        self.assertEqual(event["signal"], "RECOVERY_READY")
        self.assertEqual(event["recommended_executor"], "peer")
        self.assertFalse(event["task_control_allowed"])
        self.assertFalse(event["identity_takeover_allowed"])
        self.assertFalse(event["lease_takeover_allowed"])
        self.assertFalse(event["continuation_takeover_allowed"])


if __name__ == "__main__":
    unittest.main()
