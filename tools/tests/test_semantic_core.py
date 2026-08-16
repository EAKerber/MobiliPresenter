from __future__ import annotations

import unittest

from tools.semantics.artifacts import ARTIFACT_KINDS, require_artifact_kind
from tools.semantics.identity import RoleId, SessionId, WorkerId
from tools.semantics.observation import ObservationStatus


class SemanticCoreTests(unittest.TestCase):
    def test_identity_types_are_distinct_even_with_same_literal(self):
        role = RoleId("manager-gitops")
        worker = WorkerId("manager-gitops")
        session = SessionId("manager-gitops")
        self.assertNotEqual(type(role), type(worker))
        self.assertNotEqual(type(worker), type(session))
        self.assertEqual("manager-gitops", str(role))

    def test_invalid_identity_fails(self):
        with self.assertRaises(RuntimeError):
            WorkerId("Manager GitOps A")

    def test_observation_status_is_closed_vocabulary(self):
        self.assertEqual(ObservationStatus.PASS, ObservationStatus.parse("PASS"))
        self.assertEqual(ObservationStatus.UNKNOWN, ObservationStatus.parse("UNKNOWN"))
        self.assertEqual(ObservationStatus.FAIL, ObservationStatus.parse("FAIL"))
        with self.assertRaisesRegex(RuntimeError, "OBSERVATION_STATUS_INVALID"):
            ObservationStatus.parse("PENDING")

    def test_artifact_taxonomy_is_explicit(self):
        expected = {"inspection", "recommendation", "routing-plan", "transition-plan", "sanitization-plan", "receipt"}
        self.assertEqual(expected, set(ARTIFACT_KINDS))
        self.assertEqual("transition-plan", require_artifact_kind("transition-plan"))
        with self.assertRaisesRegex(RuntimeError, "SEMANTIC_ARTIFACT_KIND_INVALID"):
            require_artifact_kind("plan")


if __name__ == "__main__":
    unittest.main()
