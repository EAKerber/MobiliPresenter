from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import unittest

from tools import hosted_agent_cycle as hosted
from tools import hosted_cycle_frontier, hosted_cycle_reentry
from tools.canonical import stable_hash

FIXTURE_PATH = Path(__file__).with_name("test_hosted_cycle_reentry_r0.py")
SPEC = importlib.util.spec_from_file_location("hosted_cycle_reentry_r0_fixtures", FIXTURE_PATH)
fixtures = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(fixtures)


def _pass_cycle(
    *,
    request_id: str,
    begin_id: int,
    begin_result_id: int,
    run_id: int,
    source_hex: str,
    close_request_id: str,
    close_id: int,
    close_result_id: int,
    close_run_id: int,
) -> tuple[list[dict], dict]:
    begin_request, begin_result_comment, begin_result = fixtures._begin_pair(
        request_id=request_id,
        begin_id=begin_id,
        result_id=begin_result_id,
        run_id=run_id,
        source_hex=source_hex,
    )
    close = fixtures._close_command(begin_result["handle"], close_request_id)
    close_request = fixtures._owner_comment(hosted.REQUEST_MARKER_V02, close, close_id)
    close_result = fixtures._bot_comment(
        fixtures._close_pass(close, begin_result, run_id=close_run_id),
        close_result_id,
    )
    return [begin_request, begin_result_comment, close_request, close_result], begin_result


