import copy
import unittest

from tools import maintenance_inspect as maintenance
from tools import project_machine, project_sensors


def state():
    return {
        "schemaVersion": "ProjectState 2.1",
        "project": {"id": "mobilipresenter", "repository": "EAKerber/MobiliPresenter"},
        "git": {"controlBranch": "main", "protectedBranches": ["architecture/tpc"]},
        "published": {"url": "x", "artifactManifest": "ops/published/viewer-next-current.json"},
        "development": {"initiative": "I", "phase": "between-increments", "checkpoint": "C", "nextTransition": "open-next-slice"},
    }


def cap(policy="canonical", action="NO_EXPERIMENTAL_REVIEW", *, isolated=False):
    return {"id": "cap", "policy": policy, "supervisorParticipation": "isolated" if isolated else "active", "reviewAction": action, "nextGates": ["g1"] if action == "TEST_NEXT_GATES" else [], "backlogCount": 1 if action == "TEST_NEXT_GATES" else 0, "roundsWithoutActiveGates": 0, "maxRoundsWithoutActiveGates": 3, "deferReason": None, "reviewPlanHash": "a" * 64}


def work(work_id, status="READY", *, worker="developer-ui", target=None, blockers=None, depends=None, branch=None, pr=None):
    return {"id": work_id, "workerId": worker, "status": status, "branch": branch, "prNumber": pr, "dependsOn": list(depends or []), "completed": [], "remaining": [] if status == "DONE" else ["step"], "nextAction": None if status == "DONE" else f"run {work_id}", "lastKnownGood": {"sha": None, "checkpoint": None}, "blockers": list(blockers or (["external"] if status == "WAITING" else [])), "handoffToWorkerId": target if status == "HANDOFF" else None, "sourceSchemaVersion": "ContinuationState 0.2", "stateHash": (work_id[0] if work_id else "a") * 64}


def sensors(work_items=None, prs=None, capabilities=None):
    verification = {"status": "PASS", "ok": True, "complete": True, "checks": [], "remote": None}
    return {
        "projectState": project_sensors.sensor("PASS", data={"verification": verification, "checks": []}, authority={"kind": "repository", "path": "ops/state/project.json"}),
        "publication": project_sensors.sensor("PASS", data={"checks": []}, authority={"kind": "repository", "path": "ops/published/current.json"}),
        "git": project_sensors.sensor("PASS", data={"observed": {"worktree": True, "branch": "work/operations/test", "head": "1" * 40, "dirty": False}, "checks": []}, authority={"kind": "worktree"}),
        "repository": project_sensors.sensor("PASS", data={"checks": []}, authority={"kind": "repository", "name": "EAKerber/MobiliPresenter"}),
        "control": project_sensors.sensor("PASS", data={"branch": "main", "sha": "2" * 40, "mode": "remote"}, authority={"kind": "git-ref", "branch": "main"}),
        "capabilities": project_sensors.sensor("PASS", data={"items": capabilities if capabilities is not None else [cap()]}, authority={"kind": "repository", "path": "ops/capabilities"}),
        "pullRequests": project_sensors.sensor("PASS", data={"available": True, "items": prs or []}, authority={"kind": "github", "resource": "pull-requests"}),
        "coordination": project_sensors.sensor("PASS", data={"available": True, "authorityBranch": "coordination/leases", "authorityHead": "3" * 40, "intents": [], "leases": []}, authority={"kind": "git-authority", "branch": "coordination/leases"}),
        "continuations": project_sensors.sensor("PASS", data={"available": True, "authorityBranch": "coordination/continuations", "authorityHead": "4" * 40, "items": work_items or []}, authority={"kind": "git-authority", "branch": "coordination/continuations"}),
    }


def machine(work_items=None, prs=None, capabilities=None, *, scope="live"):
    return project_machine.build_inspection(state(), sensors(work_items, prs, capabilities), scope=scope)


