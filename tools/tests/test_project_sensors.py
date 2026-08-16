import unittest

from tools import project_sensors


def state(active=None, pr=None):
    return {
        "project": {"repository": "EAKerber/MobiliPresenter"},
        "git": {"activeDevelopmentBranch": active, "controlBranch": "main", "preserveBranches": ["architecture/tpc"]},
        "development": {"phase": "between-increments", "checkpoint": "C", "nextTransition": "next", "prNumber": pr, "blockers": []},
    }


class ProjectSensorsTests(unittest.TestCase):
    def test_operations_namespace_is_classified_generically(self):
        self.assertEqual(project_sensors.classify_pr(state(), "ops/project-machine-m1"), "operations")

    def test_preserved_and_unclassified_pr_classes(self):
        self.assertEqual(project_sensors.classify_pr(state(), "architecture/tpc"), "preserved")
        self.assertEqual(project_sensors.classify_pr(state(), "feature/mystery"), "unclassified")

    def test_no_active_development_is_known_pass(self):
        result = project_sensors.observe_development(state(), project_sensors.sensor("PASS", data={"available": True, "items": []}), live=True)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["code"], "NO_ACTIVE_DEVELOPMENT")

    def test_active_pr_pending_is_unknown(self):
        current = state("engine/work", 7)
        prs = project_sensors.sensor("PASS", data={"available": True, "items": [{"number": 7, "headRef": "engine/work", "baseRef": "main", "ci": "pending"}]})
        result = project_sensors.observe_development(current, prs, live=True)
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertEqual(result["code"], "REMOTE_CI_PENDING")

    def test_active_pr_divergence_fails(self):
        current = state("engine/work", 7)
        prs = project_sensors.sensor("PASS", data={"available": True, "items": [{"number": 7, "headRef": "other/work", "baseRef": "main", "ci": "green"}]})
        result = project_sensors.observe_development(current, prs, live=True)
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["code"], "REMOTE_PR_DIVERGENCE")

    def test_remote_sensors_are_optional_in_local_scope(self):
        result = project_sensors.observe_pull_requests(state(), live=False)
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertFalse(result["required"])
        self.assertEqual(result["code"], "NOT_OBSERVED_IN_LOCAL_SCOPE")


if __name__ == "__main__":
    unittest.main()
