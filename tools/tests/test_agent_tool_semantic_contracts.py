from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from tools import agent_cycle_identity
from tools.agent_tools import contracts, policy, projection, trace
from tools.canonical import stable_hash
from tools.semantics.registry import ROOT, load_registry, validate_registry


class AgentToolSemanticContractTests(unittest.TestCase):
    EXPECTED = {
        "agent-cycle-handle": ("tools.agent_cycle_identity.validate_handle", "ops/schemas/agent-cycle-handle.schema.json", agent_cycle_identity.HANDLE_SCHEMA, agent_cycle_identity.HANDLE_FIELDS),
        "agent-tool-policy-catalog": ("tools.agent_tools.policy.validate_policy", "ops/schemas/agent-tool-policy-catalog.schema.json", policy.POLICY_SCHEMA, policy.TOP_FIELDS),
        "agent-tool-request": ("tools.agent_tools.contracts.validate_request", "ops/schemas/agent-tool-request.schema.json", contracts.REQUEST_SCHEMA, contracts.REQUEST_FIELDS),
        "agent-tool-plan": ("tools.agent_tools.contracts.validate_plan", "ops/schemas/agent-tool-plan.schema.json", contracts.PLAN_SCHEMA, contracts.PLAN_FIELDS),
        "agent-tool-execution-result": ("tools.agent_tools.contracts.validate_result", "ops/schemas/agent-tool-execution-result.schema.json", contracts.RESULT_SCHEMA, contracts.RESULT_FIELDS),
        "agent-tool-projection": ("tools.agent_tools.projection.validate_projection", "ops/schemas/agent-tool-projection.schema.json", projection.PROJECTION_SCHEMA, projection.PROJECTION_FIELDS),
        "agent-cycle-execution-trace": ("tools.agent_tools.trace.validate_trace", "ops/schemas/agent-cycle-execution-trace.schema.json", trace.TRACE_SCHEMA, trace.TRACE_FIELDS),
    }

    def test_policy_catalog_is_runtime_valid(self):
        self.assertEqual(policy.POLICY_SCHEMA, policy.load_policy()["schemaVersion"])

    def test_agent_tool_contracts_are_registered_and_structurally_aligned(self):
        registry = load_registry()
        self.assertEqual([], validate_registry(registry))
        for contract_id, (validator, schema_path, title, fields) in self.EXPECTED.items():
            item = registry["contracts"].get(contract_id)
            self.assertIsInstance(item, dict, contract_id)
            self.assertEqual(validator, item["semanticValidator"])
            self.assertEqual(schema_path, item["structuralSchema"])
            schema = json.loads((ROOT / schema_path).read_text(encoding="utf-8"))
            self.assertEqual(title, schema["title"])
            self.assertFalse(schema["additionalProperties"])
            self.assertEqual(fields, set(schema["properties"]))
            self.assertEqual(fields, set(schema["required"]))

    def test_trace_contract_is_hash_bound_and_summary_checked(self):
        core = {
            "schemaVersion": trace.TRACE_SCHEMA,
            "cycleInstanceId": "cycle-instance-test",
            "begin": {"runId": 1, "sourceSha": "a" * 40, "contextHash": "b" * 64},
            "actor": {"role": "manager-gitops", "workerId": "manager-gitops-a", "sessionId": "session-1"},
            "window": {"issueNumber": 145, "beginCommentId": 10, "closeCommentId": 20},
            "attempts": [{
                "kind": "agent-tool", "requestCommentId": 11, "resultCommentId": 12,
                "requestHash": "c" * 64, "operationId": "agent-tool-example",
                "status": "BLOCKED", "blockers": ["EXPECTED_BLOCKER"], "matched": True,
            }],
            "summary": {"attemptCount": 1, "matchedCount": 1, "passCount": 0, "blockedCount": 1, "unknownCount": 0},
            "traceStatus": "PASS",
            "readOnly": True,
            "semanticAuthority": False,
            "authorizesMutation": False,
        }
        value = {**core, "traceHash": stable_hash(core)}
        self.assertEqual(value, trace.validate_trace(value))
        bad = copy.deepcopy(value)
        bad["summary"]["blockedCount"] = 0
        bad["traceHash"] = stable_hash({key: item for key, item in bad.items() if key != "traceHash"})
        with self.assertRaisesRegex(RuntimeError, "AGENT_TRACE_SUMMARY_MISMATCH"):
            trace.validate_trace(bad)


if __name__ == "__main__":
    unittest.main()
