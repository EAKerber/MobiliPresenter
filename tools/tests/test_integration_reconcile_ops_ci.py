import importlib.util
import sys
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "integration_reconcile.py"
spec = importlib.util.spec_from_file_location("integration_reconcile_operations_ci", MODULE_PATH)
planner = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = planner
spec.loader.exec_module(planner)


def reentry_run(run_id, name, head="a" * 40):
    return {
        "name": name,
        "id": run_id,
        "status": "completed",
        "conclusion": "action_required",
        "event": "pull_request",
        "headSha": head,
        "actor": "github-actions[bot]",
        "triggeringActor": "github-actions[bot]",
        "sameRepository": True,
        "runAttempt": 1,
        "jobsObserved": True,
        "jobCount": 0,
    }


class IntegrationReconcileOperationsCiTests(unittest.TestCase):
    def test_canonical_operations_branch_uses_agent_ops_as_relevant_ci(self):
        runs = [{"name": "Agent Ops", "status": "completed", "conclusion": "success", "id": 9}]
        result = planner.aggregate_ci(runs, "a" * 40, "work/operations/test")
        self.assertEqual(result["status"], "green")
        self.assertEqual(result["runs"][0]["name"], "Agent Ops")

    def test_product_branch_does_not_treat_agent_ops_as_product_ci(self):
        runs = [{"name": "Agent Ops", "status": "completed", "conclusion": "success", "id": 9}]
        result = planner.aggregate_ci(runs, "a" * 40, "engine/test")
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(result["runs"], [])

    def test_proven_action_required_routes_to_ci_reentry_not_fix_ci(self):
        runs = [
            reentry_run(11, "Coordination Guard"),
            reentry_run(12, "Agent Ops"),
            reentry_run(13, "Supervisor Snapshot"),
        ]
        result = planner.aggregate_ci(runs, "a" * 40, "work/operations/test")
        self.assertEqual(result["status"], "reentry_required")
        observation = {
            "pr": {
                "merged": False,
                "state": "open",
                "baseRef": "main",
            },
            "target": {"branch": "main"},
            "ancestry": {
                "declaredBaseToTarget": {"status": "identical"},
                "targetToHead": {"status": "ahead"},
            },
        }
        recommendation = planner.recommendation(
            observation,
            {"boundaryViolations": []},
            result,
        )
        self.assertEqual(recommendation["action"], "reenter-ci")
        self.assertEqual(recommendation["reason"], "head-ci-reentry-required")


if __name__ == "__main__":
    unittest.main()
