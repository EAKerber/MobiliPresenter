from __future__ import annotations

import unittest
from unittest.mock import patch

from tools.agent_tools import admission, contracts, resolver


def _brief(*available: str, conditional=()):
    return {
        "capabilityProjection": {
            "required": [],
            "relevantAvailable": sorted(available),
            "conditional": sorted(conditional),
            "requiredUnavailable": [],
        }
    }


def _context(*available: str, intent="inspect-and-plan", conditional=()):
    return {
        "contextHash": "b" * 64,
        "semanticContext": {"role": "manager-gitops", "declaredIntent": intent},
        "semanticBrief": _brief(*available, conditional=conditional),
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
        "tools.agent_tools.adapters.remote_git_files.git_observation.observe_branch",
        return_value={
            "repository": "EAKerber/MobiliPresenter",
            "branch": "work/operations/at2d",
            "branchHead": "c" * 40,
            "readOnly": True,
            "semanticAuthority": False,
            "authorizesMutation": False,
        },
    )
    def test_shared_mutation_has_providers_but_still_requires_proofs_and_execution_mode(self, observe):
        request = _request(
            "git.files.mutate",
            target={"branch": "work/operations/at2d"},
            input_value={
                "changes": [{"path": "docs/at2d.txt", "content": "x"}],
                "message": "AT2D plan",
            },
        )
        resolved = resolver.resolve_request(
            request,
            _context(
                intent="governed-mutation",
                conditional=("remote.canonical.execute",),
            ),
            execute=False,
        )
        plan = resolved["plan"]
        self.assertEqual(plan["status"], "READY")
        self.assertEqual(plan["mode"], "mutation-execute")
        self.assertEqual(admission.missing_guard_proof_providers(plan), [])
        with self.assertRaisesRegex(RuntimeError, "AGENT_TOOL_GUARD_PROOFS_REQUIRED"):
            admission.assert_execution_admitted(plan)
        observe.assert_called_once()

    def test_read_only_plan_is_admitted_to_existing_read_only_adapter(self):
        request = _request("project.inspect", target={}, input_value={})
        resolved = resolver.resolve_request(request, _context("project.inspect"), execute=False)
        admission.assert_execution_admitted(resolved["plan"])
        self.assertEqual(resolved["plan"]["effectClass"], "read-only")


    @patch("tools.agent_tools.admission._prove_agent_write_lifecycle_result")
    @patch("tools.agent_tools.admission.guard_proofs.validate_proof_set")
    def test_portable_lifecycle_result_is_supported_without_hosted_context(
        self, validate_set, prove_lifecycle
    ):
        plan = {
            "schemaVersion": contracts.PLAN_SCHEMA,
            "requestHash": "1" * 64,
            "begin": {"runId": 123, "sourceSha": "a" * 40, "contextHash": "b" * 64},
            "actor": {
                "role": "manager-gitops",
                "workerId": "manager-gitops-a",
                "sessionId": "session-1",
            },
            "toolId": "git.files.mutate",
            "effectClass": "shared-durable-mutation",
            "mode": "mutation-execute",
            "adapter": "remote-git-files",
            "requiredCapabilities": [],
            "eligibleToolSurfaces": [],
            "targetPolicy": "manager-git-mutation",
            "guards": ["agent-write-lifecycle-bound"],
            "target": {"branch": "work/operations/e3"},
            "input": {"changes": [{"path": "docs/e3.txt", "content": "x"}], "message": "e3"},
            "concrete": {},
            "status": "READY",
            "readOnly": True,
            "semanticAuthority": False,
            "authorizesMutation": False,
        }
        body = dict(plan)
        from tools.canonical import stable_hash
        plan["planHash"] = stable_hash(body)
        with patch("tools.agent_tools.admission.contracts.validate_plan", return_value=plan):
            prove_lifecycle.return_value = {"kind": "lifecycle"}
            validate_set.side_effect = lambda value, plan=None: value
            result = admission.collect_guard_proofs(
                plan,
                transport=object(),
                lifecycle_result_context={
                    "cycleInstanceId": "cycle-instance-" + "1" * 24,
                    "lifecycleResult": {"resultHash": "2" * 64},
                    "lifecycleResultRef": {"kind": "provided-result", "value": "2" * 64},
                },
            )
        self.assertEqual(result["status"], "PASS")
        prove_lifecycle.assert_called_once()


if __name__ == "__main__":
    unittest.main()
