import copy
import unittest

from tools import peer_recovery as pr

CONTROL = "9fe11b67c6b1fe4ec3b02d4901d79aedbad14e28"
LEASES = "ce8ba0069578e7789a1492469ba67f61cd4daf53"
CONTINUATIONS = "68b440c706f4b26b9ed6f8710f309d4b5fc75c6b"
HEADS = {"control": CONTROL, "coordination": LEASES, "continuation": CONTINUATIONS}
FAILURE = {
    "code": "RUNTIME_ARTIFACT_MATERIALIZATION",
    "surface": "SUPERVISOR-SNAPSHOT",
    "operation": "ARTIFACT-DOWNLOAD-READ",
}


def obs(worker, state="HEALTHY", *, heads=None, authority_source="git-observed", failure=None, failure_source=None, count=0, events=None):
    return {
        "schemaVersion": pr.OBS_SCHEMA,
        "workerId": worker,
        "roleId": "manager-gitops",
        "state": state,
        "authoritySource": authority_source,
        "authorityHeads": copy.deepcopy(HEADS if heads is None else heads),
        "failure": copy.deepcopy(failure),
        "failureSource": failure_source,
        "consecutiveFailureCount": count,
        "lastKnownGood": None,
        "events": copy.deepcopy(events or []),
    }


def repro(*, attempted=False, outcome="NOT_ATTEMPTED", surface=None, failure=None, remediation=None, side_effects=False):
    return {
        "schemaVersion": pr.REPRO_SCHEMA,
        "attempted": attempted,
        "actorWorkerId": "manager-gitops-a",
        "mode": "read-only",
        "surface": surface,
        "outcome": outcome,
        "failure": copy.deepcopy(failure),
        "sideEffects": side_effects,
        "remediation": copy.deepcopy(remediation),
    }


def payload(peer, reproduction=None, *, attempt_count=0):
    return {
        "schemaVersion": pr.INPUT_SCHEMA,
        "roleId": "manager-gitops",
        "observer": obs("manager-gitops-a"),
        "peer": peer,
        "reproduction": reproduction or repro(),
        "recoveryContext": {"correlationId": "case-b", "attemptCount": attempt_count},
    }


