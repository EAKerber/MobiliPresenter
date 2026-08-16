import unittest

from tools import maintenance_inspect, project_machine, project_sensors


def state(active=None, pr=None):
    return {
        "schemaVersion": "ProjectState 2.0",
        "project": {"id": "mobilipresenter", "repository": "EAKerber/MobiliPresenter"},
        "git": {"activeDevelopmentBranch": active, "controlBranch": "main", "protectedBranches": ["architecture/tpc"]},
        "published": {"url": "x", "artifactManifest": "ops/published/viewer-next-current.json"},
        "development": {"initiative": "I", "phase": "between-increments", "checkpoint": "C", "nextTransition": "next", "prNumber": pr, "blockers": []},
    }


def work_item(work_id="probe-one", status="DONE"):
    return {
        "id": work_id,
        "workerId": "developer-ui",
        "status": status,
        "branch": "ops/old" if status == "DONE" else None,
        "prNumber": 7 if status == "DONE" else None,
        "dependsOn": [],
        "completed": ["probe"] if status == "DONE" else [],
        "remaining": [] if status == "DONE" else ["probe"],
        "nextAction": None if status == "DONE" else "probe",
        "lastKnownGood": {"sha": None, "checkpoint": None},
        "blockers": [],
        "handoffToWorkerId": None,
        "sourceSchemaVersion": "ContinuationState 0.1",
        "stateHash": "a" * 64,
    }


def base_sensors():
    verification = {"status": "PASS", "ok": True, "complete": True, "checks": [], "remote": None}
    capability = {"id": "coordination-leases", "policy": "canonical", "supervisorParticipation": "active", "reviewAction": "NO_EXPERIMENTAL_REVIEW", "nextGates": [], "backlogCount": 0, "roundsWithoutActiveGates": 0, "maxRoundsWithoutActiveGates": 3, "deferReason": None, "reviewPlanHash": "a" * 64}
    return {
        "projectState": project_sensors.sensor("PASS", data={"verification": verification, "checks": []}, authority={"kind": "repository", "path": "ops/state/project.json"}),
        "publication": project_sensors.sensor("PASS", data={"checks": []}, authority={"kind": "repository", "path": "ops/published/current.json"}),
        "git": project_sensors.sensor("PASS", data={"observed": {"worktree": True, "branch": "work/operations/project-state-v2-prep", "head": "1" * 40, "dirty": False}, "checks": []}, authority={"kind": "worktree"}),
        "repository": project_sensors.sensor("PASS", data={"checks": []}, authority={"kind": "repository", "name": "EAKerber/MobiliPresenter"}),
        "control": project_sensors.sensor("PASS", data={"branch": "main", "sha": "2" * 40, "mode": "remote"}, authority={"kind": "git-ref", "branch": "main"}),
        "capabilities": project_sensors.sensor("PASS", data={"items": [capability]}, authority={"kind": "repository", "path": "ops/capabilities"}),
        "pullRequests": project_sensors.sensor("PASS", data={"available": True, "items": []}, authority={"kind": "github", "resource": "pull-requests"}),
        "coordination": project_sensors.sensor("PASS", data={"available": True, "authorityBranch": "coordination/leases", "authorityHead": "3" * 40, "intents": [], "leases": []}, authority={"kind": "git-authority", "branch": "coordination/leases"}),
        "continuations": project_sensors.sensor("PASS", data={"available": True, "authorityBranch": "coordination/continuations", "authorityHead": "4" * 40, "items": []}, authority={"kind": "git-authority", "branch": "coordination/continuations"}),
    }


