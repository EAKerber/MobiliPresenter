from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/hosted-agent-cycle.yml"
HELPER = ROOT / "tools/hosted_quiescence_sampling.py"


class HostedQuiescenceWorkflowRQ2Tests(unittest.TestCase):
    def test_sampling_runs_only_after_begin_artifact_and_resumability_proof(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertLess(workflow.index("Upload begin context"), workflow.index("Qualify begin artifact resumability"))
        self.assertLess(workflow.index("Qualify begin artifact resumability"), workflow.index("Derive hosted quiescence sample"))
        sample = workflow.split("- name: Derive hosted quiescence sample", 1)[1].split(
            "- name: Upload hosted quiescence evidence", 1
        )[0]
        self.assertIn("steps.begin.outcome == 'success'", sample)
        self.assertIn("steps.begin_artifact.outcome == 'success'", sample)
        self.assertIn("steps.begin_resumability.outcome == 'success'", sample)
        self.assertIn("continue-on-error: true", sample)

    def test_sampling_reuses_internal_helper_and_carrier_identity(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        sample = workflow.split("- name: Derive hosted quiescence sample", 1)[1].split(
            "- name: Upload hosted quiescence evidence", 1
        )[0]
        self.assertIn("hosted_quiescence_sampling.materialize_from_files", sample)
        self.assertIn("GITHUB_RUN_ID", sample)
        self.assertIn("GITHUB_RUN_ATTEMPT", sample)
        self.assertIn("GITHUB_RUN_NUMBER", sample)
        self.assertIn("/tmp/hosted-quiescence", sample)
        self.assertNotIn("/tmp/hosted-result.json", sample)
        self.assertNotIn("operational-quiescence evaluate", workflow)

    def test_sampling_failure_cannot_gate_begin_or_operational_result(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        require = workflow.split("- name: Require operational result", 1)[1]
        self.assertNotIn("hosted_quiescence", require)
        self.assertEqual(2, workflow.count("steps.hosted_quiescence.outcome"))
        upload = workflow.split("- name: Upload hosted quiescence evidence", 1)[1].split(
            "- name: Observe exact begin artifact", 1
        )[0]
        self.assertIn("continue-on-error: true", upload)
        self.assertIn("/tmp/hosted-quiescence", upload)

    def test_helper_stays_internal_instead_of_becoming_second_entrypoint(self):
        helper = HELPER.read_text(encoding="utf-8")
        self.assertNotIn("argparse", helper)
        self.assertNotIn("if __name__ ==", helper)
        self.assertNotIn("def main(", helper)
        self.assertNotIn("def run(", helper)

    def test_workflow_does_not_reimplement_rq1_or_rq2_contracts(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        for forbidden in (
            "OperationalQuiescenceSample 0.",
            "OperationalQuiescence 0.",
            "ReflectionEligibility 0.",
            "stable_hash",
            "sampleEligible =",
            "baselineHash =",
        ):
            self.assertNotIn(forbidden, workflow)


if __name__ == "__main__":
    unittest.main()
