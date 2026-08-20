import copy
import unittest

from tools import maintenance_inspect, project_machine, routines, scheduler_plan, scheduler_snapshot as snapshot
from tools.canonical import stable_hash
from tools.tests.test_project_machine import base_sensors, state


def pipeline():
    machine = project_machine.build_inspection(state(), base_sensors(), scope="live")
    routine = routines.build_inspection(machine)
    inspection = maintenance_inspect.from_inputs(machine, routine)
    plan = scheduler_plan.build_plan(inspection)
    value = snapshot.build_snapshot(machine, routine, inspection, plan)
    return machine, routine, inspection, plan, value


class SchedulerSnapshotTests(unittest.TestCase):
    def test_valid_snapshot_proves_full_routine_lineage_without_replanning(self):
        machine, routine, inspection, plan, value = pipeline()
        result = snapshot.validate_snapshot(
            value,
            source_machine=machine,
            routine_inspection=routine,
            readback_machine=copy.deepcopy(machine),
        )
        self.assertTrue(result["ok"])
        self.assertEqual(value["schemaVersion"], "SchedulerSnapshot 0.3")
        self.assertEqual(value["projectMachineInspectionHash"], machine["inspectionHash"])
        self.assertEqual(value["routineInspectionHash"], routine["inspectionHash"])
        self.assertEqual(inspection["routineInspectionHash"], routine["inspectionHash"])
        self.assertEqual(result["inspectionHash"], inspection["inspectionHash"])
        self.assertEqual(result["planHash"], plan["planHash"])

    def test_source_heads_preserve_inspection_and_control_as_distinct_facts(self):
        machine, _, _, _, value = pipeline()
        self.assertEqual(machine["sourceHeads"]["inspection"]["sha"], "1" * 40)
        self.assertEqual(machine["sourceHeads"]["control"]["sha"], "2" * 40)
        self.assertNotEqual(value["sourceHeads"]["inspection"], value["sourceHeads"]["control"])
        self.assertEqual(value["sourceHeads"], machine["sourceHeads"])

    def test_child_tampering_is_rejected_by_child_contract(self):
        machine, routine, _, _, value = pipeline()
        value["plan"]["dispatch"]["target"] = "developer-ui"
        body = {k: v for k, v in value.items() if k != "snapshotHash"}
        value["snapshotHash"] = stable_hash(body)
        with self.assertRaisesRegex(RuntimeError, "SCHEDULER_PLAN_HASH_MISMATCH"):
            snapshot.validate_snapshot(
                value,
                source_machine=machine,
                routine_inspection=routine,
                readback_machine=machine,
            )

    def test_rehashed_plan_drift_is_rejected_by_derivation(self):
        machine, routine, _, _, value = pipeline()
        value["plan"]["dispatch"]["target"] = "developer-ui"
        plan_body = {k: v for k, v in value["plan"].items() if k != "planHash"}
        value["plan"]["planHash"] = stable_hash(plan_body)
        body = {k: v for k, v in value.items() if k != "snapshotHash"}
        value["snapshotHash"] = stable_hash(body)
        with self.assertRaisesRegex(RuntimeError, "SCHEDULER_PLAN_DERIVATION_MISMATCH"):
            snapshot.validate_snapshot(
                value,
                source_machine=machine,
                routine_inspection=routine,
                readback_machine=machine,
            )

    def test_routine_hash_tampering_is_rejected_even_if_snapshot_is_rehashed(self):
        machine, routine, _, _, value = pipeline()
        value["routineInspectionHash"] = "9" * 64
        body = {k: v for k, v in value.items() if k != "snapshotHash"}
        value["snapshotHash"] = stable_hash(body)
        with self.assertRaisesRegex(RuntimeError, "SCHEDULER_SNAPSHOT_ROUTINE_MAINTENANCE_MISMATCH"):
            snapshot.validate_snapshot(
                value,
                source_machine=machine,
                routine_inspection=routine,
                readback_machine=machine,
            )

    def test_wrong_routine_is_rejected_even_when_machine_heads_match(self):
        machine, routine, _, _, value = pipeline()
        changed = base_sensors()
        changed["capabilities"]["data"]["items"] = []
        other_machine = project_machine.build_inspection(state(), changed, scope="live")
        other_routine = routines.build_inspection(other_machine)
        self.assertNotEqual(routine["inspectionHash"], other_routine["inspectionHash"])
        with self.assertRaisesRegex(RuntimeError, "ROUTINE_PROJECT_MACHINE_MISMATCH|ROUTINE_DERIVATION_MISMATCH"):
            snapshot.validate_snapshot(
                value,
                source_machine=machine,
                routine_inspection=other_routine,
                readback_machine=machine,
            )

    def test_source_head_tampering_is_rejected_even_if_snapshot_is_rehashed(self):
        machine, routine, _, _, value = pipeline()
        value["sourceHeads"]["coordination"]["sha"] = "9" * 40
        body = {k: v for k, v in value.items() if k != "snapshotHash"}
        value["snapshotHash"] = stable_hash(body)
        with self.assertRaisesRegex(RuntimeError, "SCHEDULER_SNAPSHOT_SOURCE_HEADS_MISMATCH"):
            snapshot.validate_snapshot(
                value,
                source_machine=machine,
                routine_inspection=routine,
                readback_machine=machine,
            )

    def test_explicit_readback_detects_authority_drift(self):
        machine, routine, _, _, value = pipeline()
        changed = base_sensors()
        changed["control"]["data"]["sha"] = "9" * 40
        readback = project_machine.build_inspection(state(), changed, scope="live")
        with self.assertRaisesRegex(RuntimeError, "SCHEDULER_SNAPSHOT_STALE_CONTROL"):
            snapshot.validate_snapshot(
                value,
                source_machine=machine,
                routine_inspection=routine,
                readback_machine=readback,
            )

    def test_consumer_time_expected_heads_reject_current_authority_drift(self):
        machine, routine, _, _, value = pipeline()
        expected = {name: value["sourceHeads"][name]["sha"] for name in snapshot.CURRENT_HEAD_KEYS}
        snapshot.validate_snapshot(
            value,
            source_machine=machine,
            routine_inspection=routine,
            readback_machine=copy.deepcopy(machine),
            expected_heads=expected,
        )
        changed = dict(expected)
        changed["continuation"] = "9" * 40
        with self.assertRaisesRegex(RuntimeError, "SCHEDULER_SNAPSHOT_STALE_CURRENT_CONTINUATION"):
            snapshot.validate_snapshot(
                value,
                source_machine=machine,
                routine_inspection=routine,
                readback_machine=copy.deepcopy(machine),
                expected_heads=changed,
            )

    def test_source_machine_mismatch_is_not_treated_as_readback_drift(self):
        machine, routine, _, _, value = pipeline()
        changed = base_sensors()
        changed["git"]["data"]["observed"]["head"] = "8" * 40
        wrong_source = project_machine.build_inspection(state(), changed, scope="live")
        with self.assertRaisesRegex(RuntimeError, "SCHEDULER_SNAPSHOT_SOURCE_MACHINE_MISMATCH|ROUTINE_PROJECT_MACHINE_MISMATCH"):
            snapshot.validate_snapshot(
                value,
                source_machine=wrong_source,
                routine_inspection=routine,
                readback_machine=machine,
            )


if __name__ == "__main__":
    unittest.main()
