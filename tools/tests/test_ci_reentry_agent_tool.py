from __future__ import annotations

import copy
import unittest

from tools import agent_cycle_readiness
from tools.agent_tools import contracts, projection, resolver


def brief(*available: str, conditional=()):
    return {
        "capabilityProjection": {
            "required": [],
            "relevantAvailable": sorted(available),
            "conditional": sorted(conditional),
            "requiredUnavailable": [],
        }
    }


def workflow(run_id: int, name: str, head_sha: str) -> dict:
    return {
        "name": name,
        "id": run_id,
        "status": "completed",
        "conclusion": "action_required",
        "event": "pull_request",
        "headSha": head_sha,
        "actor": "github-actions[bot]",
        "triggeringActor": "github-actions[bot]",
        "sameRepository": True,
        "runAttempt": 1,
        "jobsObserved": True,
        "jobCount": 0,
    }


def machine(*, head_sha="a" * 40, ci="reentry_required") -> dict:
    runs = [
        workflow(11, "Agent Ops", head_sha),
        workflow(12, "Coordination Guard", head_sha),
        workflow(13, "Supervisor Snapshot", head_sha),
    ]
    return {
        "sensors": {
            "pullRequests": {
                "data": {
                    "available": True,
                    "items": [
                        {
                            "number": 278,
                            "headRef": "work/operations/ci-reentry-test",
                            "headSha": head_sha,
                            "ci": ci,
                            "ciObserved": True,
                            "workflows": runs,
                        }
                    ],
                }
            }
        }
    }


def context(*, head_sha="a" * 40) -> dict:
    return {
        "contextHash": "b" * 64,
        "repository": "EAKerber/MobiliPresenter",
        "semanticContext": {
            "role": "manager-gitops",
            "declaredIntent": "inspect-and-plan",
        },
        "semanticBrief": brief("project.inspect", "routine.inspect"),
        "projectMachine": machine(head_sha=head_sha),
    }


def request(*, head_sha="a" * 40, run_ids=None) -> dict:
    begin = {"runId": 123, "sourceSha": "d" * 40, "contextHash": "b" * 64}
    actor = {
        "role": "manager-gitops",
        "workerId": "manager-gitops-a",
        "sessionId": "ci-reentry-test",
    }
    target = {}
    input_value = {
        "prNumber": 278,
        "headSha": head_sha,
        "runIds": [11, 12, 13] if run_ids is None else run_ids,
    }
    return {
        "schemaVersion": contracts.REQUEST_SCHEMA,
        "requestId": contracts.deterministic_request_id(
            begin=begin,
            actor=actor,
            tool_id="ci.workflow.rerun",
            target=target,
            input_value=input_value,
        ),
        "begin": begin,
        "actor": actor,
        "toolId": "ci.workflow.rerun",
        "target": target,
        "input": input_value,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


class CiReentryAgentToolTests(unittest.TestCase):
    def test_rerun_is_plannable_but_not_executable(self):
        value = projection.build_projection(
            {"role": "manager-gitops", "declaredIntent": "inspect-and-plan"},
            brief("project.inspect", "routine.inspect"),
        )
        entry = next(item for item in value["plannable"] if item["toolId"] == "ci.workflow.rerun")
        self.assertEqual(entry["mode"], "plan-only")
        self.assertEqual(entry["effectClass"], "transport-side-effect")

    def test_readiness_funnels_proven_reentry_to_rerun_plan(self):
        tools = projection.build_projection(
            {"role": "manager-gitops", "declaredIntent": "inspect-and-plan"},
            brief("project.inspect", "routine.inspect"),
        )
        readiness = agent_cycle_readiness.build_projection(
            legacy_status="READY",
            blocking_unknowns=[],
            tools=tools,
            machine=machine(),
        )
        action = readiness["nextSafeAction"]
        self.assertEqual(action["action"], "PLAN_TOOL")
        self.assertEqual(action["toolId"], "ci.workflow.rerun")
        self.assertEqual(action["mode"], "plan-only")
        self.assertEqual(action["reasonCodes"], ["CI_REENTRY_REQUIRED"])
        self.assertFalse(action["authorizesMutation"])

    def test_readiness_does_not_funnel_unproven_reentry(self):
        value = machine(ci="unknown")
        tools = projection.build_projection(
            {"role": "manager-gitops", "declaredIntent": "inspect-and-plan"},
            brief("project.inspect", "routine.inspect"),
        )
        readiness = agent_cycle_readiness.build_projection(
            legacy_status="READY",
            blocking_unknowns=[],
            tools=tools,
            machine=value,
        )
        self.assertEqual(readiness["nextSafeAction"]["action"], "SELECT_TOOL")

    def test_plan_is_bound_to_exact_observed_head_and_run_set(self):
        resolved = resolver.resolve_request(request(), context(), execute=True)
        self.assertEqual(resolved["result"]["status"], "PLANNED")
        self.assertEqual(resolved["plan"]["mode"], "plan-only")
        concrete = resolved["plan"]["concrete"]
        self.assertEqual(concrete["reasonCode"], "CI_REENTRY_REQUIRED")
        self.assertEqual(concrete["runIds"], [11, 12, 13])
        self.assertEqual(concrete["executionStatus"], "PLAN_ONLY")
        self.assertEqual(concrete["requiredExecutionPermission"], "actions:write")
        self.assertIsNone(concrete["executionProvider"])
        self.assertTrue(all(item["method"] == "POST" for item in concrete["requests"]))
        self.assertFalse(concrete["authorizesMutation"])

    def test_head_drift_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "AGENT_TOOL_CI_REENTRY_HEAD_MISMATCH"):
            resolver.resolve_request(request(head_sha="c" * 40), context(), execute=True)

    def test_run_set_drift_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "AGENT_TOOL_CI_REENTRY_RUN_SET_MISMATCH"):
            resolver.resolve_request(request(run_ids=[11, 12]), context(), execute=True)


if __name__ == "__main__":
    unittest.main()
