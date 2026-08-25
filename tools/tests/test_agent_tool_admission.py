from __future__ import annotations

import unittest
from unittest.mock import patch

from tools.agent_tools import admission, contracts, resolver


def _brief(*available: str):
    return {
        "capabilityProjection": {
            "required": [],
            "relevantAvailable": sorted(available),
            "conditional": [],
            "requiredUnavailable": [],
        }
    }


def _context(*available: str):
    return {
        "contextHash": "b" * 64,
        "semanticContext": {"role": "manager-gitops", "declaredIntent": "inspect-and-plan"},
        "semanticBrief": _brief(*available),
        "projectMachine": {"schemaVersion": "test-project-machine", "scope": "live"},
        "routineInspection": {"status": "PASS", "value": {"schemaVersion": "test-routine"}, "reasonCode": None},
    }


def _request(tool_id: str, *, target: dict, input_value: dict):
    begin = {"runId": 123, "sourceSha": "a" * 40, "contextHash": "b" * 64}
    actor = {"role": "manager-gitops", "workerId": "manager-gitops-a", "sessionId": "session-1"}
    return {
        "schemaVersion": contracts.REQUEST_SCHEMA,
        "requestId": contracts.deterministic_request_id(
            begin=begin,
            actor=actor,
            tool_id=tool_id,
            target=target,
            input_value=input_value,
        ),
        "begin": begin,
        "actor": actor,
        "toolId": tool_id,
        "target": target,
        "input": input_value,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


class AgentToolAdmissionTests(unittest.TestCase):
    @patch(
        "tools.agent_tools.adapters.remote_git_file.git_observation.observe_file",
        return_value={
            "repository": "EAKerber/MobiliPresenter",
            "branch": "work/operations/at2d",
            "path": "docs/at2d.txt",
            "branchHead": "c" * 40,
            "blobSha": None,
            "readOnly": True,
            "semanticAuthority": False,
            "authorizesMutation": False,
        },
    )
    def test_shared_mutation_has_providers_but_still_requires_proofs_and_execution_mode(self, observe):
        request = _request(
            "git.file.create",
            target={"branch": "work/operations/at2d", "path": "docs/at2d.txt"},
            input_value={"content": "x", "message": "AT2D plan"},
        )
        resolved = resolver.resolve_request(request, _context("remote.canonical.execute"))
        plan = resolved["plan"]
        self.assertEqual(plan["status"], "PLANNED")
        self.assertEqual(admission.missing_guard_proof_providers(plan), [])
        with self.assertRaisesRegex(RuntimeError, "AGENT_TOOL_GUARD_PROOFS_REQUIRED"):
            admission.assert_execution_admitted(plan)
        observe.assert_called_once()

    def test_read_only_plan_is_admitted_to_existing_read_only_adapter(self):
        request = _request("project.inspect", target={}, input_value={})
        resolved = resolver.resolve_request(request, _context("project.inspect"), execute=False)
        admission.assert_execution_admitted(resolved["plan"])
        self.assertEqual(resolved["plan"]["effectClass"], "read-only")


if __name__ == "__main__":
    unittest.main()
