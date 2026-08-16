import json
import unittest
from pathlib import Path

from tools import project_state
from tools import transition_protocol as protocol

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "ops" / "evidence" / "project-state" / "project-state-2.0-migration.json"


class ProjectStateMigrationEvidenceTests(unittest.TestCase):
    def test_verified_migration_evidence_matches_current_authority(self):
        evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        state = project_state.load_state()
        self.assertEqual(evidence["schemaVersion"], "ProjectStateMigrationEvidence 0.1")
        self.assertEqual(evidence["fromSchemaVersion"], "ProjectState 1.0")
        self.assertEqual(evidence["toSchemaVersion"], "ProjectState 2.0")
        self.assertEqual(evidence["migrationMap"]["constraintCount"], 32)
        self.assertEqual(evidence["migrationMap"]["unresolvedCount"], 0)
        self.assertTrue(evidence["publicationParity"]["all"])
        self.assertTrue(evidence["protectedBranchesParity"])
        plan = evidence["transitionPlan"]
        receipt = evidence["transitionReceipt"]
        protocol.validate_plan(plan)
        protocol.validate_receipt(receipt, plan)
        self.assertTrue(receipt["verified"])
        self.assertEqual(protocol.state_hash(state), plan["afterStateHash"])
        self.assertEqual(receipt["readbackStateHash"], plan["afterStateHash"])
        self.assertEqual(project_state.validate_current(state), [])


if __name__ == "__main__":
    unittest.main()
