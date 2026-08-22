import copy
import unittest
from unittest import mock

from tools import agent_cycle, agent_cycle_close, project_machine, runtime_capabilities, transition_protocol
from tools.canonical import stable_hash


class AgentCycleCloseTests(unittest.TestCase):
    def _context(self):
        machine = project_machine.inspect_local()
        runtime = runtime_capabilities.build_inspection(
            runtime_capabilities.local_provider_observations()
        )
        profile = agent_cycle.entry_profile("manager-gitops", "bootstrap-discovery")
        return agent_cycle.build_context(
            role="manager-gitops",
            declared_intent="bootstrap-discovery",
            lifecycle_phase=profile["lifecyclePhase"],
            objects=profile["objects"],
            operations=profile["operations"],
            scopes=profile["scope"],
            machine=machine,
            runtime_inspection=runtime,
        )

    def test_current_context_declares_close_implemented(self):
        context = self._context()
        self.assertEqual(context["closeRequirements"]["schemaVersion"], "AgentCycleCloseContract 0.1")
        self.assertTrue(context["closeRequirements"]["implemented"])
        self.assertIsNone(context["closeRequirements"]["nextSlice"])
        self.assertFalse(context["authorizesMutation"])

    def test_legacy_os1b_context_remains_valid(self):
        context = self._context()
        legacy = copy.deepcopy(context)
        legacy["closeRequirements"]["schemaVersion"] = "AgentCycleCloseFoundation 0.1"
        legacy["closeRequirements"]["implemented"] = False
        legacy["closeRequirements"]["nextSlice"] = "M10-OS1C"
        legacy["contextHash"] = stable_hash({key: value for key, value in legacy.items() if key != "contextHash"})
        agent_cycle.validate_context(legacy)

    def test_baseline_is_bound_to_embedded_artifacts(self):
        context = self._context()
        tampered = copy.deepcopy(context)
        tampered["baseline"]["projectStateHash"] = "0" * 64
        tampered["baseline"]["baselineHash"] = stable_hash(
            {key: value for key, value in tampered["baseline"].items() if key != "baselineHash"}
        )
        tampered["cycleId"] = f"cycle-{tampered['baseline']['baselineHash'][:20]}"
        tampered["contextHash"] = stable_hash({key: value for key, value in tampered.items() if key != "contextHash"})
        with self.assertRaisesRegex(RuntimeError, "AGENT_CYCLE_BASELINE_ARTIFACT_MISMATCH"):
            agent_cycle.validate_context(tampered)

    def test_identical_cycle_delta_has_no_durable_changes(self):
        context = self._context()
        delta = agent_cycle_close.build_delta(context, copy.deepcopy(context))
        self.assertFalse(delta["changed"])
        self.assertEqual(delta["durableChanges"], [])
        self.assertFalse(delta["authorizesMutation"])

    def test_unattributed_durable_delta_is_unknown(self):
        context = self._context()
        fake_delta = {
            "schemaVersion": "AgentCycleDelta 0.1",
            "cycleId": context["cycleId"],
            "beforeContextHash": context["contextHash"],
            "afterContextHash": context["contextHash"],
            "beforeBaselineHash": context["baseline"]["baselineHash"],
            "afterBaselineHash": context["baseline"]["baselineHash"],
            "durableChanges": [{
                "kind": "source-head", "name": "control", "branch": "main",
                "before": "1" * 40, "after": "2" * 40,
            }],
            "derivedChanges": [],
            "blockingUnknownsAdded": [],
            "blockingUnknownsResolved": [],
            "beforeStatus": context["status"],
            "afterStatus": context["status"],
            "changed": True,
            "readOnly": True,
            "semanticAuthority": False,
            "authorizesMutation": False,
            "deltaHash": "0" * 64,
        }
        with mock.patch.object(agent_cycle_close, "build_delta", return_value=fake_delta):
            receipt = agent_cycle_close.build_receipt(context, context)
        self.assertEqual(receipt["status"], "UNKNOWN")
        self.assertIn("UNATTRIBUTED_DURABLE_DELTA", receipt["blockers"])
        self.assertEqual(receipt["aggregateReadback"]["uncoveredDurableChanges"], ["source-head:control:0"])

    def test_transition_receipt_is_verified_and_hash_bound(self):
        before = {"value": 1}
        after = {"value": 2}
        plan = transition_protocol.build_plan(
            domain="project-state",
            action="checkpoint",
            subject={"kind": "project", "id": "mobilipresenter"},
            authority={"kind": "git-file", "locator": {"branch": "main", "path": "ops/state/project.json"}},
            before=before,
            candidate=after,
            intent={"reason": "test"},
        )
        receipt = transition_protocol.build_receipt(plan, after, authority_revision="abc123")
        evidence = agent_cycle_close.verify_evidence({
            "kind": "transition-receipt", "plan": plan, "receipt": receipt,
        })
        self.assertEqual(evidence["domain"], "project-state")
        self.assertEqual(evidence["readbackHash"], receipt["receiptHash"])
        self.assertEqual(len(evidence["evidenceHash"]), 64)


if __name__ == "__main__":
    unittest.main()
