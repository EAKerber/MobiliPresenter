import copy
import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "capability_gates.py"
spec = importlib.util.spec_from_file_location("capability_gates_tool", MODULE_PATH)
capability_gates = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(capability_gates)


class CapabilityGates01Tests(unittest.TestCase):
    def base_capability(self):
        return {
            "schemaVersion": "CapabilityGates 0.1",
            "id": "example-capability",
            "policy": "experimental",
            "gates": {
                "backlog": [
                    {"id": "rollback", "test": "Prove rollback."},
                    {"id": "second-agent", "test": "Exercise with a second independent agent."},
                ],
                "next": ["rollback"],
            },
            "roundsWithoutActiveGates": 0,
            "maxRoundsWithoutActiveGates": 3,
            "deferReason": None,
        }

    def test_schema_accepts_active_gate(self):
        self.assertEqual(capability_gates.validate_capability(self.base_capability()), [])

    def test_empty_next_is_deliberately_valid(self):
        value = self.base_capability()
        value["gates"]["next"] = []
        value["roundsWithoutActiveGates"] = 1
        value["deferReason"] = "Waiting for a representative cross-worker case."
        self.assertEqual(capability_gates.validate_capability(value), [])

    def test_active_gate_requires_zero_empty_rounds(self):
        value = self.base_capability()
        value["roundsWithoutActiveGates"] = 1
        errors = capability_gates.validate_capability(value)
        self.assertIn("CAPABILITY_ACTIVE_GATES_REQUIRE_ZERO_EMPTY_ROUNDS", errors)

    def test_next_gate_must_exist_in_backlog(self):
        value = self.base_capability()
        value["gates"]["next"] = ["unknown-gate"]
        errors = capability_gates.validate_capability(value)
        self.assertIn("CAPABILITY_NEXT_GATE_NOT_IN_BACKLOG", errors)

    def test_review_plan_tests_explicit_next_gates(self):
        plan = capability_gates.build_review_plan(self.base_capability())
        self.assertEqual(plan["action"], "TEST_NEXT_GATES")
        self.assertTrue(plan["readOnly"])

    def test_review_plan_rechecks_empty_round_before_limit(self):
        value = self.base_capability()
        value["gates"]["next"] = []
        value["roundsWithoutActiveGates"] = 2
        value["deferReason"] = "Waiting for a representative cross-worker case."
        plan = capability_gates.build_review_plan(value)
        self.assertEqual(plan["action"], "REVIEW_EMPTY_ROUND")

    def test_review_plan_forces_stronger_review_at_limit(self):
        value = self.base_capability()
        value["gates"]["next"] = []
        value["roundsWithoutActiveGates"] = 3
        value["deferReason"] = "Waiting for a representative cross-worker case."
        plan = capability_gates.build_review_plan(value)
        self.assertEqual(plan["action"], "REVIEW_EMPTY_LIMIT")

    def test_non_experimental_policy_does_not_enter_experimental_review(self):
        value = self.base_capability()
        value["policy"] = "canonical"
        value["gates"]["next"] = []
        plan = capability_gates.build_review_plan(value)
        self.assertEqual(plan["action"], "NO_EXPERIMENTAL_REVIEW")

    def test_plan_hash_is_stable_and_sensitive(self):
        value = self.base_capability()
        first = capability_gates.build_review_plan(value)
        second = capability_gates.build_review_plan(copy.deepcopy(value))
        self.assertEqual(first["planHash"], second["planHash"])
        changed = copy.deepcopy(value)
        changed["gates"]["next"] = ["second-agent"]
        third = capability_gates.build_review_plan(changed)
        self.assertNotEqual(first["planHash"], third["planHash"])

    def test_repository_pilot_is_discoverable_and_points_to_next_gates(self):
        discovered = {value["id"]: value for value in capability_gates.discover_capabilities()}
        self.assertIn("coordination-leases", discovered)
        pilot = discovered["coordination-leases"]
        self.assertEqual(capability_gates.validate_capability(pilot, expected_id="coordination-leases"), [])
        plan = capability_gates.build_review_plan(pilot)
        self.assertEqual(plan["action"], "TEST_NEXT_GATES")
        self.assertEqual(set(plan["nextGates"]), {"formal-rollback", "official-cli-surface"})


if __name__ == "__main__":
    unittest.main()
