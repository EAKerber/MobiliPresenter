from __future__ import annotations

import unittest

from tools import agent_cycle_resources, git_mutation_plan


class AgentCycleDeliveryBoundaryTests(unittest.TestCase):
    def test_pr_and_merge_are_canonical_delivery_plans_outside_agent_cycle(self):
        create = git_mutation_plan.create_pr(
            head="work/operations/example",
            base="main",
            head_sha="1" * 40,
            title="Delivery candidate",
            body_sha256="2" * 64,
            control_branch="main",
        )
        merge = git_mutation_plan.merge_pr(
            pr_number=77,
            head_sha="1" * 40,
            base="main",
            control_branch="main",
        )

        self.assertEqual(create["riskClass"], "pr-write")
        self.assertEqual(merge["riskClass"], "integration-write")
        self.assertEqual(
            merge["preconditions"],
            {
                "expectedHeadSha": "1" * 40,
                "expectedBase": "main",
                "requiredGatesMustBeGreen": True,
            },
        )
        self.assertEqual(
            merge["readback"],
            {
                "kind": "merged-pr",
                "prNumber": 77,
                "expectedHeadSha": "1" * 40,
                "expectedBase": "main",
            },
        )

        for plan in (create, merge):
            with self.subTest(operation=plan["operation"]):
                with self.assertRaisesRegex(
                    RuntimeError, "AGENT_CYCLE_RESOURCE_GIT_OPERATION_UNSUPPORTED"
                ):
                    agent_cycle_resources.resources_from_git_plan(plan)


if __name__ == "__main__":
    unittest.main()
