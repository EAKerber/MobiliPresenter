from __future__ import annotations

import json
import unittest

from tools import capability_gates
from tools.semantics.contracts import check_capability_gates_contract
from tools.semantics.registry import ROOT


class SemanticContractTests(unittest.TestCase):
    def test_capability_contract_is_conformant(self):
        self.assertEqual([], check_capability_gates_contract())

    def test_real_peer_recovery_is_runtime_valid_and_uses_supervisor_participation(self):
        path = ROOT / "ops" / "capabilities" / "peer-recovery.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual("isolated", value["supervisorParticipation"])
        self.assertEqual([], capability_gates.validate_capability(value, expected_id="peer-recovery"))

    def test_structural_schema_contains_runtime_optional_field(self):
        path = ROOT / "ops" / "schemas" / "capability-gates.schema.json"
        schema = json.loads(path.read_text(encoding="utf-8"))
        self.assertIn("supervisorParticipation", schema["properties"])
        self.assertNotIn("supervisorParticipation", schema["required"])
        self.assertEqual(set(capability_gates.SUPERVISOR_PARTICIPATION), set(schema["properties"]["supervisorParticipation"]["enum"]))


if __name__ == "__main__":
    unittest.main()
