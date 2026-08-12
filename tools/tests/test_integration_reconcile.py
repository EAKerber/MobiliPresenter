import copy
import importlib.util
import sys
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "integration_reconcile.py"
spec = importlib.util.spec_from_file_location("integration_reconcile", MODULE_PATH)
planner = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = planner
spec.loader.exec_module(planner)


class IntegrationReconcilePlanTests(unittest.TestCase):
    def fixture(self):
        return {
            "repository": "EAKerber/MobiliPresenter",
            "pr": {
                "number": 33,
                "state": "open",
                "draft": True,
                "merged": False,
                "mergeable": True,
                "headRef": "engine/technical-presentation-fidelity-v0.1",
                "headSha": "b" * 40,
                "baseRef": "integration/viewer-parallel-v0.1",
                "baseSha": "c" * 40,
            },
            "target": {"branch": "main", "sha": "e" * 40},
            "ancestry": {
                "declaredBaseToTarget": {"status": "ahead", "aheadBy": 4, "behindBy": 0, "mergeBaseSha": "c" * 40},
                "targetToHead": {"status": "diverged", "aheadBy": 9, "behindBy": 4, "mergeBaseSha": "c" * 40},
            },
            "changedFiles": [
                "viewer-next/src/api/ui-adapter.ts",
                "viewer-next/src/api/ui-contract.ts",
                "viewer-next/src/presentation/compile.ts",
                "viewer-next/src/presentation/contracts.ts",
                "viewer-next/src/presentation/current-service.ts",
                "viewer-next/src/presentation/technical-diagram.ts",
                "viewer-next/src/presentation/technical-view-geometry.ts",
                "viewer-next/tests/technical-presentation-fidelity.test.mjs",
            ],
            "workflowRuns": [
                {"id": 31563700519, "name": "Viewer Next", "status": "completed", "conclusion": "success"}
            ],
            "projectState": {
                "project": {"repository": "EAKerber/MobiliPresenter"},
                "git": {"controlBranch": "main", "activeDevelopmentBranch": None},
                "development": {
                    "prNumber": None,
                    "phase": "between-increments",
                    "checkpoint": "POST-H6-PUBLISHED",
                    "nextTransition": "open-developer-slice-for-geometry-derived-technical-views",
                    "blockers": ["ui-handoff-30"],
                },
            },
        }

    def test_pr33_fixture_recommends_retarget_and_revalidate(self):
        plan = planner.build_plan(self.fixture())
        self.assertEqual(plan["recommendation"]["action"], "retarget-to-control-and-revalidate")
        self.assertFalse(plan["applyEligible"])
        self.assertEqual(plan["ci"]["status"], "green")
        self.assertEqual(plan["scope"]["changedFileCount"], 8)
        self.assertEqual(len(plan["scope"]["sharedResourcesTouched"]), 2)
        self.assertEqual(plan["scope"]["boundaryViolations"], [])

    def test_hash_is_stable_and_changes_with_head(self):
        first = planner.build_plan(self.fixture())
        second = planner.build_plan(copy.deepcopy(self.fixture()))
        self.assertEqual(first["planHash"], second["planHash"])
        changed = self.fixture()
        changed["pr"]["headSha"] = "d" * 40
        third = planner.build_plan(changed)
        self.assertNotEqual(first["planHash"], third["planHash"])

    def test_engine_ui_cross_boundary_is_blocking_signal(self):
        observation = self.fixture()
        observation["changedFiles"].append("viewer-next/src/ui/product-shell.ts")
        plan = planner.build_plan(observation)
        self.assertEqual(plan["recommendation"]["action"], "semantic-owner-review")
        self.assertEqual(plan["scope"]["boundaryViolations"][0]["code"], "ENGINE_TOUCHED_UI")

    def test_ui_engine_cross_boundary_is_blocking_signal(self):
        result = planner.boundary_assessment("ui/test", ["viewer-next/src/presentation/compile.ts"])
        self.assertEqual(result["boundaryViolations"][0]["code"], "UI_TOUCHED_ENGINE_DOMAIN")

    def test_shared_api_is_review_not_violation(self):
        result = planner.boundary_assessment("engine/test", ["viewer-next/src/api/ui-contract.ts"])
        self.assertEqual(result["boundaryViolations"], [])
        self.assertEqual(result["boundaryReview"][0]["code"], "SHARED_API_CONTRACT_REVIEW")

    def test_failed_ci_blocks_recommendation(self):
        observation = self.fixture()
        observation["pr"]["baseRef"] = "main"
        observation["pr"]["baseSha"] = observation["target"]["sha"]
        observation["ancestry"]["declaredBaseToTarget"] = {
            "status": "identical", "aheadBy": 0, "behindBy": 0, "mergeBaseSha": observation["target"]["sha"]
        }
        observation["workflowRuns"] = [
            {"name": "Viewer Next", "status": "completed", "conclusion": "failure", "id": 1}
        ]
        plan = planner.build_plan(observation)
        self.assertEqual(plan["recommendation"]["action"], "fix-ci-before-integration")

    def test_merged_pr_marks_active_identity_stale(self):
        observation = self.fixture()
        observation["pr"]["merged"] = True
        observation["pr"]["state"] = "closed"
        observation["projectState"]["git"]["activeDevelopmentBranch"] = observation["pr"]["headRef"]
        observation["projectState"]["development"]["prNumber"] = 33
        plan = planner.build_plan(observation)
        self.assertEqual(plan["recommendation"]["action"], "already-merged")
        self.assertIn("git.activeDevelopmentBranch", plan["canonicalState"]["likelyStaleFields"])
        self.assertIn("development.prNumber", plan["canonicalState"]["likelyStaleFields"])

    def test_ci_uses_latest_run_per_workflow_name(self):
        runs = [
            {"name": "Viewer Next", "status": "completed", "conclusion": "success", "id": 2},
            {"name": "Viewer Next", "status": "completed", "conclusion": "failure", "id": 1},
            {"name": "Agent Ops", "status": "completed", "conclusion": "failure", "id": 9},
        ]
        result = planner.aggregate_ci(runs, "a" * 40)
        self.assertEqual(result["status"], "green")
        self.assertEqual(len(result["runs"]), 1)


if __name__ == "__main__":
    unittest.main()
