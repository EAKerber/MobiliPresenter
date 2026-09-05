from __future__ import annotations

import copy
import unittest

from tools import (
    maintenance_inspect,
    operational_quiescence,
    project_machine,
    reflection_eligibility,
    routines,
    scheduler_plan,
    scheduler_snapshot,
)
from tools.canonical import stable_hash
from tools.tests.test_maintenance_inspect import machine, sensors, state, work


def pipeline(source, *, readback=None):
    readback = copy.deepcopy(source) if readback is None else readback
    routine = routines.build_inspection(source)
    maintenance = maintenance_inspect.from_inputs(source, routine)
    plan = scheduler_plan.build_plan(maintenance)
    snapshot = scheduler_snapshot.build_snapshot(source, routine, maintenance, plan)
    reflection = reflection_eligibility.build_inspection(
        snapshot,
        source_machine=source,
        routine_inspection=routine,
        readback_machine=readback,
    )
    return routine, snapshot, reflection, readback


def sample(source, sequence, *, readback=None):
    routine, snapshot, reflection, readback = pipeline(source, readback=readback)
    return operational_quiescence.build_sample(
        snapshot=snapshot,
        reflection=reflection,
        source_machine=source,
        routine_inspection=routine,
        readback_machine=readback,
        observation_id=f"github-actions:run-{sequence}:attempt-1",
        sequence=sequence,
    )


