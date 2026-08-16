import unittest

from tools import maintenance_inspect, project_machine, project_sensors


def state():
    return {"project": {"repository": "EAKerber/MobiliPresenter"}, "git": {"activeDevelopmentBranch": None}, "development": {"phase": "between-increments", "checkpoint": "C", "nextTransition": "next", "prNumber": None, "blockers": []}}


def base_sensors():
    verification = {"status": "PASS", "ok": True, "complete": True, "checks": [], "remote": None}
    capability = {"id": "coordination-leases", "policy": "canonical", "supervisorParticipation": "active", "reviewAction": "NO_EXPERIMENTAL_REVIEW", "nextGates": [], "backlogCount": 0, "roundsWithoutActiveGates": 0, "maxRoundsWithoutActiveGates": 3, "deferReason": None, "reviewPlanHash": "a" * 64}
    return {
        "projectState": project_sensors.sensor("PASS", data={"verification": verification, "checks": []}),
        "publication": project_sensors.sensor("PASS", data={"checks": []}),
        "git": project_sensors.sensor("PASS", data={"observed": {"worktree": True, "branch": "ops/project-machine-m1-inspection", "head": "1" * 40, "dirty": False}, "checks": []}),
        "repository": project_sensors.sensor("PASS", data={"checks": []}),
        "control": project_sensors.sensor("PASS", data={"branch": "main", "sha": "2" * 40, "mode": "remote"}),
        "capabilities": project_sensors.sensor("PASS", data={"items": [capability]}),
        "pullRequests": project_sensors.sensor("PASS", data={"available": True, "items": []}),
        "coordination": project_sensors.sensor("PASS", data={"available": True, "authorityBranch": "coordination/leases", "authorityHead": "3" * 40, "intents": [], "leases": []}),
        "continuations": project_sensors.sensor("PASS", data={"available": True, "authorityBranch": "coordination/continuations", "authorityHead": "4" * 40, "items": []}),
        "development": project_sensors.sensor("PASS", code="NO_ACTIVE_DEVELOPMENT", data={"activeDevelopmentBranch": None, "developmentPrNumber": None, "phase": "between-increments", "checkpoint": "C", "nextTransition": "next", "blockers": []}),
    }


