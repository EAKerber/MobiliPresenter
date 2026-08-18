import unittest
from unittest.mock import patch

from tools import project_sensors


REPOSITORY = "EAKerber/MobiliPresenter"


def state():
    return {
        "schemaVersion": "ProjectState 2.1",
        "project": {"id": "mobilipresenter", "repository": REPOSITORY},
        "git": {"controlBranch": "main", "protectedBranches": ["architecture/tpc"]},
        "published": {"url": "x", "artifactManifest": "ops/published/viewer-next-current.json"},
        "development": {"initiative": "I", "phase": "between-increments", "checkpoint": "C", "nextTransition": "next"},
    }


class ProjectSensorsTests(unittest.TestCase):
    def test_remote_sensors_are_optional_in_local_scope(self):
        result = project_sensors.observe_pull_requests(REPOSITORY, live=False)
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertFalse(result["required"])
        self.assertEqual(result["code"], "NOT_OBSERVED_IN_LOCAL_SCOPE")

    def test_branch_backed_authorities_do_not_fallback_to_checkout(self):
        for result in (project_sensors.observe_continuations_local(), project_sensors.observe_coordination(live=False)):
            self.assertEqual(result["status"], "UNKNOWN")
            self.assertFalse(result["required"])
            self.assertEqual(result["code"], "NOT_OBSERVED_IN_LOCAL_SCOPE")
            self.assertFalse(result["data"]["available"])

    def test_local_sensor_import_does_not_materialize_live_authority_adapters(self):
        for name in (
            "continuation_remote",
            "coordination_remote",
            "GitHubContinuationAuthority",
            "GitHubCoordinationAuthority",
            "GhApiTransport",
        ):
            self.assertNotIn(name, project_sensors.__dict__)

    def test_pr_sensor_does_not_classify_prs(self):
        payloads = [(True, [{"number": 7, "draft": False, "head": {"ref": "ops/work", "sha": "1" * 40}, "base": {"ref": "main"}}]), (True, {"workflow_runs": []})]
        with patch("tools.project_sensors.agent.run_gh_json", side_effect=payloads):
            result = project_sensors.observe_pull_requests(REPOSITORY, live=True)
        self.assertEqual(result["status"], "PASS")
        self.assertNotIn("classification", result["data"]["items"][0])
        self.assertTrue(result["data"]["items"][0]["ciObserved"])

    def test_known_pending_ci_keeps_sensor_pass(self):
        payloads = [(True, [{"number": 7, "draft": False, "head": {"ref": "ops/work", "sha": "1" * 40}, "base": {"ref": "main"}}]), (True, {"workflow_runs": [{"name": "Supervisor Snapshot", "status": "in_progress", "conclusion": None, "id": 1}]})]
        with patch("tools.project_sensors.agent.run_gh_json", side_effect=payloads):
            result = project_sensors.observe_pull_requests(REPOSITORY, live=True)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["data"]["items"][0]["ci"], "pending")

    def test_unobservable_ci_is_factual_unknown_inside_passed_pr_inventory(self):
        payloads = [(True, [{"number": 7, "draft": False, "head": {"ref": "ops/work", "sha": "1" * 40}, "base": {"ref": "main"}}]), (False, {"error": "unavailable"})]
        with patch("tools.project_sensors.agent.run_gh_json", side_effect=payloads):
            result = project_sensors.observe_pull_requests(REPOSITORY, live=True)
        self.assertEqual(result["status"], "PASS")
        self.assertIsNone(result["code"])
        self.assertTrue(result["data"]["available"])
        self.assertEqual(result["data"]["items"][0]["ci"], "unknown")
        self.assertFalse(result["data"]["items"][0]["ciObserved"])

    def test_local_core_reuses_materialized_state_source_build_and_worktree(self):
        observed={"available":True,"worktree":True,"branch":"main","head":"1"*40,"origin":"https://github.com/EAKerber/MobiliPresenter.git","dirty":False}
        with patch("tools.project_sensors.project_state.load_state") as reload_state, \
             patch("tools.project_sensors.agent.verify_state") as legacy_verify, \
             patch("tools.project_sensors.agent.observed_git", return_value=observed) as observe_git, \
             patch("tools.project_sensors.publication.load_manifest", wraps=project_sensors.publication.load_manifest) as load_manifest:
            result=project_sensors.observe_local_core(state())
        reload_state.assert_not_called();legacy_verify.assert_not_called();observe_git.assert_called_once();load_manifest.assert_called_once()
        self.assertEqual(result["projectState"]["status"],"PASS")
        self.assertEqual(result["publication"]["status"],"PASS")
        self.assertEqual(result["git"]["status"],"PASS")
        self.assertEqual(result["git"]["data"]["observed"],observed)

    def test_removed_derived_helpers_are_not_present(self):
        self.assertFalse(hasattr(project_sensors, "classify_pr"))
        self.assertFalse(hasattr(project_sensors, "observe_development"))


if __name__ == "__main__":
    unittest.main()
