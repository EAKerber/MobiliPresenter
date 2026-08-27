from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from tools import agent_cycle, hosted_agent_cycle, hosted_agent_cycle_trace
from tools import project_machine, runtime_capabilities
from tools.agent_tools import contracts, mutation_dispatch, trace_collect
from tools.canonical import stable_hash


ROOT = Path(__file__).resolve().parents[2]
ACTOR = {
    "role": "manager-gitops",
    "workerId": "manager-gitops-r0",
    "sessionId": "r0-characterization",
}
BEGIN = {"runId": 123, "sourceSha": "a" * 40, "contextHash": "b" * 64}


def _context(intent: str) -> dict:
    machine = project_machine.inspect_local()
    runtime = runtime_capabilities.build_inspection(
        {
            "schemaVersion": runtime_capabilities.PROVIDER_OBSERVATIONS_SCHEMA,
            "providers": {},
        }
    )
    profile = agent_cycle.entry_profile("manager-gitops", intent)
    return agent_cycle.build_context(
        role="manager-gitops",
        declared_intent=intent,
        lifecycle_phase=profile["lifecyclePhase"],
        objects=profile["objects"],
        operations=profile["operations"],
        scopes=profile["scope"],
        machine=machine,
        runtime_inspection=runtime,
    )


def _manifest() -> dict:
    return {
        "source": {
            "runId": 123,
            "sourceSha": "a" * 40,
            "issueNumber": 145,
            "commentId": 100,
        },
        "contextHash": "b" * 64,
        "actor": copy.deepcopy(ACTOR),
    }


def _owner_comment(comment_id: int, marker: str, payload: dict) -> dict:
    return {
        "id": comment_id,
        "author_association": "OWNER",
        "user": {"login": "EAKerber"},
        "body": marker + "\n" + json.dumps(payload),
    }


def _bot_comment(comment_id: int, marker: str, payload: dict) -> dict:
    return {
        "id": comment_id,
        "author_association": "NONE",
        "user": {"login": "github-actions[bot]"},
        "body": marker + "\n```json\n" + json.dumps(payload) + "\n```",
    }


