import copy
import unittest

from tools import maintenance_inspect as maintenance


def state():
    return {
        "project": {"repository": "EAKerber/MobiliPresenter"},
        "git": {"activeDevelopmentBranch": None, "controlBranch": "main"},
        "development": {
            "phase": "between-increments",
            "checkpoint": "CHECKPOINT",
            "nextTransition": "open-next-slice",
            "prNumber": None,
            "blockers": [],
        },
    }


def verification(ok=True):
    return {"ok": ok, "checks": [] if ok else [{"name": "project-state", "status": "FAIL"}], "remote": None}


def cap():
    return {
        "id": "coordination-leases",
        "policy": "canonical",
        "supervisorParticipation": "active",
        "reviewAction": "NO_EXPERIMENTAL_REVIEW",
        "nextGates": [],
        "backlogCount": 0,
        "roundsWithoutActiveGates": 0,
        "maxRoundsWithoutActiveGates": 3,
        "deferReason": None,
        "reviewPlanHash": "a" * 64,
    }


def coherence(status="PASS", code=None):
    checks = []
    if status in {"FAIL", "UNKNOWN"}:
        checks = [
            {
                "id": "test.coherence",
                "status": status,
                "required": True,
                "code": code or "TEST_COHERENCE",
                "subjects": ["project-state", "github-pull-requests"],
                "detail": {"test": True},
            }
        ]
    return {
        "status": status,
        "ok": status != "FAIL",
        "complete": status == "PASS",
        "failedChecks": ["test.coherence"] if status == "FAIL" else [],
        "unknownChecks": ["test.coherence"] if status == "UNKNOWN" else [],
        "checks": checks,
    }


