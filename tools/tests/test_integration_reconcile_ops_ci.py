import importlib.util
import sys
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "integration_reconcile.py"
spec = importlib.util.spec_from_file_location("integration_reconcile_ops_ci", MODULE_PATH)
planner = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = planner
spec.loader.exec_module(planner)


class IntegrationReconcileOpsCiTests(unittest.TestCase):
    def test_ops_branch_uses_agent_ops_as_relevant_ci(self):
        runs = [{"name": "Agent Ops", "status": "completed", "conclusion": "success", "id": 9}]
        result = planner.aggregate_ci(runs, "a" * 40, "ops/test")
        self.assertEqual(result["status"], "green")
        self.assertEqual(result["runs"][0]["name"], "Agent Ops")

    def test_product_branch_does_not_treat_agent_ops_as_product_ci(self):
        runs = [{"name": "Agent Ops", "status": "completed", "conclusion": "success", "id": 9}]
        result = planner.aggregate_ci(runs, "a" * 40, "engine/test")
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(result["runs"], [])


if __name__ == "__main__":
    unittest.main()
