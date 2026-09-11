from __future__ import annotations

import unittest
from unittest.mock import patch

from tools import integration_reconcile, project_ci_observation, project_sensors


REPOSITORY = "EAKerber/MobiliPresenter"
HEAD = "a" * 40


def enriched_run(
    run_id: int,
    *,
    name: str = "Viewer Next",
    status: str = "completed",
    conclusion: str = "success",
    head_sha: str = HEAD,
    attempt: int = 1,
):
    return {
        "name": name,
        "id": run_id,
        "status": status,
        "conclusion": conclusion,
        "event": "pull_request",
        "headSha": head_sha,
        "actor": "github-actions[bot]",
        "triggeringActor": "github-actions[bot]",
        "sameRepository": True,
        "runAttempt": attempt,
        "jobsObserved": conclusion == "action_required",
        "jobCount": 0 if conclusion == "action_required" else None,
    }


class ProjectCiCompletenessTests(unittest.TestCase):
    def test_latest_run_is_independent_of_provider_order(self):
        older = enriched_run(1, conclusion="failure")
        newer = enriched_run(2, conclusion="success")
        for runs in ([older, newer], [newer, older]):
            self.assertEqual("green", project_ci_observation.classify_runs(runs, HEAD))
            self.assertEqual(
                [2],
                [item["id"] for item in project_ci_observation.latest_runs(runs)],
            )

    def test_attempt_breaks_tie_for_same_run_id(self):
        first = enriched_run(4, conclusion="failure", attempt=1)
        retry = enriched_run(4, conclusion="success", attempt=2)
        self.assertEqual(
            "green",
            project_ci_observation.classify_runs([first, retry], HEAD),
        )
        self.assertEqual(
            2,
            project_ci_observation.latest_runs([first, retry])[0]["runAttempt"],
        )

    def test_incomplete_positive_ci_is_unknown(self):
        self.assertEqual(
            "unknown",
            project_ci_observation.classify_runs(
                [enriched_run(2)],
                HEAD,
                observation_complete=False,
            ),
        )
        self.assertEqual(
            "unknown",
            project_ci_observation.classify_runs(
                [enriched_run(2, conclusion="action_required")],
                HEAD,
                observation_complete=False,
            ),
        )

    def test_incomplete_negative_ci_keeps_known_negative_evidence(self):
        self.assertEqual(
            "failed",
            project_ci_observation.classify_runs(
                [enriched_run(2, conclusion="failure")],
                HEAD,
                observation_complete=False,
            ),
        )
        self.assertEqual(
            "pending",
            project_ci_observation.classify_runs(
                [enriched_run(2, status="in_progress", conclusion=None)],
                HEAD,
                observation_complete=False,
            ),
        )

    def test_explicit_foreign_head_cannot_classify_green(self):
        self.assertEqual(
            "unknown",
            project_ci_observation.classify_runs(
                [enriched_run(2, head_sha="b" * 40)],
                HEAD,
            ),
        )

    def test_project_sensor_invalid_run_cannot_disappear_into_green(self):
        pulls = [
            {
                "number": 7,
                "draft": False,
                "head": {"ref": "work/operations/test", "sha": HEAD},
                "base": {"ref": "main"},
            }
        ]
        workflow_payload = {
            "total_count": 2,
            "workflow_runs": [
                {
                    "id": 2,
                    "name": "Agent Ops",
                    "status": "completed",
                    "conclusion": "success",
                    "head_sha": HEAD,
                },
                {
                    "id": 1,
                    "status": "completed",
                    "conclusion": "success",
                    "head_sha": HEAD,
                },
            ],
        }
        with patch(
            "tools.project_sensors.agent.run_gh_json",
            side_effect=[(True, pulls), (True, workflow_payload)],
        ):
            result = project_sensors.observe_pull_requests(REPOSITORY, live=True)
        item = result["data"]["items"][0]
        self.assertTrue(item["ciObserved"])
        self.assertFalse(item["ciComplete"])
        self.assertEqual("unknown", item["ci"])

    def test_project_sensor_paginates_workflow_runs(self):
        pulls = [
            {
                "number": 7,
                "draft": False,
                "head": {"ref": "work/operations/test", "sha": HEAD},
                "base": {"ref": "main"},
            }
        ]
        first = [
            {
                "id": value,
                "name": f"W{value}",
                "status": "completed",
                "conclusion": "success",
                "head_sha": HEAD,
            }
            for value in range(1, 101)
        ]
        second = [
            {
                "id": 101,
                "name": "W101",
                "status": "completed",
                "conclusion": "success",
                "head_sha": HEAD,
            }
        ]
        with patch(
            "tools.project_sensors.agent.run_gh_json",
            side_effect=[
                (True, pulls),
                (True, {"total_count": 101, "workflow_runs": first}),
                (True, {"total_count": 101, "workflow_runs": second}),
            ],
        ):
            result = project_sensors.observe_pull_requests(REPOSITORY, live=True)
        item = result["data"]["items"][0]
        self.assertTrue(item["ciComplete"])
        self.assertEqual("green", item["ci"])
        self.assertEqual(101, len(item["workflows"]))

    def test_integration_reconcile_uses_shared_selection(self):
        older = enriched_run(1, conclusion="failure")
        newer = enriched_run(2, conclusion="success")
        for runs in ([older, newer], [newer, older]):
            result = integration_reconcile.aggregate_ci(
                runs, HEAD, "work/operations/test"
            )
            self.assertEqual("green", result["status"])
            self.assertTrue(result["observationComplete"])
            self.assertEqual(2, result["runs"][0]["id"])

    def test_integration_reconcile_incomplete_observation_is_not_green(self):
        result = integration_reconcile.aggregate_ci(
            [enriched_run(2)],
            HEAD,
            "work/operations/test",
            observation_complete=False,
        )
        self.assertEqual("unknown", result["status"])
        self.assertFalse(result["observationComplete"])

    def test_integration_observer_paginates_workflow_runs(self):
        observer = integration_reconcile.GhObserver(REPOSITORY)
        first = [
            {
                "id": value,
                "name": f"W{value}",
                "status": "completed",
                "conclusion": "success",
                "head_sha": HEAD,
            }
            for value in range(1, 101)
        ]
        second = [
            {
                "id": 101,
                "name": "W101",
                "status": "completed",
                "conclusion": "success",
                "head_sha": HEAD,
            }
        ]
        with patch.object(
            observer,
            "_run",
            side_effect=[
                {"total_count": 101, "workflow_runs": first},
                {"total_count": 101, "workflow_runs": second},
            ],
        ):
            runs, complete = observer._workflow_runs(REPOSITORY, HEAD)
        self.assertTrue(complete)
        self.assertEqual(101, len(runs))


if __name__ == "__main__":
    unittest.main()
