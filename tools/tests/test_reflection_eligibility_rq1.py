from __future__ import annotations

import copy
import unittest

from tools import maintenance_inspect, reflection_eligibility, routines, scheduler_plan, scheduler_snapshot
from tools.canonical import stable_hash
from tools.tests.test_maintenance_inspect import cap, machine, work


def pipeline(m):
    routine = routines.build_inspection(m)
    maintenance = maintenance_inspect.from_inputs(m, routine)
    plan = scheduler_plan.build_plan(maintenance)
    snapshot = scheduler_snapshot.build_snapshot(m, routine, maintenance, plan)
    return routine, maintenance, plan, snapshot


def inspect(m, *, readback=None):
    routine, _, _, snapshot = pipeline(m)
    return reflection_eligibility.build_inspection(
        snapshot,
        source_machine=m,
        routine_inspection=routine,
        readback_machine=copy.deepcopy(m) if readback is None else readback,
    )


class ReflectionEligibilityRQ1Tests(unittest.TestCase):
    def test_next_transition_is_reflection_eligible_but_not_assignment(self):
        value = inspect(machine())
        self.assertEqual("REFLECTION_ELIGIBLE", value["status"])
        self.assertTrue(value["reflectionEligible"])
        self.assertEqual("REFLECT", value["nextSafeAction"])
        self.assertEqual("CONTINUE", value["operationalAction"])
        self.assertEqual("NEXT_TRANSITION_AVAILABLE", value["operationalReasonCode"])
        self.assertEqual("development", value["focus"])
        self.assertIsNone(value["workId"])
        self.assertEqual(
            ["NEXT_TRANSITION_AVAILABLE", "ROADMAP_DIRECTION_NOT_ASSIGNMENT"],
            value["reasonCodes"],
        )
        self.assertFalse(value["semanticAuthority"])
        self.assertFalse(value["authorizesMutation"])

    def test_waiting_work_allows_reflection_without_claiming_quiescence(self):
        value = inspect(machine([work("a", "WAITING")]))
        self.assertEqual("LEGITIMATE_WAIT", value["status"])
        self.assertTrue(value["reflectionEligible"])
        self.assertEqual("WAIT_OR_REFLECT", value["nextSafeAction"])
        self.assertEqual("WORK_WAITING", value["operationalReasonCode"])
        self.assertEqual("a", value["workId"])

    def test_pending_ci_is_legitimate_wait(self):
        item = work("a", branch="work/ui/a", pr=7)
        prs = [
            {
                "number": 7,
                "headRef": "work/ui/a",
                "baseRef": "main",
                "ci": "pending",
                "ciObserved": True,
            }
        ]
        value = inspect(machine([item], prs))
        self.assertEqual("LEGITIMATE_WAIT", value["status"])
        self.assertEqual("WORK_PR_CI_PENDING", value["operationalReasonCode"])
        self.assertEqual("a", value["workId"])

    def test_runnable_work_has_priority_over_reflection(self):
        value = inspect(machine([work("a")]))
        self.assertEqual("PRIORITY_OPERATION_REQUIRED", value["status"])
        self.assertFalse(value["reflectionEligible"])
        self.assertEqual("HONOR_OPERATIONAL_PRIORITY", value["nextSafeAction"])
        self.assertEqual("WORK_RUNNABLE", value["operationalReasonCode"])
        self.assertEqual("a", value["workId"])

    def test_handoff_and_reconcile_have_priority(self):
        handoff = inspect(machine([work("a", "HANDOFF", target="developer-engine")]))
        self.assertEqual("PRIORITY_OPERATION_REQUIRED", handoff["status"])
        self.assertEqual("HANDOFF", handoff["operationalAction"])

        item = work("a", branch="work/ui/a", pr=7)
        prs = [
            {
                "number": 7,
                "headRef": "work/ui/a",
                "baseRef": "main",
                "ci": "failed",
                "ciObserved": True,
            }
        ]
        failed = inspect(machine([item], prs))
        self.assertEqual("PRIORITY_OPERATION_REQUIRED", failed["status"])
        self.assertEqual("RECONCILE", failed["operationalAction"])

    def test_known_human_decision_is_operational_priority(self):
        experimental = cap("experimental", "REVIEW_EMPTY_LIMIT")
        value = inspect(machine(capabilities=[experimental]))
        self.assertEqual("NEEDS_HUMAN", value["operationalAction"])
        self.assertEqual("CAPABILITY_EMPTY_LIMIT", value["operationalReasonCode"])
        self.assertEqual("PRIORITY_OPERATION_REQUIRED", value["status"])
        self.assertFalse(value["reflectionEligible"])

    def test_unknown_ci_is_insufficient_observation(self):
        item = work("a", branch="work/ui/a", pr=7)
        prs = [
            {
                "number": 7,
                "headRef": "work/ui/a",
                "baseRef": "main",
                "ci": "unknown",
                "ciObserved": False,
            }
        ]
        value = inspect(machine([item], prs))
        self.assertEqual("INSUFFICIENT_OBSERVATION", value["status"])
        self.assertFalse(value["reflectionEligible"])
        self.assertEqual("OBSERVE", value["nextSafeAction"])
        self.assertEqual("WORK_PR_CI_UNKNOWN", value["operationalReasonCode"])

    def test_active_routine_work_outranks_waiting_work(self):
        experimental = cap("experimental", "TEST_NEXT_GATES")
        value = inspect(
            machine([work("a", "WAITING")], capabilities=[experimental])
        )
        self.assertEqual("PRIORITY_OPERATION_REQUIRED", value["status"])
        self.assertEqual("CAPABILITY_GATES_DUE", value["operationalReasonCode"])
        self.assertIsNone(value["workId"])

    def test_readback_drift_fails_before_reflection_classification(self):
        source = machine()
        routine, _, _, snapshot = pipeline(source)
        readback = machine([work("a")])
        with self.assertRaisesRegex(RuntimeError, "SCHEDULER_SNAPSHOT_STALE_CONTINUATION"):
            reflection_eligibility.build_inspection(
                snapshot,
                source_machine=source,
                routine_inspection=routine,
                readback_machine=readback,
            )

    def test_rehashed_status_tampering_is_rejected(self):
        value = inspect(machine())
        value["status"] = "PRIORITY_OPERATION_REQUIRED"
        body = {key: item for key, item in value.items() if key != "inspectionHash"}
        value["inspectionHash"] = stable_hash(body)
        with self.assertRaisesRegex(RuntimeError, "REFLECTION_ELIGIBILITY_STATUS_MISMATCH"):
            reflection_eligibility.validate_inspection(value)

    def test_rehashed_roadmap_subject_tampering_is_rejected(self):
        value = inspect(machine())
        value["focus"] = "work:a"
        body = {key: item for key, item in value.items() if key != "inspectionHash"}
        value["inspectionHash"] = stable_hash(body)
        with self.assertRaisesRegex(RuntimeError, "REFLECTION_ELIGIBILITY_ROADMAP_DIRECTION_INVALID"):
            reflection_eligibility.validate_inspection(value)

    def test_exact_derivation_rejects_rehashed_source_binding_drift(self):
        source = machine()
        routine, _, _, snapshot = pipeline(source)
        value = reflection_eligibility.build_inspection(
            snapshot,
            source_machine=source,
            routine_inspection=routine,
            readback_machine=source,
        )
        value["schedulerPlanHash"] = "9" * 64
        body = {key: item for key, item in value.items() if key != "inspectionHash"}
        value["inspectionHash"] = stable_hash(body)
        with self.assertRaisesRegex(RuntimeError, "REFLECTION_ELIGIBILITY_DERIVATION_MISMATCH"):
            reflection_eligibility.validate_derivation(
                value,
                snapshot,
                source_machine=source,
                routine_inspection=routine,
                readback_machine=source,
            )


if __name__ == "__main__":
    unittest.main()
