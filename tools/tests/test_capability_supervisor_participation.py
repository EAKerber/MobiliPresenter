import copy
import unittest
from tools import capability_evidence as evidence
from tools import capability_transition as transition


def capability():
    return {
        "schemaVersion": "CapabilityGates 0.1",
        "id": "example-capability",
        "policy": "experimental",
        "gates": {
            "backlog": [{"id": "runtime-shadow", "test": "Run shadow probe."}],
            "next": ["runtime-shadow"],
        },
        "roundsWithoutActiveGates": 0,
        "maxRoundsWithoutActiveGates": 3,
        "deferReason": None,
    }


class SupervisorParticipationTests(unittest.TestCase):
    def test_transition_is_deterministic_and_replayable(self):
        before = capability()
        original = copy.deepcopy(before)
        first = transition.set_supervisor_participation(before, "isolated")
        second = transition.set_supervisor_participation(copy.deepcopy(before), "isolated")
        self.assertEqual(before, original)
        self.assertEqual(first["planHash"], second["planHash"])
        self.assertEqual(first["after"]["supervisorParticipation"], "isolated")
        record = evidence.record(first)
        rebuilt = evidence.rebuild(before, record)
        self.assertEqual(rebuilt["planHash"], first["planHash"])
        self.assertEqual(rebuilt["afterStateHash"], first["afterStateHash"])

    def test_transition_can_activate_after_isolation(self):
        isolated = transition.set_supervisor_participation(capability(), "isolated")["after"]
        active = transition.set_supervisor_participation(isolated, "active")
        self.assertEqual(active["after"]["supervisorParticipation"], "active")

    def test_unchanged_transition_is_rejected(self):
        isolated = transition.set_supervisor_participation(capability(), "isolated")["after"]
        with self.assertRaisesRegex(RuntimeError, "CAPABILITY_SUPERVISOR_PARTICIPATION_UNCHANGED"):
            transition.set_supervisor_participation(isolated, "isolated")


if __name__ == "__main__":
    unittest.main()