class MaintenanceInspectTests(unittest.TestCase):
    def test_only_project_machine_is_supported_input(self):
        self.assertFalse(hasattr(maintenance, "build_inspection"))
        value = maintenance.from_project_inspection(machine())
        self.assertEqual(value["schemaVersion"], "MaintenanceInspection 0.5")
        self.assertEqual(set(value), {"schemaVersion", "repository", "projectMachineInspectionHash", "findings", "recommendation", "readOnly", "inspectionHash"})
        self.assertTrue(maintenance.validate_derivation(value, machine())["ok"])

    def test_no_work_continues_project_transition(self):
        value = maintenance.from_project_inspection(machine())
        self.assertEqual(value["recommendation"]["action"], "CONTINUE")
        self.assertEqual(value["recommendation"]["reasonCode"], "NEXT_TRANSITION_AVAILABLE")
        self.assertIsNone(value["recommendation"]["workId"])

    def test_handoff_precedes_runnable_work_and_carries_target_decision(self):
        value = maintenance.from_project_inspection(machine([work("a", "HANDOFF", target="developer-engine"), work("b")]))
        rec = value["recommendation"]
        self.assertEqual(rec["action"], "HANDOFF")
        self.assertEqual(rec["workId"], "a")
        self.assertEqual(rec["targetWorkerId"], "developer-engine")

    def test_runnable_work_carries_worker_target(self):
        value = maintenance.from_project_inspection(machine([work("a", worker="developer-engine")]))
        rec = value["recommendation"]
        self.assertEqual(rec["action"], "CONTINUE")
        self.assertEqual(rec["workId"], "a")
        self.assertEqual(rec["targetWorkerId"], "developer-engine")

    def test_pending_ci_does_not_pause_independent_runnable_work(self):
        items = [work("a", branch="work/ui/a", pr=7), work("b", worker="developer-engine")]
        prs = [{"number": 7, "headRef": "work/ui/a", "baseRef": "main", "ci": "pending", "ciObserved": True}]
        rec = maintenance.from_project_inspection(machine(items, prs))["recommendation"]
        self.assertEqual(rec["action"], "CONTINUE")
        self.assertEqual(rec["workId"], "b")

    def test_single_work_ci_states_are_policy_not_sensor_trust(self):
        item = work("a", branch="work/ui/a", pr=7)
        base = {"number": 7, "headRef": "work/ui/a", "baseRef": "main", "ciObserved": True}
        pending = maintenance.from_project_inspection(machine([item], [{**base, "ci": "pending"}]))
        self.assertEqual(pending["recommendation"]["action"], "PAUSE")
        self.assertEqual(pending["recommendation"]["reasonCode"], "WORK_PR_CI_PENDING")
        failed = maintenance.from_project_inspection(machine([item], [{**base, "ci": "failed"}]))
        self.assertEqual(failed["recommendation"]["action"], "RECONCILE")
        unknown = maintenance.from_project_inspection(machine([item], [{**base, "ci": "unknown", "ciObserved": False}]))
        self.assertEqual(unknown["recommendation"]["action"], "NEEDS_HUMAN")
        self.assertEqual(unknown["recommendation"]["reasonCode"], "WORK_PR_CI_UNKNOWN")

    def test_work_pr_identity_failure_comes_from_project_machine_coherence(self):
        m = machine([work("a", branch="work/ui/a", pr=7)], [])
        self.assertEqual(m["coherence"]["status"], "FAIL")
        value = maintenance.from_project_inspection(m)
        self.assertEqual(value["recommendation"]["action"], "RECONCILE")
        self.assertEqual(value["recommendation"]["reasonCode"], "WORK_PR_NOT_OPEN")

    def test_waiting_and_dependency_blocked_work_pause_only_without_independent_progress(self):
        waiting = maintenance.from_project_inspection(machine([work("a", "WAITING")]))
        self.assertEqual(waiting["recommendation"]["action"], "PAUSE")
        dep = maintenance.from_project_inspection(machine([work("a", depends=["dep"]), work("dep", "WAITING")]))
        self.assertEqual(dep["recommendation"]["action"], "PAUSE")
        independent = maintenance.from_project_inspection(machine([work("a", "WAITING"), work("b")]))
        self.assertEqual(independent["recommendation"]["action"], "CONTINUE")
        self.assertEqual(independent["recommendation"]["workId"], "b")

    def test_active_experimental_capability_can_supply_progress(self):
        experimental = cap("experimental", "TEST_NEXT_GATES")
        value = maintenance.from_project_inspection(machine([work("a", "WAITING")], capabilities=[experimental]))
        self.assertEqual(value["recommendation"]["action"], "CONTINUE")
        self.assertEqual(value["recommendation"]["focus"], "cap")

    def test_isolated_experimental_capability_is_not_actionable(self):
        experimental = cap("experimental", "TEST_NEXT_GATES", isolated=True)
        value = maintenance.from_project_inspection(machine(capabilities=[experimental]))
        self.assertEqual(value["recommendation"]["reasonCode"], "NEXT_TRANSITION_AVAILABLE")

    def test_partial_scope_does_not_turn_unobserved_work_into_empty_work(self):
        s = sensors()
        s["continuations"] = project_sensors.observe_continuations_local()
        m = project_machine.build_inspection(state(), s, scope="base")
        value = maintenance.from_project_inspection(m)
        self.assertEqual(value["recommendation"]["action"], "PAUSE")
        self.assertEqual(value["recommendation"]["reasonCode"], "NOT_OBSERVED_IN_LOCAL_SCOPE")

    def test_hash_and_derivation_reject_tampering(self):
        m = machine([work("a")])
        value = maintenance.from_project_inspection(m)
        tampered = copy.deepcopy(value)
        tampered["recommendation"]["focus"] = "tampered"
        with self.assertRaisesRegex(RuntimeError, "MAINTENANCE_HASH_MISMATCH"):
            maintenance.validate_inspection(tampered)
        rehashed = copy.deepcopy(value)
        rehashed["recommendation"]["detail"] = "drift"
        body = {k: v for k, v in rehashed.items() if k != "inspectionHash"}
        rehashed["inspectionHash"] = maintenance.stable_hash(body)
        with self.assertRaisesRegex(RuntimeError, "MAINTENANCE_DERIVATION_MISMATCH"):
            maintenance.validate_derivation(rehashed, m)


if __name__ == "__main__":
    unittest.main()
