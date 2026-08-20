import copy
import unittest
from tools import scheduler_plan as scheduler
from tools.canonical import stable_hash

SOURCE_HASH = "f" * 64
ROUTINE_HASH = "e" * 64


def inspection(action="CONTINUE", focus="development", work_id=None, target=None):
    value = {
        "schemaVersion": "MaintenanceInspection 0.6",
        "repository": "EAKerber/MobiliPresenter",
        "projectMachineInspectionHash": SOURCE_HASH,
        "routineInspectionHash": ROUTINE_HASH,
        "findings": [],
        "recommendation": {
            "action": action,
            "reasonCode": "TEST",
            "focus": focus,
            "detail": "test",
            "decisionScope": "operational-only",
            "semanticAuthority": False,
            "allowedActions": ["CONTINUE", "RECONCILE", "HANDOFF", "PAUSE", "NEEDS_HUMAN"],
            "workId": work_id,
            "targetWorkerId": target,
        },
        "readOnly": True,
    }
    value["inspectionHash"] = stable_hash(value)
    return value


class SchedulerPlan02Tests(unittest.TestCase):
    def test_rejects_tampered_inspection(self):
        value = inspection()
        value["recommendation"]["focus"] = "tampered"
        with self.assertRaisesRegex(RuntimeError, "MAINTENANCE_HASH_MISMATCH"):
            scheduler.build_plan(value)

    def test_handoff_routes_only_explicit_worker_target(self):
        value = inspection("HANDOFF", "work:task-one", "task-one", "developer-engine")
        plan = scheduler.build_plan(value)
        self.assertEqual(plan["schemaVersion"], "SchedulerPlan 0.2")
        self.assertEqual(plan["dispatch"]["target"], "developer-engine")
        self.assertEqual(plan["dispatch"]["channelClass"], "worker")
        self.assertEqual(plan["dispatch"]["workId"], "task-one")
        bad = inspection("HANDOFF", "work:task-one", "task-one", None)
        with self.assertRaisesRegex(RuntimeError, "SCHEDULER_HANDOFF_TARGET_INVALID"):
            scheduler.build_plan(bad)

    def test_continue_work_routes_worker_id(self):
        plan = scheduler.build_plan(
            inspection("CONTINUE", "work:task-one", "task-one", "developer-ui")
        )
        self.assertEqual(plan["dispatch"]["target"], "developer-ui")
        self.assertEqual(plan["dispatch"]["workId"], "task-one")

    def test_generic_continue_stays_with_supervisor(self):
        plan = scheduler.build_plan(inspection())
        self.assertEqual(
            plan["dispatch"],
            {
                "shouldWake": True,
                "channelClass": "supervisor",
                "target": "gitops-supervisor",
                "workId": None,
            },
        )

    def test_non_actionable_routing(self):
        self.assertFalse(scheduler.build_plan(inspection("PAUSE"))["dispatch"]["shouldWake"])
        self.assertEqual(
            scheduler.build_plan(inspection("RECONCILE"))["dispatch"]["channelClass"],
            "supervisor",
        )
        self.assertEqual(
            scheduler.build_plan(inspection("NEEDS_HUMAN"))["dispatch"]["channelClass"],
            "human",
        )

    def test_plan_is_deterministic_read_only_and_transport_free(self):
        value = inspection()
        a = scheduler.build_plan(value)
        b = scheduler.build_plan(copy.deepcopy(value))
        self.assertEqual(a["planHash"], b["planHash"])
        self.assertTrue(a["readOnly"])
        self.assertFalse(a["transportSideEffects"])
        self.assertFalse(a["semanticAuthority"])
        self.assertTrue(scheduler.validate_plan(a)["ok"])
        self.assertTrue(scheduler.validate_derivation(a, value)["ok"])

    def test_unsupported_or_semantic_inspection_is_rejected_by_maintenance_contract(self):
        value = inspection()
        value["schemaVersion"] = "MaintenanceInspection 99"
        value["inspectionHash"] = stable_hash({k: v for k, v in value.items() if k != "inspectionHash"})
        with self.assertRaisesRegex(RuntimeError, "MAINTENANCE_SCHEMA_UNSUPPORTED"):
            scheduler.build_plan(value)
        value = inspection()
        value["recommendation"]["semanticAuthority"] = True
        value["inspectionHash"] = stable_hash({k: v for k, v in value.items() if k != "inspectionHash"})
        with self.assertRaisesRegex(RuntimeError, "MAINTENANCE_SEMANTIC_AUTHORITY_INVALID"):
            scheduler.build_plan(value)

    def test_plan_derivation_rejects_rehashed_routing_drift(self):
        source = inspection()
        plan = scheduler.build_plan(source)
        plan["dispatch"]["target"] = "developer-ui"
        body = {k: v for k, v in plan.items() if k != "planHash"}
        plan["planHash"] = stable_hash(body)
        with self.assertRaisesRegex(RuntimeError, "SCHEDULER_PLAN_DERIVATION_MISMATCH"):
            scheduler.validate_derivation(plan, source)


if __name__ == "__main__":
    unittest.main()