def _request() -> dict:
    value = {
        "schemaVersion": contracts.REQUEST_SCHEMA,
        "requestId": "r0-late-result",
        "begin": copy.deepcopy(BEGIN),
        "actor": copy.deepcopy(ACTOR),
        "toolId": "project.inspect",
        "target": {},
        "input": {},
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return contracts.validate_request(value)


def _comments_with_result_after_close() -> list[dict]:
    request = _request()
    return [
        {"id": 100, "author_association": "OWNER", "user": {"login": "EAKerber"}, "body": "begin"},
        _owner_comment(101, trace_collect.AGENT_TOOL_REQUEST_MARKER, request),
        {"id": 200, "author_association": "OWNER", "user": {"login": "EAKerber"}, "body": "close"},
        _bot_comment(
            201,
            trace_collect.AGENT_TOOL_RESULT_MARKER,
            {
                "requestHash": stable_hash(request),
                "begin": copy.deepcopy(BEGIN),
                "actor": copy.deepcopy(ACTOR),
                "status": "PASS",
                "blockers": [],
            },
        ),
    ]


def _close_command() -> dict:
    return {
        "schemaVersion": hosted_agent_cycle.COMMAND_SCHEMA,
        "requestId": "r0-close",
        "action": "close",
        "actor": copy.deepcopy(ACTOR),
        "declaredIntent": "inspect-and-plan",
        "machineScope": "live",
        "begin": copy.deepcopy(BEGIN),
        "evidenceCommentIds": [],
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


class AgentCycleR0CharacterizationTests(unittest.TestCase):
    """Freeze observed AT3D behavior before the R1 vocabulary refactor.

    Several assertions intentionally describe known gaps. They are compatibility
    alarms, not claims that the behavior is desirable. A later slice may change
    them only with an explicit replacement expectation.
    """

    def test_governed_mutation_context_can_be_ready_while_tool_is_conditional(self):
        context = _context("governed-mutation")

        self.assertEqual(context["status"], "READY")
        self.assertEqual(context["blockingUnknowns"], [])
        self.assertEqual(context["agentTools"]["available"], [])
        self.assertEqual(
            [item["toolId"] for item in context["agentTools"]["conditional"]],
            ["git.files.mutate"],
        )
        self.assertEqual(
            context["agentTools"]["conditional"][0]["reasonCode"],
            "CAPABILITY_NOT_AVAILABLE:remote.canonical.execute",
        )

    def test_cycle_identity_is_a_context_fingerprint_not_an_instance_identity(self):
        first = _context("inspect-and-plan")
        second = _context("inspect-and-plan")

        self.assertEqual(first["baseline"]["baselineHash"], second["baseline"]["baselineHash"])
        self.assertEqual(first["cycleId"], second["cycleId"])
        self.assertEqual(first["contextHash"], second["contextHash"])

    def test_hosted_instance_identity_changes_with_the_begin_source(self):
        first = _manifest()
        second = copy.deepcopy(first)
        second["source"]["runId"] = 124
        second["source"]["commentId"] = 101

        self.assertNotEqual(
            trace_collect.cycle_instance_id(first),
            trace_collect.cycle_instance_id(second),
        )

    def test_close_requirements_are_static_across_intents(self):
        inspect = _context("inspect-and-plan")
        mutate = _context("governed-mutation")

        self.assertEqual(inspect["closeRequirements"], mutate["closeRequirements"])
        self.assertEqual(
            mutate["closeRequirements"]["requiredEvidence"],
            agent_cycle.CLOSE_EVIDENCE,
        )

    def test_durable_baseline_has_only_the_four_project_machine_source_heads(self):
        context = _context("governed-mutation")

        self.assertEqual(
            set(context["baseline"]["sourceHeads"]),
            {"inspection", "control", "coordination", "continuation"},
        )
        self.assertNotIn("touchedResources", context["baseline"])

    def test_hosted_begin_command_has_no_work_binding(self):
        command = {
            "schemaVersion": hosted_agent_cycle.COMMAND_SCHEMA,
            "requestId": "r0-begin",
            "action": "begin",
            "actor": copy.deepcopy(ACTOR),
            "declaredIntent": "inspect-and-plan",
            "machineScope": "live",
            "begin": None,
            "evidenceCommentIds": [],
            "semanticAuthority": False,
            "authorizesMutation": False,
        }
        hosted_agent_cycle.validate_command(command)

        command["workId"] = "work:r0-example"
        with self.assertRaisesRegex(RuntimeError, "HOSTED_AGENT_COMMAND_FIELDS_INVALID"):
            hosted_agent_cycle.validate_command(command)

    @patch("tools.hosted_agent_cycle._run_agent")
    def test_hosted_begin_failure_compacts_the_root_blocker(self, run_agent):
        command = {
            "schemaVersion": hosted_agent_cycle.COMMAND_SCHEMA,
            "requestId": "r0-begin-failure",
            "action": "begin",
            "actor": copy.deepcopy(ACTOR),
            "declaredIntent": "inspect-and-plan",
            "machineScope": "live",
            "begin": None,
            "evidenceCommentIds": [],
            "semanticAuthority": False,
            "authorizesMutation": False,
        }
        run_agent.return_value = (
            2,
            {
                "status": "BLOCKED",
                "blockingUnknowns": ["ROOT_PROVIDER_SCOPE_MISSING"],
            },
        )

        with self.assertRaises(hosted_agent_cycle.HostedAgentCycleError) as raised:
            hosted_agent_cycle.begin_from_envelope(
                command,
                {"issueNumber": 145, "commentId": 100},
                context_path="unused-context.json",
                manifest_path="unused-manifest.json",
            )
        failure = hosted_agent_cycle.failure_payload(raised.exception, command)

        self.assertEqual(failure["blockers"], ["HOSTED_AGENT_BEGIN_NOT_READY"])
        self.assertNotIn("ROOT_PROVIDER_SCOPE_MISSING", failure["detail"])
        self.assertEqual(failure["detail"], "HOSTED_AGENT_BEGIN_NOT_READY:BLOCKED")

    def test_result_after_close_is_outside_the_current_trace_window(self):
        trace = trace_collect.build_trace(
            _comments_with_result_after_close(),
            _manifest(),
            close_comment_id=200,
        )

        self.assertEqual(trace["traceStatus"], "INCOMPLETE")
        self.assertEqual(trace["summary"]["attemptCount"], 1)
        self.assertEqual(trace["summary"]["matchedCount"], 0)
        self.assertEqual(trace["attempts"][0]["blockers"], ["EXECUTION_RESULT_MISSING"])

    def test_interleaved_agent_tool_result_from_another_begin_is_ignored(self):
        own = _request()
        other = copy.deepcopy(own)
        other["requestId"] = "r0-other-cycle"
        other["begin"]["runId"] = 124
        contracts.validate_request(other)
        comments = [
            {"id": 100, "author_association": "OWNER", "user": {"login": "EAKerber"}, "body": "begin"},
            _owner_comment(101, trace_collect.AGENT_TOOL_REQUEST_MARKER, own),
            _owner_comment(102, trace_collect.AGENT_TOOL_REQUEST_MARKER, other),
            _bot_comment(
                103,
                trace_collect.AGENT_TOOL_RESULT_MARKER,
                {
                    "requestHash": stable_hash(other),
                    "begin": copy.deepcopy(other["begin"]),
                    "actor": copy.deepcopy(ACTOR),
                    "status": "PASS",
                    "blockers": [],
                },
            ),
            _bot_comment(
                104,
                trace_collect.AGENT_TOOL_RESULT_MARKER,
                {
                    "requestHash": stable_hash(own),
                    "begin": copy.deepcopy(BEGIN),
                    "actor": copy.deepcopy(ACTOR),
                    "status": "PASS",
                    "blockers": [],
                },
            ),
            {"id": 200, "author_association": "OWNER", "user": {"login": "EAKerber"}, "body": "close"},
        ]

        trace = trace_collect.build_trace(comments, _manifest(), close_comment_id=200)

        self.assertEqual(trace["traceStatus"], "PASS")
        self.assertEqual(trace["summary"]["attemptCount"], 1)
        self.assertEqual(trace["attempts"][0]["requestHash"], stable_hash(own))
        self.assertEqual(trace["attempts"][0]["resultCommentId"], 104)

    def test_stabilization_cannot_observe_a_result_after_the_close_boundary(self):
        comments = _comments_with_result_after_close()
        fetch = Mock(return_value=comments)
        sleep = Mock()

        with self.assertRaisesRegex(RuntimeError, "EXECUTION_TRACE_INCOMPLETE"):
            hosted_agent_cycle_trace.prepare_close_stabilized(
                _close_command(),
                {"issueNumber": 145, "commentId": 200},
                _manifest(),
                {},
                repository="EAKerber/MobiliPresenter",
                fetch_comments=fetch,
                sleep=sleep,
                attempts=3,
                delay_seconds=0,
            )

        self.assertEqual(fetch.call_count, 3)
        self.assertEqual(sleep.call_count, 2)

    def test_workflow_concurrency_is_partitioned_by_carrier(self):
        cycle = (ROOT / ".github/workflows/hosted-agent-cycle.yml").read_text(encoding="utf-8")
        tool = (ROOT / ".github/workflows/hosted-agent-tool.yml").read_text(encoding="utf-8")
        lease = (ROOT / ".github/workflows/hosted-agent-write-lease.yml").read_text(encoding="utf-8")
        remote = (ROOT / ".github/workflows/remote-canonical-execution.yml").read_text(encoding="utf-8")

        self.assertNotIn("\nconcurrency:\n", cycle)
        self.assertIn("group: hosted-agent-tool-${{ github.event.issue.number }}", tool)
        self.assertIn("group: hosted-agent-write-lease-${{ github.event.issue.number }}", lease)
        self.assertIn("group: remote-canonical-execution-", remote)

    def test_mutation_dispatch_has_no_sequence_or_dependency_contract(self):
        self.assertNotIn("sequence", mutation_dispatch.FIELDS)
        self.assertNotIn("dependsOn", mutation_dispatch.FIELDS)
        self.assertNotIn("resourceKey", mutation_dispatch.FIELDS)


if __name__ == "__main__":
    unittest.main()
