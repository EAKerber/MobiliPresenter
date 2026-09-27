import copy
import unittest

from tools import hosted_cycle_own_work_delta_recovery as recovery


BASE = {
    "id": "e5i-own-work-multi-pr-chain-recovery",
    "workerId": "manager-gitops-chat",
    "status": "READY",
    "remaining": ["qualify-live-two-pr-chain"],
    "nextAction": "Qualify the live two-PR chain.",
    "branch": "work/operations/e5i-own-work-multi-pr-chain-recovery",
    "prNumber": 359,
    "dependsOn": [],
    "stateHash": "a" * 64,
}


def terminal_unbind():
    after = copy.deepcopy(BASE)
    after["prNumber"] = None
    after["stateHash"] = "b" * 64
    return after


class OwnWorkBindingTransitionTests(unittest.TestCase):
    def test_exact_work_state_is_compatible(self) -> None:
        self.assertTrue(recovery._work_state_compatible(BASE, copy.deepcopy(BASE)))

    def test_terminal_pr_unbind_with_derived_state_hash_is_compatible(self) -> None:
        self.assertTrue(recovery._work_state_compatible(BASE, terminal_unbind()))

    def test_rebinding_to_another_pr_is_rejected(self) -> None:
        after = copy.deepcopy(BASE)
        after["prNumber"] = 360
        after["stateHash"] = "b" * 64
        self.assertFalse(recovery._work_state_compatible(BASE, after))

    def test_binding_from_none_is_rejected(self) -> None:
        before = copy.deepcopy(BASE)
        before["prNumber"] = None
        before["stateHash"] = "b" * 64
        after = copy.deepcopy(before)
        after["prNumber"] = 360
        after["stateHash"] = "c" * 64
        self.assertFalse(recovery._work_state_compatible(before, after))

    def test_other_work_mutation_still_fails_closed(self) -> None:
        after = terminal_unbind()
        after["status"] = "DONE"
        self.assertFalse(recovery._work_state_compatible(BASE, after))

    def test_unbind_without_derived_state_hash_change_is_rejected(self) -> None:
        after = copy.deepcopy(BASE)
        after["prNumber"] = None
        self.assertFalse(recovery._work_state_compatible(BASE, after))


if __name__ == "__main__":
    unittest.main()