class MaintenanceInspectTests(unittest.TestCase):
    def build(
        self,
        s=None,
        v=None,
        caps=None,
        remote=False,
        prs=None,
        coord=None,
        machine_trust=None,
        machine_coherence=None,
        machine_sensors=None,
    ):
        return maintenance.build_inspection(
            s or state(),
            v or verification(),
            {"worktree": True, "branch": "main", "head": "1" * 40, "dirty": False},
            caps if caps is not None else [cap()],
            remote_requested=remote,
            pull_requests=prs or {"available": False, "reason": "NOT_REQUESTED", "items": []},
            coordination_state=coord or {"available": False, "reason": "NOT_REQUESTED", "intents": [], "leases": []},
            machine_trust=machine_trust,
            machine_coherence=machine_coherence,
            machine_sensors=machine_sensors,
        )

    def test_coherent_state_continues(self):
        result = self.build()
        self.assertEqual(result["recommendation"]["action"], "CONTINUE")
        self.assertEqual(result["recommendation"]["reasonCode"], "NEXT_TRANSITION_AVAILABLE")
        self.assertTrue(result["readOnly"])

    def test_verification_failure_reconciles(self):
        self.assertEqual(self.build(v=verification(False))["recommendation"]["action"], "RECONCILE")

    def test_blocker_pauses(self):
        current = state()
        current["development"]["blockers"] = ["waiting-on-input"]
        self.assertEqual(self.build(s=current)["recommendation"]["action"], "PAUSE")

    def test_gate_limit_requires_human(self):
        current = cap()
        current.update({"id": "experiment", "policy": "experimental", "reviewAction": "REVIEW_EMPTY_LIMIT", "roundsWithoutActiveGates": 3})
        result = self.build(caps=[current])
        self.assertEqual(result["recommendation"]["action"], "NEEDS_HUMAN")
        self.assertEqual(result["recommendation"]["focus"], "experiment")

    def test_isolated_experimental_capability_does_not_change_recommendation(self):
        current = cap()
        current.update({"id": "peer-recovery", "policy": "experimental", "supervisorParticipation": "isolated", "reviewAction": "TEST_NEXT_GATES", "nextGates": ["runtime-shadow"], "backlogCount": 1})
        result = self.build(caps=[current])
        self.assertEqual(result["recommendation"]["reasonCode"], "NEXT_TRANSITION_AVAILABLE")

    def test_unknown_machine_sensor_requires_human_with_original_code(self):
        trust = {"status": "UNKNOWN", "ok": True, "complete": False, "failedSensors": [], "unknownSensors": ["coordination"]}
        sensors = {"coordination": {"code": "COORDINATION_AUTHORITY_UNAVAILABLE"}}
        result = self.build(machine_trust=trust, machine_sensors=sensors)
        self.assertEqual(result["recommendation"]["action"], "NEEDS_HUMAN")
        self.assertEqual(result["recommendation"]["reasonCode"], "COORDINATION_AUTHORITY_UNAVAILABLE")

    def test_coherence_failure_reconciles_without_reimplementing_fact(self):
        result = self.build(machine_coherence=coherence("FAIL", "UNCLASSIFIED_OPEN_PR"))
        self.assertEqual(result["recommendation"]["action"], "RECONCILE")
        self.assertEqual(result["recommendation"]["reasonCode"], "UNCLASSIFIED_OPEN_PR")

    def test_coherence_unknown_requires_human(self):
        result = self.build(machine_coherence=coherence("UNKNOWN", "REMOTE_PR_INVENTORY_UNAVAILABLE"))
        self.assertEqual(result["recommendation"]["action"], "NEEDS_HUMAN")
        self.assertEqual(result["recommendation"]["reasonCode"], "REMOTE_PR_INVENTORY_UNAVAILABLE")

    def test_active_pr_pending_and_failed_are_policy(self):
        current = state()
        current["git"]["activeDevelopmentBranch"] = "ops/work"
        current["development"]["prNumber"] = 7
        coord = {"available": True, "authorityHead": "2" * 40, "intents": [], "leases": []}
        prs = {"available": True, "items": [{"number": 7, "headRef": "ops/work", "ci": "pending", "ciObserved": True}]}
        self.assertEqual(self.build(s=current, remote=True, prs=prs, coord=coord)["recommendation"]["action"], "PAUSE")
        failed = copy.deepcopy(prs)
        failed["items"][0]["ci"] = "failed"
        self.assertEqual(self.build(s=current, remote=True, prs=failed, coord=coord)["recommendation"]["action"], "RECONCILE")

    def test_active_pr_unknown_ci_requires_human(self):
        current = state()
        current["git"]["activeDevelopmentBranch"] = "ops/work"
        current["development"]["prNumber"] = 7
        prs = {"available": True, "items": [{"number": 7, "headRef": "ops/work", "ci": "unknown", "ciObserved": True}]}
        result = self.build(s=current, remote=True, prs=prs)
        self.assertEqual(result["recommendation"]["action"], "NEEDS_HUMAN")
        self.assertEqual(result["recommendation"]["reasonCode"], "ACTIVE_PR_CI_UNKNOWN")

    def test_maintenance_no_longer_detects_unclassified_pr_or_stale_lease_itself(self):
        prs = {"available": True, "items": [{"number": 55, "headRef": "feature/mystery", "ci": "green", "ciObserved": True}]}
        coord = {"available": True, "intents": [], "leases": [{"leaseId": "L1", "owner": {"pr": 99}}]}
        result = self.build(remote=True, prs=prs, coord=coord)
        self.assertEqual(result["recommendation"]["reasonCode"], "NEXT_TRANSITION_AVAILABLE")

    def test_hash_stable_sensitive_and_handoff_reserved(self):
        first = self.build()
        second = self.build()
        self.assertEqual(first["inspectionHash"], second["inspectionHash"])
        self.assertIn("HANDOFF", first["recommendation"]["allowedActions"])
        current = state()
        current["development"]["nextTransition"] = "different"
        self.assertNotEqual(first["inspectionHash"], self.build(s=current)["inspectionHash"])


if __name__ == "__main__":
    unittest.main()
