from __future__ import annotations

import unittest

from tools import agent_cycle_turnover as turnover


def readiness(candidates: list[str], action: str = "SELECT_INTENT") -> dict:
    return {
        "nextSafeAction": {
            "action": action,
            "candidateIntents": candidates,
        }
    }


def reentry(action: str) -> dict:
    return {"nextSafeAction": action}


class AgentCycleTurnoverTests(unittest.TestCase):
    def test_unique_candidate_releases_active_ownership_first(self) -> None:
        value = turnover.build_projection(
            work_id="work-1",
            current_intent="governed-mutation",
            readiness=readiness(["inspect-and-plan"]),
            reentry=reentry("RESUME_EXACT_CYCLE"),
            write_lifecycle_state="ACTIVE",
        )
        self.assertEqual(value["targetIntent"], "inspect-and-plan")
        self.assertEqual(value["action"], "RELEASE_OWNERSHIP")
        self.assertTrue(value["readOnly"])
        self.assertFalse(value["authorizesMutation"])

    def test_release_completion_advances_to_close_without_persisted_turnover_state(self) -> None:
        value = turnover.build_projection(
            work_id="work-1",
            current_intent="governed-mutation",
            target_intent="inspect-and-plan",
            readiness=readiness(["inspect-and-plan"]),
            reentry=reentry("RESUME_EXACT_CYCLE"),
            write_lifecycle_state="RELEASED",
        )
        self.assertEqual(value["action"], "CLOSE_AGENT_CYCLE")

    def test_closed_cycle_can_begin_target_intent_after_process_restart(self) -> None:
        value = turnover.build_projection(
            work_id="work-1",
            current_intent=None,
            target_intent="inspect-and-plan",
            readiness=None,
            reentry=reentry("BEGIN_NEW_CYCLE"),
            write_lifecycle_state="NONE",
        )
        self.assertEqual(value["action"], "BEGIN_AGENT_CYCLE")
        self.assertEqual(value["targetIntent"], "inspect-and-plan")

    def test_ambiguous_candidate_intents_are_never_chosen_automatically(self) -> None:
        value = turnover.build_projection(
            work_id="work-1",
            current_intent="bootstrap-discovery",
            readiness=readiness(["governed-mutation", "inspect-and-plan"]),
            reentry=reentry("RESUME_EXACT_CYCLE"),
            write_lifecycle_state="NONE",
        )
        self.assertEqual(value["action"], "SELECT_INTENT")
        self.assertIsNone(value["targetIntent"])

    def test_explicit_admissible_target_resolves_ambiguity(self) -> None:
        value = turnover.build_projection(
            work_id="work-1",
            current_intent="bootstrap-discovery",
            target_intent="inspect-and-plan",
            readiness=readiness(["governed-mutation", "inspect-and-plan"]),
            reentry=reentry("RESUME_EXACT_CYCLE"),
            write_lifecycle_state="NONE",
        )
        self.assertEqual(value["action"], "CLOSE_AGENT_CYCLE")

    def test_explicit_non_candidate_target_fails_closed(self) -> None:
        value = turnover.build_projection(
            work_id="work-1",
            current_intent="governed-mutation",
            target_intent="bootstrap-discovery",
            readiness=readiness(["inspect-and-plan"]),
            reentry=reentry("RESUME_EXACT_CYCLE"),
            write_lifecycle_state="NONE",
        )
        self.assertEqual(value["action"], "BLOCKED")
        self.assertIn("TARGET_INTENT_NOT_ADMISSIBLE", value["reasonCodes"])

    def test_unknown_write_lifecycle_fails_closed(self) -> None:
        value = turnover.build_projection(
            work_id="work-1",
            current_intent="governed-mutation",
            readiness=readiness(["inspect-and-plan"]),
            reentry=reentry("RESUME_EXACT_CYCLE"),
            write_lifecycle_state="UNKNOWN",
        )
        self.assertEqual(value["action"], "BLOCKED")
        self.assertEqual(value["reasonCodes"], ["WRITE_LIFECYCLE_UNKNOWN"])

    def test_non_select_intent_readiness_does_not_trigger_turnover(self) -> None:
        value = turnover.build_projection(
            work_id="work-1",
            current_intent="inspect-and-plan",
            readiness=readiness([], action="PLAN_TOOL"),
            reentry=reentry("RESUME_EXACT_CYCLE"),
            write_lifecycle_state="NONE",
        )
        self.assertEqual(value["action"], "NO_TURNOVER")

    def test_executor_invokes_exactly_one_existing_primitive(self) -> None:
        calls: list[tuple[str, dict]] = []

        projection = turnover.build_projection(
            work_id="work-1",
            current_intent="governed-mutation",
            readiness=readiness(["inspect-and-plan"]),
            reentry=reentry("RESUME_EXACT_CYCLE"),
            write_lifecycle_state="ACTIVE",
        )
        result = turnover.execute_one(
            projection,
            release_ownership=lambda payload: calls.append(("release", payload)) or {"ok": True},
            close_cycle=lambda payload: calls.append(("close", payload)) or {"ok": True},
            begin_cycle=lambda payload: calls.append(("begin", payload)) or {"ok": True},
        )
        self.assertTrue(result["submitted"])
        self.assertEqual([name for name, _ in calls], ["release"])
        self.assertEqual(calls[0][1]["workRef"], {"workId": "work-1"})
        self.assertEqual(calls[0][1]["targetIntent"], "inspect-and-plan")

    def test_projection_contains_no_protocol_or_lease_identity(self) -> None:
        value = turnover.build_projection(
            work_id="work-1",
            current_intent="governed-mutation",
            readiness=readiness(["inspect-and-plan"]),
            reentry=reentry("RESUME_EXACT_CYCLE"),
            write_lifecycle_state="ACTIVE",
        )
        text = repr(value)
        for forbidden in (
            "issueNumber",
            "commentId",
            "leaseId",
            "bindingHash",
            "cycleInstanceId",
            "protocolVersion",
        ):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
