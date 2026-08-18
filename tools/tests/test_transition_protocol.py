import copy
import unittest

from tools import transition_protocol as protocol


class TransitionProtocolTests(unittest.TestCase):
    def plan(self):
        before = {"value": 1}
        candidate = {"value": 2}
        return protocol.build_plan(
            domain="test-domain",
            action="advance",
            subject={"kind": "test-subject", "id": "subject-a"},
            authority={"kind": "repository-file", "locator": {"path": "ops/test.json"}},
            before=before,
            candidate=candidate,
            intent={"value": 2},
        )

    def test_plan_hash_is_deterministic_and_intent_sensitive(self):
        first = self.plan()
        second = self.plan()
        self.assertEqual(first, second)
        changed = protocol.build_plan(
            domain="test-domain",
            action="advance",
            subject={"kind": "test-subject", "id": "subject-a"},
            authority={"kind": "repository-file", "locator": {"path": "ops/test.json"}},
            before={"value": 1},
            candidate={"value": 3},
            intent={"value": 3},
        )
        self.assertNotEqual(first["planHash"], changed["planHash"])
        self.assertNotEqual(first["afterStateHash"], changed["afterStateHash"])

    def test_validate_rejects_candidate_and_plan_hash_tampering(self):
        plan = self.plan()
        bad = copy.deepcopy(plan)
        bad["candidate"]["value"] = 99
        with self.assertRaisesRegex(RuntimeError, "TRANSITION_CANDIDATE_HASH_MISMATCH"):
            protocol.validate_plan(bad)
        bad = copy.deepcopy(plan)
        bad["intent"]["value"] = 99
        with self.assertRaisesRegex(RuntimeError, "TRANSITION_PLAN_HASH_MISMATCH"):
            protocol.validate_plan(bad)

    def test_expected_plan_and_before_state_are_fail_closed(self):
        plan = self.plan()
        with self.assertRaisesRegex(RuntimeError, "TRANSITION_EXPECTED_PLAN_REQUIRED"):
            protocol.require_expected_plan(plan, None)
        with self.assertRaisesRegex(RuntimeError, "TRANSITION_EXPECTED_PLAN_MISMATCH"):
            protocol.require_expected_plan(plan, "0" * 64)
        with self.assertRaisesRegex(RuntimeError, "TRANSITION_PLAN_STALE"):
            protocol.verify_before_state(plan, {"value": 9})
        protocol.require_expected_plan(plan, plan["planHash"])
        protocol.verify_before_state(plan, {"value": 1})

    def test_receipt_requires_exact_readback_and_is_deterministic(self):
        plan = self.plan()
        with self.assertRaisesRegex(RuntimeError, "TRANSITION_READBACK_MISMATCH"):
            protocol.build_receipt(plan, {"value": 9})
        first = protocol.build_receipt(plan, {"value": 2})
        second = protocol.build_receipt(plan, {"value": 2})
        self.assertEqual(first, second)
        self.assertTrue(first["verified"])
        self.assertEqual(first["afterStateHash"], first["readbackStateHash"])
        protocol.validate_receipt(first, plan)

    def test_receipt_tampering_is_rejected(self):
        plan = self.plan()
        receipt = protocol.build_receipt(plan, {"value": 2})
        bad = copy.deepcopy(receipt)
        bad["verified"] = False
        with self.assertRaisesRegex(RuntimeError, "TRANSITION_RECEIPT_NOT_VERIFIED"):
            protocol.validate_receipt(bad, plan)
        bad = copy.deepcopy(receipt)
        bad["authorityRevision"] = "changed"
        with self.assertRaisesRegex(RuntimeError, "TRANSITION_RECEIPT_HASH_MISMATCH"):
            protocol.validate_receipt(bad, plan)

    def test_authority_locator_rejects_values_outside_structural_contract(self):
        for locator in ({"path": ""}, {"attempt": True}, {"nested": {"x": 1}}):
            with self.subTest(locator=locator), self.assertRaisesRegex(RuntimeError, "TRANSITION_AUTHORITY_INVALID"):
                protocol.build_plan(
                    domain="test-domain",
                    action="advance",
                    subject={"kind": "test-subject", "id": "subject-a"},
                    authority={"kind": "repository-file", "locator": locator},
                    before={"value": 1},
                    candidate={"value": 2},
                    intent={"value": 2},
                )

    def test_receipt_authority_revision_is_null_or_nonempty(self):
        plan = self.plan()
        with self.assertRaisesRegex(RuntimeError, "TRANSITION_AUTHORITY_REVISION_INVALID"):
            protocol.build_receipt(plan, {"value": 2}, authority_revision="")
        receipt = protocol.build_receipt(plan, {"value": 2}, authority_revision="rev-1")
        self.assertEqual("rev-1", receipt["authorityRevision"])
        protocol.validate_receipt(receipt, plan)


if __name__ == "__main__":
    unittest.main()