class ProjectMachineTests(unittest.TestCase):
    def test_complete_live_inspection_has_pass_trust_coherence_and_graph(self):
        value = project_machine.build_inspection(state(), base_sensors(), scope="live")
        self.assertEqual(value["schemaVersion"], "ProjectMachineInspection 0.4")
        self.assertEqual(value["project"]["protectedBranches"], ["architecture/tpc"])
        self.assertNotIn("preserveBranches", value["project"])
        self.assertEqual(value["workGraph"]["schemaVersion"], "WorkGraph 0.1")
        self.assertEqual(value["workGraph"]["nodes"], [])
        self.assertEqual(value["trust"]["status"], "PASS")
        self.assertEqual(value["coherence"]["status"], "PASS")
        self.assertTrue(project_machine.validate_inspection(value)["ok"])

    def test_base_scope_is_explicit_and_valid(self):
        value = project_machine.build_inspection(state(), base_sensors(), scope="base")
        self.assertEqual(value["scope"], "base")
        self.assertTrue(project_machine.validate_inspection(value)["ok"])

    def test_unknown_sensor_is_not_green(self):
        sensors = base_sensors(); sensors["coordination"] = project_sensors.sensor("UNKNOWN", code="COORDINATION_AUTHORITY_UNAVAILABLE", data={"available": False, "intents": [], "leases": []}, authority={"kind": "git-authority", "branch": "coordination/leases"})
        value = project_machine.build_inspection(state(), sensors, scope="live")
        self.assertEqual(value["trust"]["status"], "UNKNOWN")
        self.assertFalse(value["trust"]["complete"])

    def test_known_authority_contradiction_separates_trust_and_coherence(self):
        sensors = base_sensors(); sensors["pullRequests"]["data"]["items"] = [{"number": 7, "headRef": "wrong", "baseRef": "main", "ci": "green", "ciObserved": True}]
        value = project_machine.build_inspection(state("work/operations/work", 7), sensors, scope="live")
        self.assertEqual(value["trust"]["status"], "PASS")
        self.assertEqual(value["coherence"]["status"], "FAIL")

    def test_unknown_live_continuation_fails_closed_in_maintenance(self):
        sensors = base_sensors(); sensors["continuations"] = project_sensors.sensor("UNKNOWN", code="CONTINUATION_AUTHORITY_UNAVAILABLE", data={"available": False, "items": []}, authority={"kind": "git-authority", "branch": "coordination/continuations"})
        machine = project_machine.build_inspection(state(), sensors, scope="live"); maintenance = maintenance_inspect.from_project_inspection(machine)
        self.assertEqual(maintenance["recommendation"]["action"], "NEEDS_HUMAN")
        self.assertEqual(maintenance["recommendation"]["reasonCode"], "CONTINUATION_AUTHORITY_UNAVAILABLE")

    def test_failed_sensor_reconciles_with_sensor_reason(self):
        sensors = base_sensors(); sensors["publication"] = project_sensors.sensor("FAIL", code="PUBLISHED_ARTIFACT_MISMATCH", data={}, authority={"kind": "repository", "path": "ops/published/current.json"})
        machine = project_machine.build_inspection(state(), sensors, scope="live"); maintenance = maintenance_inspect.from_project_inspection(machine)
        self.assertEqual(maintenance["recommendation"]["action"], "RECONCILE")
        self.assertEqual(maintenance["recommendation"]["reasonCode"], "PUBLISHED_ARTIFACT_MISMATCH")

    def test_coherence_failure_reconciles_with_factual_reason(self):
        sensors = base_sensors(); machine = project_machine.build_inspection(state("work/operations/work", 7), sensors, scope="live"); maintenance = maintenance_inspect.from_project_inspection(machine)
        self.assertEqual(machine["trust"]["status"], "PASS")
        self.assertEqual(machine["coherence"]["status"], "FAIL")
        self.assertEqual(maintenance["recommendation"]["reasonCode"], "ACTIVE_PR_NOT_OPEN")

    def test_known_pending_ci_is_policy_not_trust_failure(self):
        current = state("work/operations/work", 7); sensors = base_sensors(); sensors["pullRequests"]["data"]["items"] = [{"number": 7, "headRef": "work/operations/work", "baseRef": "main", "ci": "pending", "ciObserved": True}]
        machine = project_machine.build_inspection(current, sensors, scope="live"); maintenance = maintenance_inspect.from_project_inspection(machine)
        self.assertEqual(machine["trust"]["status"], "PASS"); self.assertEqual(machine["coherence"]["status"], "PASS"); self.assertEqual(maintenance["recommendation"]["action"], "PAUSE")

    def test_known_failed_ci_is_policy_not_trust_failure(self):
        current = state("work/operations/work", 7); sensors = base_sensors(); sensors["pullRequests"]["data"]["items"] = [{"number": 7, "headRef": "work/operations/work", "baseRef": "main", "ci": "failed", "ciObserved": True}]
        machine = project_machine.build_inspection(current, sensors, scope="live"); maintenance = maintenance_inspect.from_project_inspection(machine)
        self.assertEqual(machine["trust"]["status"], "PASS"); self.assertEqual(machine["coherence"]["status"], "PASS"); self.assertEqual(maintenance["recommendation"]["action"], "RECONCILE")

    def test_hash_is_stable_and_sensitive(self):
        first = project_machine.build_inspection(state(), base_sensors(), scope="live"); second = project_machine.build_inspection(state(), base_sensors(), scope="live"); self.assertEqual(first["inspectionHash"], second["inspectionHash"])
        changed = base_sensors(); changed["control"]["data"]["sha"] = "9" * 40; third = project_machine.build_inspection(state(), changed, scope="live"); self.assertNotEqual(first["inspectionHash"], third["inspectionHash"])

    def test_authority_projection_tampering_is_rejected_even_if_rehashed(self):
        value = project_machine.build_inspection(state(), base_sensors(), scope="live"); value["authorities"] = []; body = {k:v for k,v in value.items() if k != "inspectionHash"}; value["inspectionHash"] = project_machine.stable_hash(body)
        with self.assertRaisesRegex(RuntimeError, "PROJECT_MACHINE_AUTHORITIES_MISMATCH"): project_machine.validate_inspection(value)

    def test_work_graph_tampering_is_rejected_even_if_rehashed(self):
        value = project_machine.build_inspection(state(), base_sensors(), scope="live"); value["workGraph"]["terminal"] = ["fake"]; body = {k:v for k,v in value.items() if k != "inspectionHash"}; value["inspectionHash"] = project_machine.stable_hash(body)
        with self.assertRaisesRegex(RuntimeError, "PROJECT_MACHINE_WORK_GRAPH_MISMATCH"): project_machine.validate_inspection(value)

    def test_coherence_tampering_is_rejected_even_if_rehashed(self):
        value = project_machine.build_inspection(state(), base_sensors(), scope="live"); value["coherence"]["status"] = "FAIL"; body = {k:v for k,v in value.items() if k != "inspectionHash"}; value["inspectionHash"] = project_machine.stable_hash(body)
        with self.assertRaisesRegex(RuntimeError, "PROJECT_MACHINE_COHERENCE_MISMATCH"): project_machine.validate_inspection(value)

    def test_source_head_mismatch_is_rejected_even_if_rehashed(self):
        value = project_machine.build_inspection(state(), base_sensors(), scope="live"); value["sourceHeads"]["control"]["sha"] = "9" * 40; body = {k:v for k,v in value.items() if k != "inspectionHash"}; value["inspectionHash"] = project_machine.stable_hash(body)
        with self.assertRaisesRegex(RuntimeError, "PROJECT_MACHINE_SOURCE_HEADS_MISMATCH"): project_machine.validate_inspection(value)

    def test_done_continuation_is_terminal_work_observation_not_failure(self):
        sensors = base_sensors(); sensors["continuations"]["data"]["items"] = [work_item()]
        value = project_machine.build_inspection(state(), sensors, scope="live")
        self.assertEqual(value["trust"]["status"], "PASS"); self.assertEqual(value["coherence"]["status"], "PASS"); self.assertEqual(value["workGraph"]["terminal"], ["probe-one"]); self.assertEqual(value["observations"][0]["code"], "TERMINAL_CONTINUATION_RESIDUE")

    def test_maintenance_parity_from_project_machine(self):
        sensors = base_sensors(); machine = project_machine.build_inspection(state(), sensors, scope="live"); from_machine = maintenance_inspect.from_project_inspection(machine)
        view_state = {"project":{"repository":"EAKerber/MobiliPresenter"},"git":{"activeDevelopmentBranch":None,"controlBranch":"main"},"development":{"phase":"between-increments","checkpoint":"C","nextTransition":"next","prNumber":None,"blockers":[]}}
        direct = maintenance_inspect.build_inspection(view_state, sensors["projectState"]["data"]["verification"], sensors["git"]["data"]["observed"], sensors["capabilities"]["data"]["items"], remote_requested=True, pull_requests=sensors["pullRequests"]["data"], coordination_state=sensors["coordination"]["data"], work_items=sensors["continuations"]["data"]["items"], work_graph=machine["workGraph"], machine_trust=machine["trust"], machine_coherence=machine["coherence"], machine_sensors=machine["sensors"])
        self.assertEqual(from_machine["recommendation"], direct["recommendation"]); self.assertEqual(from_machine["findings"], direct["findings"])

    def test_project_machine_has_no_apply_surface(self):
        forbidden = {"checkpoint_candidate", "prune_apply", "capability_apply", "update_ref", "atomic_write_json"}
        self.assertTrue(forbidden.isdisjoint(set(project_machine.__dict__)))


if __name__ == "__main__": unittest.main()
