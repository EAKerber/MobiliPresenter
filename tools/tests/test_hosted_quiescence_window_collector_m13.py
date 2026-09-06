from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import (
    agent_cycle,
    hosted_quiescence_sampling,
    operational_quiescence,
    runtime_capabilities,
)
from tools.tests import test_maintenance_inspect as fixture


def _runtime_inspection():
    return runtime_capabilities.build_inspection(
        {
            "schemaVersion": runtime_capabilities.PROVIDER_OBSERVATIONS_SCHEMA,
            "providers": {},
        }
    )


def _context():
    profile = agent_cycle.entry_profile("manager-gitops", "inspect-and-plan")
    return agent_cycle.build_context(
        role="manager-gitops",
        declared_intent="inspect-and-plan",
        lifecycle_phase=profile["lifecyclePhase"],
        objects=profile["objects"],
        operations=profile["operations"],
        scopes=profile["scope"],
        machine=fixture.machine(),
        runtime_inspection=_runtime_inspection(),
    )


def _sample(sequence: int, run_id: int) -> dict:
    context = _context()
    snapshot = hosted_quiescence_sampling.build_snapshot_from_context(context)
    return hosted_quiescence_sampling.derive_sample(
        context,
        snapshot=snapshot,
        readback_machine=context["projectMachine"],
        observation_id=f"{run_id}:1",
        sequence=sequence,
    )["sample"]


def _run(run_id: int, run_number: int, *, conclusion: str = "success") -> dict:
    return {
        "id": run_id,
        "run_number": run_number,
        "run_attempt": 1,
        "status": "completed",
        "conclusion": conclusion,
        "head_sha": "a" * 40,
    }


class HostedQuiescenceWindowCollectorM13Tests(unittest.TestCase):
    def test_collect_prior_samples_skips_whole_workflow_skips_and_selects_two_samples(self):
        runs = [
            _run(404, 404),
            _run(403, 403),
            _run(402, 402, conclusion="skipped"),
            _run(401, 401),
        ]
        samples = {
            403: _sample(403, 403),
            401: _sample(401, 401),
        }

        def download(_repository, run):
            return samples[int(run["id"])]

        with mock.patch.object(
            hosted_quiescence_sampling,
            "_workflow_runs",
            return_value=runs,
        ), mock.patch.object(
            hosted_quiescence_sampling,
            "_download_sample_from_run",
            side_effect=download,
        ) as download_sample:
            result = hosted_quiescence_sampling.collect_prior_samples(
                repository=operational_quiescence.REPOSITORY,
                current_run_id=404,
                current_sequence=404,
            )

        self.assertEqual([401, 403], [item["sequence"] for item in result])
        self.assertEqual(
            [403, 401],
            [int(call.args[1]["id"]) for call in download_sample.call_args_list],
        )

    def test_materialize_window_emits_quiescent_after_three_stable_samples(self):
        first = _sample(501, 501)
        second = _sample(502, 502)
        current = _sample(503, 503)

        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            hosted_quiescence_sampling,
            "collect_prior_samples",
            return_value=[first, second],
        ):
            result = hosted_quiescence_sampling.materialize_window(
                current,
                output_dir=tmp,
            )
            window = json.loads(
                (Path(tmp) / "operational-quiescence.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual("AVAILABLE", result["historyStatus"])
        self.assertEqual(2, result["historySampleCount"])
        self.assertEqual("QUIESCENT", result["windowStatus"])
        self.assertTrue(result["windowComplete"])
        self.assertTrue(result["windowEligible"])
        self.assertEqual([501, 502, 503], window["windowSequences"])
        self.assertEqual(3, window["sampleCountObserved"])
        operational_quiescence.validate_window(
            window,
            samples=[first, second, current],
        )

    def test_history_observation_failure_fails_closed_to_current_sample(self):
        current = _sample(603, 603)
        code = "HOSTED_QUIESCENCE_HISTORY_OBSERVATION_FAILED"

        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            hosted_quiescence_sampling,
            "collect_prior_samples",
            side_effect=hosted_quiescence_sampling.HostedQuiescenceHistoryError(
                code
            ),
        ):
            result = hosted_quiescence_sampling.materialize_window(
                current,
                output_dir=tmp,
            )
            window = json.loads(
                (Path(tmp) / "operational-quiescence.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual("UNKNOWN", result["historyStatus"])
        self.assertEqual([code], result["historyReasonCodes"])
        self.assertEqual(0, result["historySampleCount"])
        self.assertEqual("ACCUMULATING", result["windowStatus"])
        self.assertFalse(result["windowComplete"])
        self.assertFalse(result["windowEligible"])
        self.assertEqual(1, window["sampleCountObserved"])
        self.assertEqual([current["sampleHash"]], window["sampleHashesObserved"])


if __name__ == "__main__":
    unittest.main()
