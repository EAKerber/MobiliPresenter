import unittest

from tools import maintenance_inspect, project_machine, routines
from tools.tests.test_project_machine import base_sensors, state


def capability_item(
    *,
    capability_id="experimental-capability",
    review_action="REVIEW_EMPTY_ROUND",
    participation="active",
    next_gates=None,
    rounds=1,
    maximum=3,
):
    return {
        "id": capability_id,
        "policy": "experimental",
        "supervisorParticipation": participation,
        "reviewAction": review_action,
        "nextGates": list(next_gates or []),
        "backlogCount": len(next_gates or []),
        "roundsWithoutActiveGates": rounds,
        "maxRoundsWithoutActiveGates": maximum,
        "deferReason": "waiting for evidence",
        "reviewPlanHash": "a" * 64,
    }


def machine_with(*items):
    sensors = base_sensors()
    sensors["capabilities"]["data"]["items"] = list(items)
    return project_machine.build_inspection(state(), sensors, scope="live")


class RoutineKernelTests(unittest.TestCase):
    def test_current_canonical_capability_state_is_healthy_noop(self):
        machine = project_machine.build_inspection(state(), base_sensors(), scope="live")
        value = routines.build_inspection(machine)
        self.assertEqual(value["status"], "PASS")
        self.assertTrue(value["complete"])
        result = value["results"][0]
        self.assertEqual(result["id"], "capability-deathcircle")
        self.assertFalse(result["applicable"])
        self.assertEqual(result["findings"], [])
        self.assertEqual(routines.validate_inspection(value, machine), value)

    def test_experimental_empty_round_is_detected(self):
        machine = machine_with(capability_item())
        result = routines.evaluate_capability_deathcircle(machine)
        self.assertTrue(result["applicable"])
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["findings"][0]["code"], "CAPABILITY_EMPTY_REVIEW_DUE")
        self.assertTrue(result["findings"][0]["supervisorEligible"])

    def test_deathcircle_limit_is_detected_without_operational_action(self):
        machine = machine_with(
            capability_item(review_action="REVIEW_EMPTY_LIMIT", rounds=3, maximum=3)
        )
        result = routines.evaluate_capability_deathcircle(machine)
        self.assertEqual(result["findings"][0]["code"], "CAPABILITY_EMPTY_LIMIT")
        self.assertNotIn("action", result["findings"][0])

    def test_active_routine_findings_are_translated_only_by_maintenance(self):
        machine = machine_with(
            capability_item(
                capability_id="cap-a",
                review_action="TEST_NEXT_GATES",
                next_gates=["g1"],
                rounds=0,
            )
        )
        routine = routines.build_inspection(machine)
        finding = routine["results"][0]["findings"][0]
        self.assertEqual(finding["code"], "CAPABILITY_GATES_DUE")
        self.assertNotIn("action", finding)
        maintenance = maintenance_inspect.from_inputs(machine, routine)
        translated = [
            item for item in maintenance["findings"] if item["code"] == "CAPABILITY_GATES_DUE"
        ]
        self.assertEqual(len(translated), 1)
        self.assertEqual(translated[0]["action"], "CONTINUE")

    def test_isolated_capability_is_monitored_but_not_supervisor_eligible(self):
        machine = machine_with(
            capability_item(
                capability_id="isolated-cap",
                review_action="REVIEW_EMPTY_LIMIT",
                participation="isolated",
                rounds=3,
                maximum=3,
            )
        )
        routine = routines.build_inspection(machine)
        finding = routine["results"][0]["findings"][0]
        self.assertFalse(finding["supervisorEligible"])
        maintenance = maintenance_inspect.from_inputs(machine, routine)
        self.assertNotIn(
            "CAPABILITY_EMPTY_LIMIT", [item["code"] for item in maintenance["findings"]]
        )
        self.assertEqual(
            maintenance["recommendation"]["reasonCode"], "NEXT_TRANSITION_AVAILABLE"
        )

    def test_routine_exception_becomes_visible_failure(self):
        machine = project_machine.build_inspection(state(), base_sensors(), scope="live")

        def explode(_machine):
            raise RuntimeError("SYNTHETIC_ROUTINE_FAILURE:detail")

        definition = routines.RoutineDefinition(
            id="synthetic-failure",
            required=True,
            input_kind="ProjectMachineInspection",
            evaluator=explode,
        )
        value = routines.build_inspection(machine, catalog=(definition,))
        self.assertEqual(value["status"], "FAIL")
        self.assertFalse(value["complete"])
        self.assertEqual(value["results"][0]["status"], "FAIL")
        self.assertEqual(
            value["results"][0]["findings"][0]["code"], "ROUTINE_EVALUATION_FAILED"
        )


if __name__ == "__main__":
    unittest.main()