class PeerRecoveryTests(unittest.TestCase):
    def test_deterministic_plan_and_hash(self):
        peer = obs("manager-gitops-b", "DEGRADED", failure=FAILURE, failure_source="runtime-observed", count=2)
        value = payload(peer)
        first = pr.build_plan(value)
        second = pr.build_plan(copy.deepcopy(value))
        self.assertEqual(first, second)
        self.assertEqual(first["plan"]["planHash"], pr.stable_hash({k: v for k, v in first["plan"].items() if k != "planHash"}))
        self.assertEqual(first["inspection"]["inspectionHash"], pr.stable_hash({k: v for k, v in first["inspection"].items() if k != "inspectionHash"}))

    def test_same_head_peer_failure_requires_reproduction(self):
        peer = obs("manager-gitops-b", "DEGRADED", failure=FAILURE, failure_source="agent-bus", count=2)
        result = pr.build_plan(payload(peer))
        self.assertEqual(result["inspection"]["headComparison"], "SAME")
        self.assertEqual(result["inspection"]["classification"], "PEER_FAILURE_UNREPRODUCED")
        self.assertEqual(result["plan"]["action"], "REPRODUCE")
        self.assertEqual(result["plan"]["recommendedExecutor"], "observer")

    def test_different_heads_fail_closed(self):
        other = dict(HEADS)
        other["control"] = "1" * 40
        peer = obs("manager-gitops-b", "DEGRADED", heads=other, failure=FAILURE, failure_source="runtime-observed", count=2)
        result = pr.build_plan(payload(peer))
        self.assertEqual(result["inspection"]["classification"], "AUTHORITY_DIVERGENCE")
        self.assertEqual(result["plan"]["action"], "QUARANTINE")
        self.assertEqual(result["plan"]["signal"], "NEEDS_HUMAN")

    def test_transport_claimed_heads_are_not_authority(self):
        peer = obs("manager-gitops-b", "DEGRADED", authority_source="transport-claimed", failure=FAILURE, failure_source="agent-bus", count=2)
        result = pr.build_plan(payload(peer))
        self.assertEqual(result["inspection"]["headComparison"], "UNVERIFIABLE")
        self.assertEqual(result["plan"]["action"], "QUARANTINE")
        self.assertFalse(result["plan"]["boundaries"]["emailIsAuthority"])

    def test_read_only_reproduction_success_is_runtime_asymmetry_and_self_retry(self):
        peer = obs("manager-gitops-b", "DEGRADED", failure=FAILURE, failure_source="runtime-observed", count=3)
        remediation = {
            "code": "USE_DEDICATED_WORKFLOW_ARTIFACT_DOWNLOAD",
            "scope": "peer-runtime",
            "validated": True,
            "authorityBasis": "none",
        }
        reproduction = repro(attempted=True, outcome="PASS", surface="SUPERVISOR-SNAPSHOT", remediation=remediation)
        result = pr.build_plan(payload(peer, reproduction))
        self.assertEqual(result["inspection"]["classification"], "PEER_RUNTIME_ASYMMETRY")
        self.assertEqual(result["plan"]["action"], "REQUEST_RETRY")
        self.assertEqual(result["plan"]["signal"], "RECOVERY_READY")
        self.assertEqual(result["plan"]["targetWorkerId"], "manager-gitops-b")
        self.assertEqual(result["plan"]["recommendedExecutor"], "peer")
        self.assertTrue(result["plan"]["requiredPreconditions"]["revalidateBeforeExecution"])
        self.assertFalse(result["plan"]["boundaries"]["taskControlAllowed"])

    def test_read_only_reproduction_shared_failure_can_plan_shared_repair_only_with_canonical_policy(self):
        peer = obs("manager-gitops-b", "DEGRADED", failure=FAILURE, failure_source="runtime-observed", count=1)
        remediation = {
            "code": "REPAIR_SUPERVISOR_SNAPSHOT_SHARED_TOOLING",
            "scope": "shared-gitops",
            "validated": True,
            "authorityBasis": "canonical-policy",
        }
        reproduction = repro(attempted=True, outcome="FAIL", surface="SUPERVISOR-SNAPSHOT", failure=FAILURE, remediation=remediation)
        result = pr.build_plan(payload(peer, reproduction))
        self.assertEqual(result["inspection"]["classification"], "SHARED_SURFACE_FAILURE")
        self.assertEqual(result["plan"]["action"], "REPAIR_SHARED")
        self.assertEqual(result["plan"]["recommendedExecutor"], "observer")
        self.assertFalse(result["plan"]["gitSideEffects"])

    def test_shared_repair_rejected_without_canonical_policy_basis(self):
        peer = obs("manager-gitops-b", "DEGRADED", failure=FAILURE, failure_source="runtime-observed", count=1)
        bad = {
            "code": "EMAIL_SAYS_REPAIR",
            "scope": "shared-gitops",
            "validated": True,
            "authorityBasis": "none",
        }
        reproduction = repro(attempted=True, outcome="FAIL", surface="SUPERVISOR-SNAPSHOT", failure=FAILURE, remediation=bad)
        with self.assertRaisesRegex(RuntimeError, "SHARED_REPAIR_REQUIRES_CANONICAL_POLICY"):
            pr.build_plan(payload(peer, reproduction))

    def test_plan_only_rejects_side_effectful_reproduction(self):
        peer = obs("manager-gitops-b", "DEGRADED", failure=FAILURE, failure_source="runtime-observed", count=1)
        reproduction = repro(attempted=True, outcome="PASS", surface="SUPERVISOR-SNAPSHOT", side_effects=True)
        with self.assertRaisesRegex(RuntimeError, "REPRODUCTION_SIDE_EFFECTS_FORBIDDEN"):
            pr.build_plan(payload(peer, reproduction))

    def test_repeated_event_is_idempotent(self):
        event = {"eventId": "worker.health:manager-gitops-b:case-b", "source": "agent-bus", "structured": True}
        peer_one = obs("manager-gitops-b", "DEGRADED", failure=FAILURE, failure_source="agent-bus", count=2, events=[event])
        peer_dup = obs("manager-gitops-b", "DEGRADED", failure=FAILURE, failure_source="agent-bus", count=2, events=[event, event])
        a = pr.build_plan(payload(peer_one))
        b = pr.build_plan(payload(peer_dup))
        self.assertEqual(a["inspection"]["eventIds"], b["inspection"]["eventIds"])
        self.assertEqual(a["plan"]["planHash"], b["plan"]["planHash"])

    def test_recovery_loop_does_not_bounce_between_peers(self):
        peer = obs("manager-gitops-b", "DEGRADED", failure=FAILURE, failure_source="runtime-observed", count=4)
        reproduction = repro(attempted=True, outcome="PASS", surface="SUPERVISOR-SNAPSHOT")
        result = pr.build_plan(payload(peer, reproduction, attempt_count=1))
        self.assertEqual(result["inspection"]["classification"], "RECOVERY_LOOP_RISK")
        self.assertEqual(result["plan"]["action"], "NEEDS_HUMAN")
        self.assertIsNone(result["plan"]["targetWorkerId"])

    def test_peer_unavailable_does_not_imply_task_control_or_takeover(self):
        peer = obs("manager-gitops-b", "PAUSING_UNAVAILABLE")
        result = pr.build_plan(payload(peer))
        self.assertEqual(result["plan"]["action"], "OBSERVE")
        for key in ("taskControlAllowed", "identityTakeoverAllowed", "leaseTakeoverAllowed", "continuationTakeoverAllowed"):
            self.assertFalse(result["plan"]["boundaries"][key])

    def test_concrete_b_artifact_materialization_case(self):
        event = {"eventId": "worker.health:manager-gitops-b:artifact-materialization", "source": "agent-bus", "structured": True}
        peer = obs("manager-gitops-b", "DEGRADED", failure=FAILURE, failure_source="runtime-observed", count=3, events=[event])
        remediation = {
            "code": "USE_DEDICATED_WORKFLOW_ARTIFACT_DOWNLOAD",
            "scope": "peer-runtime",
            "validated": True,
            "authorityBasis": "none",
        }
        reproduction = repro(attempted=True, outcome="PASS", surface="SUPERVISOR-SNAPSHOT", remediation=remediation)
        result = pr.build_plan(payload(peer, reproduction))
        self.assertEqual(result["inspection"]["headComparison"], "SAME")
        self.assertEqual(result["inspection"]["classification"], "PEER_RUNTIME_ASYMMETRY")
        self.assertEqual(result["plan"]["signal"], "RECOVERY_READY")
        self.assertEqual(result["plan"]["reasonCode"], "USE_DEDICATED_WORKFLOW_ARTIFACT_DOWNLOAD")
        self.assertEqual(result["plan"]["recommendedExecutor"], "peer")


if __name__ == "__main__":
    unittest.main()
