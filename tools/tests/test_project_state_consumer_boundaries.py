import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
LEGACY_CONSUMERS=[
    "tools/agent.py",
    "tools/project_sensors.py",
    "tools/project_machine.py",
    "tools/project_coherence.py",
    "tools/maintenance_inspect.py",
    "tools/integration_reconcile.py",
    "tools/project_state_apply.py",
    "tools/prune_plan.py",
]
FORBIDDEN_LEGACY=(
    '"productInvariants"','"publishedBranch"','"preserveBranches"','"artifactSha256"',
    '"constraints"','"toolboxPhase"','"canonicalState"','["plan"]',
)
EXECUTION_TOKENS=(
    'get("activeDevelopmentBranch")','["activeDevelopmentBranch"]',
    'get("developmentPrNumber")','["developmentPrNumber"]',
    '["development"].get("prNumber")','["development"]["prNumber"]',
    '["development"].get("blockers")','["development"]["blockers"]',
)


class ProjectStateConsumerBoundaryTests(unittest.TestCase):
    def test_operational_consumers_do_not_read_removed_or_shadow_fields(self):
        violations=[]
        for relative in LEGACY_CONSUMERS:
            text=(ROOT/relative).read_text(encoding="utf-8")
            for token in FORBIDDEN_LEGACY+EXECUTION_TOKENS:
                if token in text:
                    violations.append(f"{relative}:{token}")
        self.assertEqual(violations,[])

    def test_prune_execution_protection_is_work_backed(self):
        text=(ROOT/"tools/prune_plan.py").read_text(encoding="utf-8")
        self.assertIn('reasons.append("active-work")',text)
        self.assertIn('GitHubContinuationAuthority',text)
        self.assertIn('work_graph.active_execution_bindings',text)
        self.assertNotIn('active-development',text)

    def test_live_authority_and_canonical_schema_are_v2_only(self):
        state=(ROOT/"ops/state/project.json").read_text(encoding="utf-8")
        schema=(ROOT/"ops/schemas/project-state.schema.json").read_text(encoding="utf-8")
        self.assertIn('"schemaVersion": "ProjectState 2.0"',state)
        self.assertIn('"ProjectState 2.0"',schema)
        self.assertNotIn('"schemaVersion": "ProjectState 1.0"',state)
        self.assertFalse((ROOT/"ops/schemas/project-state-2.0.schema.json").exists())
        self.assertFalse((ROOT/"ops/migrations/project-state-2.0.json").exists())

    def test_runtime_compatibility_helpers_are_retired(self):
        text=(ROOT/"tools/project_state.py").read_text(encoding="utf-8")
        for token in (
            "validate_v1","validate_v2","validate_compatible","migrate_v1_to_v2",
            "MIGRATION_MAP_PATH","CANDIDATE_V2_SCHEMA_PATH",
        ):
            self.assertNotIn(token,text)
        self.assertNotIn("validate_state_shape",(ROOT/"tools/agent.py").read_text(encoding="utf-8"))


if __name__=="__main__":
    unittest.main()