class ProjectMachineTests(unittest.TestCase):
    def test_pass_trust_for_complete_live_inspection(self):
        value = project_machine.build_inspection(state(), base_sensors(), scope="live")
        self.assertEqual(value["trust"]["status"], "PASS")
        self.assertTrue(value["trust"]["complete"])
        self.assertTrue(project_machine.validate_inspection(value)["ok"])

    def test_base_scope_is_explicit_and_valid(self):
        value = project_machine.build_inspection(state(), base_sensors(), scope="base")
        self.assertEqual(value["scope"], "base")
        self.assertTrue(project_machine.validate_inspection(value)["ok"])

    def test_unknown_is_not_green(self):
        sensors = base_sensors()
        sensors["coordination"] = project_sensors.sensor("UNKNOWN", code="COORDINATION_AUTHORITY_UNAVAILABLE", data={"available": False, "intents": [], "leases": []})
        value = project_machine.build_inspection(state(), sensors, scope="live")
        self.assertEqual(value["trust"]["status"], "UNKNOWN")
        self.assertTrue(value["trust"]["ok"])
        self.assertFalse(value["trust"]["complete"])
        self.assertIn("coordination", value["trust"]["unknownSensors"])

    def test_unknown_machine_trust_fails_closed_in_maintenance(self):
        sensors = base_sensors()
        sensors["continuations"] = project_sensors.sensor("UNKNOWN", code="CONTINUATION_AUTHORITY_UNAVAILABLE", data={"available": False, "items": []})
        machine = project_machine.build_inspection(state(), sensors, scope="live")
        maintenance = maintenance_inspect.from_project_inspection(machine)
        self.assertEqual(maintenance["recommendation"]["action"], "NEEDS_HUMAN")
        self.assertEqual(maintenance["recommendation"]["reasonCode"], "PROJECT_MACHINE_INCOMPLETE")

    def test_failed_machine_trust_reconciles(self):
        sensors = base_sensors()
        sensors["publication"] = project_sensors.sensor("FAIL", code="PUBLISHED_ARTIFACT_MISMATCH", data={})
        machine = project_machine.build_inspection(state(), sensors, scope="live")
        maintenance = maintenance_inspect.from_project_inspection(machine)
        self.assertEqual(maintenance["recommendation"]["action"], "RECONCILE")
        self.assertEqual(maintenance["recommendation"]["reasonCode"], "PROJECT_MACHINE_FAILED")

    def test_failure_dominates_unknown(self):
        sensors = base_sensors()
        sensors["coordination"] = project_sensors.sensor("UNKNOWN", code="X", data={"available": False})
        sensors["publication"] = project_sensors.sensor("FAIL", code="Y", data={})
        value = project_machine.build_inspection(state(), sensors, scope="live")
        self.assertEqual(value["trust"]["status"], "FAIL")
        self.assertFalse(value["trust"]["ok"])
        self.assertIn("publication", value["trust"]["failedSensors"])

    def test_hash_is_stable_and_sensitive(self):
        first = project_machine.build_inspection(state(), base_sensors(), scope="live")
        second = project_machine.build_inspection(state(), base_sensors(), scope="live")
        self.assertEqual(first["inspectionHash"], second["inspectionHash"])
        changed = base_sensors()
        changed["control"]["data"]["sha"] = "9" * 40
        third = project_machine.build_inspection(state(), changed, scope="live")
        self.assertNotEqual(first["inspectionHash"], third["inspectionHash"])

    def test_tampering_is_rejected(self):
        value = project_machine.build_inspection(state(), base_sensors(), scope="live")
        value["project"]["checkpoint"] = "tampered"
        with self.assertRaisesRegex(RuntimeError, "PROJECT_MACHINE_HASH_MISMATCH"):
            project_machine.validate_inspection(value)

    def test_invalid_sensor_status_is_rejected_even_if_rehashed(self):
        value = project_machine.build_inspection(state(), base_sensors(), scope="live")
        value["sensors"]["coordination"]["status"] = "MAYBE"
        body = {key: item for key, item in value.items() if key != "inspectionHash"}
        value["inspectionHash"] = project_machine.stable_hash(body)
        with self.assertRaisesRegex(RuntimeError, "PROJECT_MACHINE_SENSOR_STATUS_INVALID"):
            project_machine.validate_inspection(value)

    def test_source_head_mismatch_is_rejected_even_if_rehashed(self):
        value = project_machine.build_inspection(state(), base_sensors(), scope="live")
        value["sourceHeads"]["control"]["sha"] = "9" * 40
        body = {key: item for key, item in value.items() if key != "inspectionHash"}
        value["inspectionHash"] = project_machine.stable_hash(body)
        with self.assertRaisesRegex(RuntimeError, "PROJECT_MACHINE_SOURCE_HEADS_MISMATCH"):
            project_machine.validate_inspection(value)

    def test_derived_observation_mismatch_is_rejected_even_if_rehashed(self):
        value = project_machine.build_inspection(state(), base_sensors(), scope="live")
        value["observations"] = [{"severity": "INFO", "code": "INVENTED"}]
        body = {key: item for key, item in value.items() if key != "inspectionHash"}
        value["inspectionHash"] = project_machine.stable_hash(body)
        with self.assertRaisesRegex(RuntimeError, "PROJECT_MACHINE_OBSERVATIONS_MISMATCH"):
            project_machine.validate_inspection(value)

    def test_done_continuation_is_observation_not_failure(self):
        sensors = base_sensors()
        sensors["continuations"]["data"]["items"] = [{"id": "probe-one", "status": "DONE"}]
        value = project_machine.build_inspection(state(), sensors, scope="live")
        self.assertEqual(value["trust"]["status"], "PASS")
        self.assertEqual(value["observations"][0]["code"], "TERMINAL_CONTINUATION_RESIDUE")

    def test_maintenance_parity_from_project_machine(self):
        sensors = base_sensors()
        machine = project_machine.build_inspection(state(), sensors, scope="live")
        from_machine = maintenance_inspect.from_project_inspection(machine)
        direct = maintenance_inspect.build_inspection(state(), sensors["projectState"]["data"]["verification"], sensors["git"]["data"]["observed"], sensors["capabilities"]["data"]["items"], remote_requested=True, pull_requests=sensors["pullRequests"]["data"], coordination_state=sensors["coordination"]["data"], continuations=sensors["continuations"]["data"]["items"], machine_trust=machine["trust"])
        self.assertEqual(from_machine["recommendation"], direct["recommendation"])
        self.assertEqual(from_machine["findings"], direct["findings"])

    def test_project_machine_has_no_apply_surface(self):
        forbidden = {"checkpoint_candidate", "prune_apply", "capability_apply", "update_ref", "atomic_write_json"}
        self.assertTrue(forbidden.isdisjoint(set(project_machine.__dict__)))


if __name__ == "__main__":
    unittest.main()
