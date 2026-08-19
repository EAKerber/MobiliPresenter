import unittest
from pathlib import Path

from tools import routines

ROOT = Path(__file__).resolve().parents[2]


class RoutineCoverageTests(unittest.TestCase):
    def test_catalog_is_sorted_unique_and_has_required_deathcircle(self):
        catalog = routines.ROUTINE_CATALOG
        ids = [item.id for item in catalog]
        self.assertEqual(ids, sorted(ids))
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("capability-deathcircle", ids)
        self.assertTrue(next(item for item in catalog if item.id == "capability-deathcircle").required)

    def test_missing_required_routine_is_explicit(self):
        coverage = routines.coverage_for(routines.ROUTINE_CATALOG, [])
        self.assertEqual(coverage["required"], ["capability-deathcircle"])
        self.assertEqual(coverage["evaluated"], [])
        self.assertEqual(coverage["missing"], ["capability-deathcircle"])

    def test_shadow_routine_runs_in_both_operational_workflows(self):
        agent = (ROOT / ".github/workflows/agent-ops.yml").read_text(encoding="utf-8")
        supervisor = (ROOT / ".github/workflows/supervisor-snapshot.yml").read_text(encoding="utf-8")
        for workflow in (agent, supervisor):
            self.assertIn("tools/routines.py inspect", workflow)
            self.assertIn("tools/routines.py validate", workflow)
            self.assertIn("/tmp/routine-inspection.json", workflow)

    def test_routine_layer_is_not_scheduler_or_authority_writer(self):
        source = (ROOT / "tools/routines.py").read_text(encoding="utf-8")
        for forbidden in (
            "from tools.semantics.actions",
            "coordination_remote",
            "continuation_remote",
            "update_ref(",
            "mutation-plan",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
