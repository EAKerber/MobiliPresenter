import unittest

from tools import maintenance_inspect as maintenance
from tools.tests.test_maintenance_inspect import cap, machine


class CapabilityPromotionBoundaryTests(unittest.TestCase):
    def test_canonical_isolated_capability_does_not_reactivate_stale_experimental_review(self):
        promoted = cap("canonical", "TEST_NEXT_GATES", isolated=True)
        value = maintenance.from_project_inspection(machine(capabilities=[promoted]))
        recommendation = value["recommendation"]
        self.assertEqual(recommendation["action"], "CONTINUE")
        self.assertEqual(recommendation["reasonCode"], "NEXT_TRANSITION_AVAILABLE")
        self.assertEqual(recommendation["focus"], "development")


if __name__ == "__main__":
    unittest.main()
