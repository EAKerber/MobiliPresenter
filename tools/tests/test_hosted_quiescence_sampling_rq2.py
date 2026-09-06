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
    project_machine,
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


def _context(role="manager-gitops", intent="inspect-and-plan"):
    profile = agent_cycle.entry_profile(role, intent)
    return agent_cycle.build_context(
        role=role,
        declared_intent=intent,
        lifecycle_phase=profile["lifecyclePhase"],
        objects=profile["objects"],
        operations=profile["operations"],
        scopes=profile["scope"],
        machine=fixture.machine(),
        runtime_inspection=_runtime_inspection(),
    )


def _drifted_machine():
    sensors = fixture.sensors()
    sensors["control"]["data"]["sha"] = "9" * 40
    return project_machine.build_inspection(fixture.state(), sensors, scope="live")


class HostedQuiescenceSamplingRQ2Tests(unittest.TestCase):
    def test_manager_inspect_and_plan_derives_exact_eligible_sample(self):
        context = _context()
        snapshot = hosted_quiescence_sampling.build_snapshot_from_context(context)
        derived = hosted_quiescence_sampling.derive_sample(
            context,
            snapshot=snapshot,
            readback_machine=context["projectMachine"],
            observation_id="hosted:101:1",
            sequence=101,
        )
        sample = derived["sample"]
        self.assertTrue(sample["sampleEligible"])
        self.assertEqual("REFLECTION_ELIGIBLE", sample["reflectionStatus"])
        self.assertEqual("hosted:101:1", sample["observationId"])
        self.assertEqual(101, sample["sequence"])
        self.assertEqual(sample["sourceCriticalHash"], sample["readbackCriticalHash"])
        self.assertEqual(sample["baselineHash"], sample["readbackCriticalHash"])
        operational_quiescence.validate_sample_derivation(
            sample,
            snapshot=snapshot,
            reflection=derived["reflectionEligibility"],
            source_machine=context["projectMachine"],
            routine_inspection=context["routineInspection"]["value"],
            readback_machine=context["projectMachine"],
        )

    def test_non_applicable_role_is_noop_without_live_readback(self):
        context = _context(role="ui-ux", intent="inspect-and-plan")
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            hosted_quiescence_sampling.project_machine,
            "inspect_live",
        ) as inspect_live:
            result = hosted_quiescence_sampling.materialize(
                context,
                observation_id="hosted:201:1",
                sequence=201,
                output_dir=tmp,
            )
        self.assertEqual(
            {
                "ok": True,
                "applicable": False,
                "role": "ui-ux",
                "declaredIntent": "inspect-and-plan",
                "readOnly": True,
                "semanticAuthority": False,
                "authorizesMutation": False,
            },
            result,
        )
        inspect_live.assert_not_called()

    def test_snapshot_is_materialized_before_fresh_readback(self):
        context = _context()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            def observe():
                self.assertTrue((root / "scheduler-snapshot.json").is_file())
                self.assertFalse((root / "project-machine-readback.json").exists())
                return context["projectMachine"]

            with mock.patch.object(
                hosted_quiescence_sampling.project_machine,
                "inspect_live",
                side_effect=observe,
            ) as inspect_live:
                result = hosted_quiescence_sampling.materialize(
                    context,
                    observation_id="hosted:301:1",
                    sequence=301,
                    output_dir=root,
                )
            self.assertTrue(result["applicable"])
            self.assertTrue(result["sampleEligible"])
            inspect_live.assert_called_once_with()
            sample = json.loads(
                (root / "operational-quiescence-sample.json").read_text(encoding="utf-8")
            )
            self.assertEqual("hosted:301:1", sample["observationId"])
            self.assertEqual(301, sample["sequence"])

    def test_authority_drift_is_rejected_before_sample_materialization(self):
        context = _context()
        snapshot = hosted_quiescence_sampling.build_snapshot_from_context(context)
        with self.assertRaisesRegex(RuntimeError, "SCHEDULER_SNAPSHOT_STALE_CONTROL"):
            hosted_quiescence_sampling.derive_sample(
                context,
                snapshot=snapshot,
                readback_machine=_drifted_machine(),
                observation_id="hosted:401:1",
                sequence=401,
            )

    def test_materialize_preserves_carrier_identity_exactly(self):
        context = _context()
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            hosted_quiescence_sampling.project_machine,
            "inspect_live",
            return_value=context["projectMachine"],
        ):
            result = hosted_quiescence_sampling.materialize(
                context,
                observation_id="33999999999:2",
                sequence=1234,
                output_dir=tmp,
            )
            sample = json.loads(
                (Path(tmp) / "operational-quiescence-sample.json").read_text(
                    encoding="utf-8"
                )
            )
        self.assertEqual("33999999999:2", result["observationId"])
        self.assertEqual(1234, result["sequence"])
        self.assertEqual(result["observationId"], sample["observationId"])
        self.assertEqual(result["sequence"], sample["sequence"])
        self.assertFalse(result["semanticAuthority"])
        self.assertFalse(result["authorizesMutation"])


if __name__ == "__main__":
    unittest.main()