class HostedCycleFrontierS1Tests(unittest.TestCase):
    def test_pass_then_open_is_proven_single_active_frontier(self):
        closed, closed_result = _pass_cycle(
            request_id="begin-a",
            begin_id=1001,
            begin_result_id=1101,
            run_id=3001,
            source_hex="b",
            close_request_id="close-a",
            close_id=1201,
            close_result_id=1301,
            close_run_id=4001,
        )
        open_request, open_result_comment, open_result = fixtures._begin_pair(
            request_id="begin-b",
            begin_id=1401,
            result_id=1501,
            run_id=3002,
            source_hex="d",
        )
        result = fixtures._inspect([*closed, open_request, open_result_comment])

        self.assertEqual("HostedCycleReentryInspection 0.2", result["schemaVersion"])
        self.assertEqual("CLEAN_REENTRY", result["state"])
        self.assertEqual("RESUME_EXACT_CYCLE", result["nextSafeAction"])
        self.assertEqual(open_result["cycleInstanceId"], result["targetCycle"]["cycleInstanceId"])
        frontier = result["cycleFrontier"]
        self.assertEqual("SINGLE", frontier["state"])
        self.assertEqual([closed_result["cycleInstanceId"]], frontier["terminalCycleIds"])
        self.assertEqual([open_result["cycleInstanceId"]], frontier["activeCycleIds"])
        self.assertEqual(1, len(frontier["successionEvidence"]))
        self.assertTrue(frontier["successionEvidence"][0]["ordered"])
        self.assertEqual(1301, frontier["successionEvidence"][0]["terminalResultCommentId"])
        self.assertEqual(1401, frontier["successionEvidence"][0]["activeBeginCommentId"])

    def test_two_passed_cycles_and_done_work_are_terminal_history_not_ambiguity(self):
        a, a_result = _pass_cycle(
            request_id="begin-a",
            begin_id=1001,
            begin_result_id=1101,
            run_id=3001,
            source_hex="b",
            close_request_id="close-a",
            close_id=1201,
            close_result_id=1301,
            close_run_id=4001,
        )
        b, b_result = _pass_cycle(
            request_id="begin-b",
            begin_id=1401,
            begin_result_id=1501,
            run_id=3002,
            source_hex="d",
            close_request_id="close-b",
            close_id=1601,
            close_result_id=1701,
            close_run_id=4002,
        )
        result = fixtures._inspect([*a, *b], status="DONE")

        self.assertEqual("NO_REENTRY_REQUIRED", result["state"])
        self.assertEqual("NONE", result["nextSafeAction"])
        self.assertEqual("NONE", result["cycleFrontier"]["state"])
        self.assertEqual(
            sorted([a_result["cycleInstanceId"], b_result["cycleInstanceId"]]),
            result["cycleFrontier"]["terminalCycleIds"],
        )
        self.assertEqual([], result["cycleFrontier"]["activeCycleIds"])

    def test_two_passed_cycles_and_active_work_can_begin_new_cycle(self):
        a, _ = _pass_cycle(
            request_id="begin-a",
            begin_id=1001,
            begin_result_id=1101,
            run_id=3001,
            source_hex="b",
            close_request_id="close-a",
            close_id=1201,
            close_result_id=1301,
            close_run_id=4001,
        )
        b, _ = _pass_cycle(
            request_id="begin-b",
            begin_id=1401,
            begin_result_id=1501,
            run_id=3002,
            source_hex="d",
            close_request_id="close-b",
            close_id=1601,
            close_result_id=1701,
            close_run_id=4002,
        )
        result = fixtures._inspect([*a, *b])
        self.assertEqual("CLEAN_REENTRY", result["state"])
        self.assertEqual("BEGIN_NEW_CYCLE", result["nextSafeAction"])
        self.assertEqual(["PREVIOUS_CYCLE_CLOSED"], result["reasonCodes"])
        self.assertEqual("NONE", result["cycleFrontier"]["state"])

    def test_two_open_cycles_are_concurrent_active_frontier(self):
        a = fixtures._begin_pair(
            request_id="begin-a", begin_id=1001, result_id=1101, run_id=3001, source_hex="b"
        )
        b = fixtures._begin_pair(
            request_id="begin-b", begin_id=1201, result_id=1301, run_id=3002, source_hex="d"
        )
        result = fixtures._inspect([a[0], a[1], b[0], b[1]])

        self.assertEqual("INSUFFICIENT_OBSERVATION", result["state"])
        self.assertEqual("OBSERVE", result["nextSafeAction"])
        self.assertEqual(["HOSTED_CYCLE_LINEAGE_AMBIGUOUS"], result["reasonCodes"])
        self.assertEqual("CONCURRENT", result["cycleFrontier"]["state"])
        self.assertEqual(
            sorted([a[2]["cycleInstanceId"], b[2]["cycleInstanceId"]]),
            result["cycleFrontier"]["activeCycleIds"],
        )

    def test_open_cycle_started_before_previous_pass_is_not_assumed_successor(self):
        closed, closed_result = _pass_cycle(
            request_id="begin-a",
            begin_id=1001,
            begin_result_id=1101,
            run_id=3001,
            source_hex="b",
            close_request_id="close-a",
            close_id=1301,
            close_result_id=1501,
            close_run_id=4001,
        )
        open_request, open_result_comment, open_result = fixtures._begin_pair(
            request_id="begin-b",
            begin_id=1401,
            result_id=1601,
            run_id=3002,
            source_hex="d",
        )
        result = fixtures._inspect([*closed, open_request, open_result_comment])

        self.assertEqual("INSUFFICIENT_OBSERVATION", result["state"])
        self.assertEqual("OBSERVE", result["nextSafeAction"])
        self.assertEqual(["HOSTED_CYCLE_SUCCESSION_UNPROVEN"], result["reasonCodes"])
        frontier = result["cycleFrontier"]
        self.assertEqual("SUCCESSION_UNPROVEN", frontier["state"])
        self.assertEqual([closed_result["cycleInstanceId"]], frontier["terminalCycleIds"])
        self.assertEqual([open_result["cycleInstanceId"]], frontier["activeCycleIds"])
        self.assertFalse(frontier["successionEvidence"][0]["ordered"])

    def test_pending_begin_after_terminal_history_remains_insufficient_observation(self):
        closed, _ = _pass_cycle(
            request_id="begin-a",
            begin_id=1001,
            begin_result_id=1101,
            run_id=3001,
            source_hex="b",
            close_request_id="close-a",
            close_id=1201,
            close_result_id=1301,
            close_run_id=4001,
        )
        pending = fixtures._owner_comment(
            hosted.REQUEST_MARKER_V03,
            fixtures._begin_command("begin-pending"),
            1401,
        )
        result = fixtures._inspect([*closed, pending])
        self.assertEqual("INSUFFICIENT_OBSERVATION", result["state"])
        self.assertEqual(["HOSTED_BEGIN_PENDING"], result["reasonCodes"])

    def test_rehashed_frontier_cannot_forge_succession_evidence(self):
        closed, _ = _pass_cycle(
            request_id="begin-a",
            begin_id=1001,
            begin_result_id=1101,
            run_id=3001,
            source_hex="b",
            close_request_id="close-a",
            close_id=1201,
            close_result_id=1301,
            close_run_id=4001,
        )
        open_request, open_result_comment, _ = fixtures._begin_pair(
            request_id="begin-b",
            begin_id=1401,
            result_id=1501,
            run_id=3002,
            source_hex="d",
        )
        result = fixtures._inspect([*closed, open_request, open_result_comment])
        tampered = copy.deepcopy(result)
        evidence = tampered["cycleFrontier"]["successionEvidence"][0]
        evidence["activeBeginCommentId"] = 1450
        evidence["ordered"] = True
        frontier_core = {
            key: copy.deepcopy(value)
            for key, value in tampered["cycleFrontier"].items()
            if key != "frontierHash"
        }
        tampered["cycleFrontier"]["frontierHash"] = stable_hash(frontier_core)
        inspection_core = {
            key: copy.deepcopy(value)
            for key, value in tampered.items()
            if key != "inspectionHash"
        }
        tampered["inspectionHash"] = stable_hash(inspection_core)

        with self.assertRaisesRegex(RuntimeError, "FRONTIER_EVIDENCE_MISMATCH"):
            hosted_cycle_reentry.validate_reentry(tampered)

    def test_frontier_validator_rejects_rehashed_false_order(self):
        open_cycle = fixtures._begin_pair()[2]
        outcomes = [
            {
                "cycleInstanceId": open_cycle["cycleInstanceId"],
                "beginRequestCommentId": 1401,
                "state": "OPEN",
                "closeRequestCommentId": None,
                "resultCommentIds": [],
                "resultHash": None,
                "reasonCodes": [],
            }
        ]
        frontier = hosted_cycle_frontier.build_frontier(outcomes)
        self.assertEqual("SINGLE", frontier["state"])
        self.assertEqual(frontier, hosted_cycle_frontier.validate_frontier(frontier))


if __name__ == "__main__":
    unittest.main()
