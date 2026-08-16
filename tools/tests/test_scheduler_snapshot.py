import copy
import unittest

from tools import maintenance_inspect, project_machine, scheduler_plan, scheduler_snapshot as snapshot
from tools.canonical import stable_hash
from tools.tests.test_project_machine import base_sensors, state


def pipeline():
    machine = project_machine.build_inspection(state(), base_sensors(), scope="live")
    inspection = maintenance_inspect.from_project_inspection(machine)
    plan = scheduler_plan.build_plan(inspection)
    value = snapshot.build_snapshot(machine, inspection, plan)
    return machine, inspection, plan, value


class SchedulerSnapshotTests(unittest.TestCase):
    def test_valid_snapshot_proves_full_derivation_without_replanning_in_workflow(self):
        machine, inspection, plan, value = pipeline()
        result = snapshot.validate_snapshot(value, source_machine=machine, readback_machine=copy.deepcopy(machine))
        self.assertTrue(result["ok"])
        self.assertEqual(value["schemaVersion"], "SchedulerSnapshot 0.2")
        self.assertEqual(value["projectMachineInspectionHash"], machine["inspectionHash"])
        self.assertEqual(result["inspectionHash"], inspection["inspectionHash"])
        self.assertEqual(result["planHash"], plan["planHash"])

    def test_source_heads_preserve_inspection_and_control_as_distinct_facts(self):
        machine, _, _, value = pipeline()
        self.assertEqual(machine["sourceHeads"]["inspection"]["sha"], "1" * 40)
        self.assertEqual(machine["sourceHeads"]["control"]["sha"], "2" * 40)
        self.assertNotEqual(value["sourceHeads"]["inspection"], value["sourceHeads"]["control"])
        self.assertEqual(value["sourceHeads"], machine["sourceHeads"])

    def test_child_tampering_is_rejected_by_child_contract(self):
        machine, _, _, value = pipeline()
        value["plan"]["dispatch"]["target"] = "developer-ui"
        body = {k: v for k, v in value.items() if k != "snapshotHash"}
        value["snapshotHash"] = stable_hash(body)
        with self.assertRaisesRegex(RuntimeError, "SCHEDULER_PLAN_HASH_MISMATCH"):
            snapshot.validate_snapshot(value, source_machine=machine, readback_machine=machine)

    def test_rehashed_plan_drift_is_rejected_by_derivation(self):
        machine, _, _, value = pipeline()
        value["plan"]["dispatch"]["target"] = "developer-ui"
        plan_body = {k: v for k, v in value["plan"].items() if k != "planHash"}
        value["plan"]["planHash"] = stable_hash(plan_body)
        body = {k: v for k, v in value.items() if k != "snapshotHash"}
        value["snapshotHash"] = stable_hash(body)
        with self.assertRaisesRegex(RuntimeError, "SCHEDULER_PLAN_DERIVATION_MISMATCH"):
            snapshot.validate_snapshot(value, source_machine=machine, readback_machine=machine)

    def test_source_head_tampering_is_rejected_even_if_snapshot_is_rehashed(self):
        machine, _, _, value = pipeline()
        value["sourceHeads"]["coordination"]["sha"] = "9" * 40
        body = {k: v for k, v in value.items() if k != "snapshotHash"}
        value["snapshotHash"] = stable_hash(body)
        with self.assertRaisesRegex(RuntimeError, "SCHEDULER_SNAPSHOT_SOURCE_HEADS_MISMATCH"):
            snapshot.validate_snapshot(value, source_machine=machine, readback_machine=machine)

    def test_explicit_readback_detects_authority_drift(self):
        machine, _, _, value = pipeline()
        changed = base_sensors()
        changed["control"]["data"]["sha"] = "9" * 40
        readback = project_machine.build_inspection(state(), changed, scope="live")
        with self.assertRaisesRegex(RuntimeError, "SCHEDULER_SNAPSHOT_STALE_CONTROL"):
            snapshot.validate_snapshot(value, source_machine=machine, readback_machine=readback)

    def test_source_machine_mismatch_is_not_treated_as_readback_drift(self):
        machine, _, _, value = pipeline()
        changed = base_sensors()
        changed["git"]["data"]["observed"]["head"] = "8" * 40
        wrong_source = project_machine.build_inspection(state(), changed, scope="live")
        with self.assertRaisesRegex(RuntimeError, "SCHEDULER_SNAPSHOT_SOURCE_MACHINE_MISMATCH"):
            snapshot.validate_snapshot(value, source_machine=wrong_source, readback_machine=machine)


if __name__ == "__main__":
    unittest.main()
