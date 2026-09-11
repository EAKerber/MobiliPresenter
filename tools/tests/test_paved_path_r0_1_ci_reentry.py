from __future__ import annotations

import unittest

from tools import project_coherence, scheduler_plan
from tools.tests import test_maintenance_inspect as maintenance_fixture
from tools.tests import test_project_ci_observation_s2 as ci_fixture


class PavedPathR01CIReentryTests(unittest.TestCase):
    def test_project_coherence_preserves_reentry_reason(self):
        result = project_coherence.evaluate_coherence(
            ci_fixture.project(),
            ci_fixture.coherence_sensors([ci_fixture.pr(ci="reentry_required")]),
            scope="live",
        )
        check = ci_fixture.coherence_check(result)
        self.assertEqual("UNKNOWN", check["status"])
        self.assertEqual("PR_CI_REENTRY_REQUIRED", check["code"])
        self.assertFalse(check["required"])
        self.assertEqual("PASS", result["status"])

    def test_maintenance_routes_observed_reentry_to_reconcile(self):
        item = maintenance_fixture.work(
            "a", worker="developer-engine", branch="work/operations/a", pr=7
        )
        pr = {
            "number": 7,
            "headRef": "work/operations/a",
            "baseRef": "main",
            "ci": "reentry_required",
            "ciObserved": True,
        }
        _, value = maintenance_fixture.derive(maintenance_fixture.machine([item], [pr]))
        rec = value["recommendation"]
        self.assertEqual("RECONCILE", rec["action"])
        self.assertEqual("WORK_PR_CI_REENTRY_REQUIRED", rec["reasonCode"])
        self.assertEqual("a", rec["workId"])
        self.assertEqual("developer-engine", rec["targetWorkerId"])
        plan = scheduler_plan.build_plan(value)
        self.assertTrue(plan["dispatch"]["shouldWake"])
        self.assertEqual("supervisor", plan["dispatch"]["channelClass"])
        self.assertEqual("a", plan["dispatch"]["workId"])

    def test_unobserved_reentry_remains_unknown_and_needs_human(self):
        item = maintenance_fixture.work(
            "a", worker="developer-engine", branch="work/operations/a", pr=7
        )
        pr = {
            "number": 7,
            "headRef": "work/operations/a",
            "baseRef": "main",
            "ci": "reentry_required",
            "ciObserved": False,
        }
        _, value = maintenance_fixture.derive(maintenance_fixture.machine([item], [pr]))
        rec = value["recommendation"]
        self.assertEqual("NEEDS_HUMAN", rec["action"])
        self.assertEqual("WORK_PR_CI_UNKNOWN", rec["reasonCode"])


if __name__ == "__main__":
    unittest.main()
