import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONSUMERS = [
    "tools/agent.py",
    "tools/project_sensors.py",
    "tools/project_machine.py",
    "tools/project_coherence.py",
    "tools/prune_plan.py",
    "tools/maintenance_inspect.py",
]
FORBIDDEN = [
    '"productInvariants"',
    '"publishedBranch"',
    '"preserveBranches"',
    '"artifactSha256"',
    '"constraints"',
    '"toolboxPhase"',
    '"canonicalState"',
    '["plan"]',
]


class ProjectStateConsumerBoundaryTests(unittest.TestCase):
    def test_migrated_consumers_do_not_read_fields_scheduled_for_removal(self):
        violations=[]
        for relative in CONSUMERS:
            text=(ROOT/relative).read_text(encoding="utf-8")
            for token in FORBIDDEN:
                if token in text:
                    violations.append(f"{relative}:{token}")
        self.assertEqual(violations, [])

    def test_live_authority_and_canonical_schema_remain_v1_during_m4a(self):
        state=(ROOT/"ops/state/project.json").read_text(encoding="utf-8")
        schema=(ROOT/"ops/schemas/project-state.schema.json").read_text(encoding="utf-8")
        self.assertIn('"schemaVersion": "ProjectState 1.0"', state)
        self.assertIn('"ProjectState 1.0"', schema)
        self.assertNotIn('"schemaVersion": "ProjectState 2.0"', state)


if __name__ == "__main__":
    unittest.main()
