import unittest
from unittest.mock import patch

from tools import project_sensors


def state(active=None, pr=None):
    return {
        "schemaVersion": "ProjectState 2.0",
        "project": {"id": "mobilipresenter", "repository": "EAKerber/MobiliPresenter"},
        "git": {"activeDevelopmentBranch": active, "controlBranch": "main", "protectedBranches": ["architecture/tpc"]},
        "published": {"url": "x", "artifactManifest": "ops/published/viewer-next-current.json"},
        "development": {"initiative": "I", "phase": "between-increments", "checkpoint": "C", "nextTransition": "next", "prNumber": pr, "blockers": []},
    }


class ProjectSensorsTests(unittest.TestCase):
    def test_remote_sensors_are_optional_in_local_scope(self):
        result = project_sensors.observe_pull_requests(state(), live=False)
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertFalse(result["required"])
        self.assertEqual(result["code"], "NOT_OBSERVED_IN_LOCAL_SCOPE")

    def test_pr_sensor_does_not_classify_prs(self):
        payloads = [(True, [{"number": 7, "draft": False, "head": {"ref": "ops/work", "sha": "1" * 40}, "base": {"ref": "main"}}]), (True, {"workflow_runs": []})]
        with patch("tools.project_sensors.agent.run_gh_json", side_effect=payloads):
            result = project_sensors.observe_pull_requests(state(), live=True)
        self.assertEqual(result["status"], "PASS")
        self.assertNotIn("classification", result["data"]["items"][0])
        self.assertTrue(result["data"]["items"][0]["ciObserved"])

    def test_known_pending_active_ci_keeps_sensor_pass(self):
        payloads = [(True, [{"number": 7, "draft": False, "head": {"ref": "ops/work", "sha": "1" * 40}, "base": {"ref": "main"}}]), (True, {"workflow_runs": [{"name": "Supervisor Snapshot", "status": "in_progress", "conclusion": None, "id": 1}]})]
        with patch("tools.project_sensors.agent.run_gh_json", side_effect=payloads):
            result = project_sensors.observe_pull_requests(state("ops/work", 7), live=True)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["data"]["items"][0]["ci"], "pending")

    def test_unobservable_active_ci_marks_sensor_unknown(self):
        payloads = [(True, [{"number": 7, "draft": False, "head": {"ref": "ops/work", "sha": "1" * 40}, "base": {"ref": "main"}}]), (False, {"error": "unavailable"})]
        with patch("tools.project_sensors.agent.run_gh_json", side_effect=payloads):
            result = project_sensors.observe_pull_requests(state("ops/work", 7), live=True)
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertEqual(result["code"], "ACTIVE_PR_CI_UNAVAILABLE")
        self.assertTrue(result["data"]["available"])
        self.assertFalse(result["data"]["items"][0]["ciObserved"])

    def test_removed_derived_helpers_are_not_present(self):
        self.assertFalse(hasattr(project_sensors, "classify_pr"))
        self.assertFalse(hasattr(project_sensors, "observe_development"))


if __name__ == "__main__":
    unittest.main()