class OperationalQuiescenceRQ2Tests(unittest.TestCase):
    def test_reflection_eligible_live_snapshot_produces_eligible_sample(self):
        value = sample(machine(), 101)
        self.assertTrue(value["sampleEligible"])
        self.assertEqual([], value["reasonCodes"])
        self.assertEqual("REFLECTION_ELIGIBLE", value["reflectionStatus"])
        self.assertTrue(value["reflectionEligible"])
        self.assertEqual(value["sourceCriticalHash"], value["readbackCriticalHash"])
        self.assertEqual(value["readbackCriticalHash"], value["baselineHash"])
        self.assertTrue(value["readOnly"])
        self.assertFalse(value["semanticAuthority"])
        self.assertFalse(value["authorizesMutation"])

    def test_legitimate_wait_can_count_as_quiet_sample(self):
        value = sample(machine([work("a", "WAITING")]), 102)
        self.assertTrue(value["sampleEligible"])
        self.assertEqual("LEGITIMATE_WAIT", value["reflectionStatus"])
        self.assertEqual([], value["reasonCodes"])

    def test_priority_operation_resets_sample_eligibility(self):
        value = sample(machine([work("a")]), 103)
        self.assertFalse(value["sampleEligible"])
        self.assertIn("PRIORITY_OPERATION_REQUIRED", value["reasonCodes"])
        self.assertIn("WORK_RUNNABLE", value["reasonCodes"])
        self.assertIsNone(value["baselineHash"])

    def test_unknown_operational_state_is_not_quiet(self):
        item = work("a", branch="work/ui/a", pr=7)
        prs = [
            {
                "number": 7,
                "headRef": "work/ui/a",
                "baseRef": "main",
                "ci": "unknown",
                "ciObserved": False,
            }
        ]
        value = sample(machine([item], prs), 104)
        self.assertFalse(value["sampleEligible"])
        self.assertIn("INSUFFICIENT_OBSERVATION", value["reasonCodes"])
        self.assertIn("WORK_PR_CI_UNKNOWN", value["reasonCodes"])

    def test_coordination_intent_is_incompatible_activity_even_without_work(self):
        raw = sensors()
        raw["coordination"]["data"]["intents"] = [
            {"intentId": "i-1", "scope": {"kind": "branch", "branch": "work/ui/a"}}
        ]
        m = project_machine.build_inspection(state(), raw, scope="live")
        value = sample(m, 105)
        self.assertFalse(value["sampleEligible"])
        self.assertIn("COORDINATION_INTENTS_ACTIVE", value["reasonCodes"])

    def test_pr_ci_change_without_authority_head_change_is_detected_as_intra_sample_drift(self):
        source = machine()
        changed_sensors = sensors(
            prs=[
                {
                    "number": 7,
                    "draft": False,
                    "headRef": "work/operations/test",
                    "headSha": "7" * 40,
                    "baseRef": "main",
                    "ci": "pending",
                    "ciObserved": True,
                }
            ]
        )
        changed = project_machine.build_inspection(state(), changed_sensors, scope="live")
        routine, snapshot, reflection, _ = pipeline(source, readback=changed)
        value = operational_quiescence.build_sample(
            snapshot=snapshot,
            reflection=reflection,
            source_machine=source,
            routine_inspection=routine,
            readback_machine=changed,
            observation_id="github-actions:run-106:attempt-1",
            sequence=106,
        )
        self.assertFalse(value["sampleEligible"])
        self.assertIn("INTRA_SAMPLE_OPERATIONAL_DRIFT", value["reasonCodes"])
        self.assertNotEqual(value["sourceCriticalHash"], value["readbackCriticalHash"])

    def test_terminal_continuation_residue_is_not_activity_by_itself(self):
        value = sample(machine([work("a", "DONE")]), 107)
        self.assertTrue(value["sampleEligible"])
        self.assertEqual([], value["reasonCodes"])

    def test_intrinsic_validation_rejects_rehashed_coordination_tampering(self):
        value = sample(machine(), 108)
        value["sourceFacts"]["coordination"]["leases"] = [{"leaseId": "forged"}]
        value["sourceCriticalHash"] = stable_hash(value["sourceFacts"])
        body = {key: copy.deepcopy(item) for key, item in value.items() if key != "sampleHash"}
        value["sampleHash"] = stable_hash(body)
        with self.assertRaisesRegex(
            RuntimeError, "OPERATIONAL_QUIESCENCE_REASONS_MISMATCH"
        ):
            operational_quiescence.validate_sample(value)

    def test_no_samples_is_healthy_noop(self):
        value = operational_quiescence.evaluate_window([])
        self.assertEqual("NO_SAMPLES", value["status"])
        self.assertFalse(value["windowComplete"])
        self.assertFalse(value["eligible"])
        self.assertFalse(value["invalidated"])
        self.assertEqual(["INSUFFICIENT_SAMPLES"], value["reasonCodes"])

    def test_two_compatible_samples_accumulate_but_do_not_prove_quiescence(self):
        values = [sample(machine(), 201), sample(machine(), 202)]
        result = operational_quiescence.evaluate_window(values)
        self.assertEqual("ACCUMULATING", result["status"])
        self.assertEqual(3, result["windowSize"])
        self.assertFalse(result["windowComplete"])
        self.assertFalse(result["eligible"])
        self.assertEqual(2, len(result["windowSampleHashes"]))

    def test_three_compatible_samples_prove_operational_quiescence(self):
        values = [sample(machine(), 301), sample(machine(), 302), sample(machine(), 303)]
        result = operational_quiescence.evaluate_window(values)
        self.assertEqual("QUIESCENT", result["status"])
        self.assertTrue(result["windowComplete"])
        self.assertTrue(result["eligible"])
        self.assertFalse(result["invalidated"])
        self.assertEqual(["WINDOW_COMPLETE"], result["reasonCodes"])
        self.assertEqual([301, 302, 303], result["windowSequences"])
        self.assertNotIn("experimentAdmissionEligible", result)

    def test_baseline_change_restarts_window_from_new_eligible_sample(self):
        values = [
            sample(machine(), 401),
            sample(machine(), 402),
            sample(machine([work("a", "WAITING")]), 403),
        ]
        result = operational_quiescence.evaluate_window(values)
        self.assertEqual("ACCUMULATING", result["status"])
        self.assertFalse(result["invalidated"])
        self.assertFalse(result["eligible"])
        self.assertEqual(1, result["resetCount"])
        self.assertEqual(["OPERATIONAL_BASELINE_CHANGED"], result["lastResetReasonCodes"])
        self.assertEqual([403], result["windowSequences"])
        self.assertIn("WINDOW_RESTARTED", result["reasonCodes"])

    def test_priority_sample_invalidates_current_window(self):
        values = [
            sample(machine(), 501),
            sample(machine(), 502),
            sample(machine([work("a")]), 503),
        ]
        result = operational_quiescence.evaluate_window(values)
        self.assertEqual("RESET", result["status"])
        self.assertTrue(result["invalidated"])
        self.assertFalse(result["eligible"])
        self.assertEqual([], result["windowSampleHashes"])
        self.assertIn("PRIORITY_OPERATION_REQUIRED", result["reasonCodes"])

    def test_three_new_samples_after_reset_can_complete_a_new_window(self):
        values = [
            sample(machine([work("a")]), 601),
            sample(machine(), 602),
            sample(machine(), 603),
            sample(machine(), 604),
        ]
        result = operational_quiescence.evaluate_window(values)
        self.assertEqual("QUIESCENT", result["status"])
        self.assertTrue(result["eligible"])
        self.assertFalse(result["invalidated"])
        self.assertEqual(1, result["resetCount"])
        self.assertEqual([602, 603, 604], result["windowSequences"])

    def test_duplicate_or_reordered_carrier_sequence_is_rejected(self):
        a = sample(machine(), 701)
        b = sample(machine(), 702)
        with self.assertRaisesRegex(
            RuntimeError, "OPERATIONAL_QUIESCENCE_SAMPLE_SEQUENCE_INVALID"
        ):
            operational_quiescence.evaluate_window([b, a])
        duplicate = copy.deepcopy(b)
        duplicate["observationId"] = "other"
        duplicate["sequence"] = 701
        body = {
            key: copy.deepcopy(item)
            for key, item in duplicate.items()
            if key != "sampleHash"
        }
        duplicate["sampleHash"] = stable_hash(body)
        with self.assertRaisesRegex(
            RuntimeError, "OPERATIONAL_QUIESCENCE_SAMPLE_SEQUENCE_INVALID"
        ):
            operational_quiescence.evaluate_window([a, duplicate])

    def test_window_is_not_experiment_admission(self):
        result = operational_quiescence.evaluate_window(
            [sample(machine(), 801), sample(machine(), 802), sample(machine(), 803)]
        )
        self.assertTrue(result["eligible"])
        self.assertEqual("operational-quiescence-only", result["decisionScope"])
        self.assertNotIn("experimentAdmissionEligible", result)
        self.assertNotIn("authorizesExperiment", result)


if __name__ == "__main__":
    unittest.main()
