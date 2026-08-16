import copy
import unittest

from tools import maintenance_inspect, project_machine, project_sensors


def state(active=None, pr=None):
    return {
        "project": {"repository": "EAKerber/MobiliPresenter"},
        "git": {
            "activeDevelopmentBranch": active,
            "controlBranch": "main",
            "preserveBranches": ["architecture/tpc"],
        },
        "development": {
            "phase": "between-increments",
            "checkpoint": "C",
            "nextTransition": "next",
            "prNumber": pr,
            "blockers": [],
        },
    }


def base_sensors():
    verification = {"status": "PASS", "ok": True, "complete": True, "checks": [], "remote": None}
    capability = {
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
    return {
        "projectState": project_sensors.sensor(
            "PASS", data={"verification": verification, "checks": []}, authority={"kind": "repository", "path": "ops/state/project.json"}
        ),
        "publication": project_sensors.sensor(
            "PASS", data={"checks": []}, authority={"kind": "repository", "path": "ops/published/current.json"}
        ),
        "git": project_sensors.sensor(
            "PASS",
            data={"observed": {"worktree": True, "branch": "ops/project-machine-m2-authority-coherence", "head": "1" * 40, "dirty": False}, "checks": []},
            authority={"kind": "worktree"},
        ),
        "repository": project_sensors.sensor(
            "PASS", data={"checks": []}, authority={"kind": "repository", "name": "EAKerber/MobiliPresenter"}
        ),
        "control": project_sensors.sensor(
            "PASS", data={"branch": "main", "sha": "2" * 40, "mode": "remote"}, authority={"kind": "git-ref", "branch": "main"}
        ),
        "capabilities": project_sensors.sensor(
            "PASS", data={"items": [capability]}, authority={"kind": "repository", "path": "ops/capabilities"}
        ),
        "pullRequests": project_sensors.sensor(
            "PASS", data={"available": True, "items": []}, authority={"kind": "github", "resource": "pull-requests"}
        ),
        "coordination": project_sensors.sensor(
            "PASS",
            data={"available": True, "authorityBranch": "coordination/leases", "authorityHead": "3" * 40, "intents": [], "leases": []},
            authority={"kind": "git-authority", "branch": "coordination/leases"},
        ),
        "continuations": project_sensors.sensor(
            "PASS",
            data={"available": True, "authorityBranch": "coordination/continuations", "authorityHead": "4" * 40, "items": []},
            authority={"kind": "git-authority", "branch": "coordination/continuations"},
        ),
    }


class ProjectMachineTests(unittest.TestCase):
    def test_complete_live_inspection_has_pass_trust_and_coherence(self):
        value = project_machine.build_inspection(state(), base_sensors(), scope="live")
        self.assertEqual(value["schemaVersion"], "ProjectMachineInspection 0.2")
        self.assertEqual(value["trust"]["status"], "PASS")
        self.assertEqual(value["coherence"]["status"], "PASS")
        self.assertTrue(project_machine.validate_inspection(value)["ok"])

    def test_base_scope_is_explicit_and_valid(self):
        value = project_machine.build_inspection(state(), base_sensors(), scope="base")
        self.assertEqual(value["scope"], "base")
        self.assertTrue(project_machine.validate_inspection(value)["ok"])

    def test_unknown_sensor_is_not_green(self):
        sensors = base_sensors()
        sensors["coordination"] = project_sensors.sensor(
            "UNKNOWN",
            code="COORDINATION_AUTHORITY_UNAVAILABLE",
            data={"available": False, "intents": [], "leases": []},
            authority={"kind": "git-authority", "branch": "coordination/leases"},
        )
        value = project_machine.build_inspection(state(), sensors, scope="live")
        self.assertEqual(value["trust"]["status"], "UNKNOWN")
        self.assertFalse(value["trust"]["complete"])

    def test_known_authority_contradiction_separates_trust_and_coherence(self):
        sensors = base_sensors()
        sensors["pullRequests"]["data"]["items"] = [
            {"number": 7, "headRef": "wrong", "baseRef": "main", "ci": "green", "ciObserved": True}
        ]
        value = project_machine.build_inspection(state("ops/work", 7), sensors, scope="live")
        self.assertEqual(value["trust"]["status"], "PASS")
        self.assertEqual(value["coherence"]["status"], "FAIL")

    def test_unknown_live_continuation_fails_closed_in_maintenance(self):
        sensors = base_sensors()
        sensors["continuations"] = project_sensors.sensor(
            "UNKNOWN",
            code="CONTINUATION_AUTHORITY_UNAVAILABLE",
            data={"available": False, "items": []},
            authority={"kind": "git-authority", "branch": "coordination/continuations"},
        )
        machine = project_machine.build_inspection(state(), sensors, scope="live")
        maintenance = maintenance_inspect.from_project_inspection(machine)
        self.assertEqual(maintenance["recommendation"]["action"], "NEEDS_HUMAN")
        self.assertEqual(maintenance["recommendation"]["reasonCode"], "CONTINUATION_AUTHORITY_UNAVAILABLE")

    def test_failed_sensor_reconciles_with_sensor_reason(self):
        sensors = base_sensors()
        sensors["publication"] = project_sensors.sensor(
            "FAIL", code="PUBLISHED_ARTIFACT_MISMATCH", data={}, authority={"kind": "repository", "path": "ops/published/current.json"}
        )
        machine = project_machine.build_inspection(state(), sensors, scope="live")
        maintenance = maintenance_inspect.from_project_inspection(machine)
        self.assertEqual(maintenance["recommendation"]["action"], "RECONCILE")
        self.assertEqual(maintenance["recommendation"]["reasonCode"], "PUBLISHED_ARTIFACT_MISMATCH")

    def test_coherence_failure_reconciles_with_factual_reason(self):
        sensors = base_sensors()
        machine = project_machine.build_inspection(state("ops/work", 7), sensors, scope="live")
        maintenance = maintenance_inspect.from_project_inspection(machine)
        self.assertEqual(machine["trust"]["status"], "PASS")
        self.assertEqual(machine["coherence"]["status"], "FAIL")
        self.assertEqual(maintenance["recommendation"]["action"], "RECONCILE")
        self.assertEqual(maintenance["recommendation"]["reasonCode"], "ACTIVE_PR_NOT_OPEN")

    def test_known_pending_ci_is_policy_not_trust_failure(self):
        current = state("ops/work", 7)
        sensors = base_sensors()
        sensors["pullRequests"]["data"]["items"] = [
            {"number": 7, "headRef": "ops/work", "baseRef": "main", "ci": "pending", "ciObserved": True}
        ]
        machine = project_machine.build_inspection(current, sensors, scope="live")
        maintenance = maintenance_inspect.from_project_inspection(machine)
        self.assertEqual(machine["trust"]["status"], "PASS")
        self.assertEqual(machine["coherence"]["status"], "PASS")
        self.assertEqual(maintenance["recommendation"]["action"], "PAUSE")
        self.assertEqual(maintenance["recommendation"]["reasonCode"], "ACTIVE_PR_CI_PENDING")

    def test_known_failed_ci_is_policy_not_trust_failure(self):
        current = state("ops/work", 7)
        sensors = base_sensors()
        sensors["pullRequests"]["data"]["items"] = [
            {"number": 7, "headRef": "ops/work", "baseRef": "main", "ci": "failed", "ciObserved": True}
        ]
        machine = project_machine.build_inspection(current, sensors, scope="live")
        maintenance = maintenance_inspect.from_project_inspection(machine)
        self.assertEqual(machine["trust"]["status"], "PASS")
        self.assertEqual(machine["coherence"]["status"], "PASS")
        self.assertEqual(maintenance["recommendation"]["action"], "RECONCILE")
        self.assertEqual(maintenance["recommendation"]["reasonCode"], "ACTIVE_PR_CI_FAILED")

    def test_hash_is_stable_and_sensitive(self):
        first = project_machine.build_inspection(state(), base_sensors(), scope="live")
        second = project_machine.build_inspection(state(), base_sensors(), scope="live")
        self.assertEqual(first["inspectionHash"], second["inspectionHash"])
        changed = base_sensors()
        changed["control"]["data"]["sha"] = "9" * 40
        third = project_machine.build_inspection(state(), changed, scope="live")
        self.assertNotEqual(first["inspectionHash"], third["inspectionHash"])

    def test_authority_projection_tampering_is_rejected_even_if_rehashed(self):
        value = project_machine.build_inspection(state(), base_sensors(), scope="live")
        value["authorities"] = []
        body = {key: item for key, item in value.items() if key != "inspectionHash"}
        value["inspectionHash"] = project_machine.stable_hash(body)
        with self.assertRaisesRegex(RuntimeError, "PROJECT_MACHINE_AUTHORITIES_MISMATCH"):
            project_machine.validate_inspection(value)

    def test_coherence_tampering_is_rejected_even_if_rehashed(self):
        value = project_machine.build_inspection(state(), base_sensors(), scope="live")
        value["coherence"]["status"] = "FAIL"
        body = {key: item for key, item in value.items() if key != "inspectionHash"}
        value["inspectionHash"] = project_machine.stable_hash(body)
        with self.assertRaisesRegex(RuntimeError, "PROJECT_MACHINE_COHERENCE_MISMATCH"):
            project_machine.validate_inspection(value)

    def test_source_head_mismatch_is_rejected_even_if_rehashed(self):
        value = project_machine.build_inspection(state(), base_sensors(), scope="live")
        value["sourceHeads"]["control"]["sha"] = "9" * 40
        body = {key: item for key, item in value.items() if key != "inspectionHash"}
        value["inspectionHash"] = project_machine.stable_hash(body)
        with self.assertRaisesRegex(RuntimeError, "PROJECT_MACHINE_SOURCE_HEADS_MISMATCH"):
            project_machine.validate_inspection(value)

    def test_done_continuation_is_observation_not_failure(self):
        sensors = base_sensors()
        sensors["continuations"]["data"]["items"] = [
            {"id": "probe-one", "status": "DONE", "branch": "ops/old", "prNumber": 7}
        ]
        value = project_machine.build_inspection(state(), sensors, scope="live")
        self.assertEqual(value["trust"]["status"], "PASS")
        self.assertEqual(value["coherence"]["status"], "PASS")
        self.assertEqual(value["observations"][0]["code"], "TERMINAL_CONTINUATION_RESIDUE")

    def test_maintenance_parity_from_project_machine(self):
        sensors = base_sensors()
        machine = project_machine.build_inspection(state(), sensors, scope="live")
        from_machine = maintenance_inspect.from_project_inspection(machine)
        direct = maintenance_inspect.build_inspection(
            state(),
            sensors["projectState"]["data"]["verification"],
            sensors["git"]["data"]["observed"],
            sensors["capabilities"]["data"]["items"],
            remote_requested=True,
            pull_requests=sensors["pullRequests"]["data"],
            coordination_state=sensors["coordination"]["data"],
            continuations=sensors["continuations"]["data"]["items"],
            machine_trust=machine["trust"],
            machine_coherence=machine["coherence"],
            machine_sensors=machine["sensors"],
        )
        self.assertEqual(from_machine["recommendation"], direct["recommendation"])
        self.assertEqual(from_machine["findings"], direct["findings"])

    def test_project_machine_has_no_apply_surface(self):
        forbidden = {"checkpoint_candidate", "prune_apply", "capability_apply", "update_ref", "atomic_write_json"}
        self.assertTrue(forbidden.isdisjoint(set(project_machine.__dict__)))


if __name__ == "__main__":
    unittest.main()
