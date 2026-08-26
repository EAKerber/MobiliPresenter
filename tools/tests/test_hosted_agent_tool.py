from __future__ import annotations

import copy
import json
import unittest
from unittest.mock import patch

from tools import hosted_agent_tool as hosted
from tools.agent_tools import contracts
from tools.canonical import stable_hash


def request(tool_id="project.inspect", *, target=None, input_value=None):
    begin = {"runId": 123, "sourceSha": "a" * 40, "contextHash": "b" * 64}
    actor = {"role": "manager-gitops", "workerId": "manager-gitops-a", "sessionId": "session-1"}
    target = {} if target is None else target
    input_value = {} if input_value is None else input_value
    return {
        "schemaVersion": contracts.REQUEST_SCHEMA,
        "requestId": contracts.deterministic_request_id(
            begin=begin, actor=actor, tool_id=tool_id, target=target, input_value=input_value
        ),
        "begin": begin,
        "actor": actor,
        "toolId": tool_id,
        "target": target,
        "input": input_value,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


def event(value):
    return {
        "issue": {"number": 145, "title": hosted.BUS_TITLE},
        "comment": {"id": 9001, "author_association": "OWNER", "body": hosted.REQUEST_MARKER + "\n" + json.dumps(value)},
        "repository": {"full_name": hosted.REPOSITORY},
    }


def manifest(value):
    return {
        "source": {"runId": 123, "sourceSha": "a" * 40, "issueNumber": 145, "commentId": 8001},
        "contextHash": "b" * 64,
        "actor": copy.deepcopy(value["actor"]),
        "cycleInstanceId": "cycle-instance-" + "c" * 24,
    }


class HostedAgentToolTests(unittest.TestCase):
    def test_parse_is_owner_only_and_request_contract_closed(self):
        value, meta = hosted.parse_event(event(request()))
        self.assertEqual(value["toolId"], "project.inspect")
        self.assertEqual(meta, {"issueNumber": 145, "commentId": 9001})
        bad_event = event(request())
        bad_event["comment"]["author_association"] = "MEMBER"
        with self.assertRaisesRegex(RuntimeError, "ACTOR_FORBIDDEN"):
            hosted.parse_event(bad_event)

    @patch("tools.hosted_agent_tool.hosted_agent_cycle.validate_begin_manifest")
    def test_begin_binding_pins_run_source_context_and_actor(self, validate_manifest):
        value = request()
        hosted.validate_begin_binding(value, manifest(value), {})
        bad = copy.deepcopy(value)
        bad["begin"]["sourceSha"] = "c" * 40
        with self.assertRaisesRegex(RuntimeError, "BEGIN_REF_MISMATCH"):
            hosted.validate_begin_binding(bad, manifest(value), {})
        bad = copy.deepcopy(value)
        bad["actor"]["sessionId"] = "other"
        with self.assertRaisesRegex(RuntimeError, "CYCLE_IDENTITY_MISMATCH"):
            hosted.validate_begin_binding(bad, manifest(value), {})

    @patch("tools.hosted_agent_tool.validate_begin_binding")
    @patch("tools.hosted_agent_tool.resolver.resolve_request")
    def test_read_only_execution_returns_hash_bound_non_authoritative_result(self, resolve, validate_binding):
        value = request()
        plan = {"mode": "read-only-execute", "planHash": "c" * 64}
        resolve.side_effect = [
            {"plan": plan, "result": {"status": "PLANNED", "blockers": [], "resultHash": "e" * 64}},
            {"plan": plan, "result": {"status": "PASS", "blockers": [], "resultHash": "d" * 64}},
        ]
        payload = hosted.execute_request(value, manifest(value), {})
        self.assertEqual(payload["status"], "PASS")
        self.assertFalse(payload["semanticAuthority"])
        self.assertFalse(payload["authorizesMutation"])
        core = {key: item for key, item in payload.items() if key != "hostedResultHash"}
        self.assertEqual(payload["hostedResultHash"], stable_hash(core))
        self.assertEqual(resolve.call_count, 2)
        self.assertFalse(resolve.call_args_list[0].kwargs["execute"])
        self.assertTrue(resolve.call_args_list[1].kwargs["execute"])

    @patch("tools.hosted_agent_tool.validate_begin_binding")
    @patch("tools.hosted_agent_tool.resolver.resolve_request")
    def test_plan_only_tool_cannot_report_executed_mutation(self, resolve, validate_binding):
        value = request("git.files.mutate")
        resolve.return_value = {
            "plan": {"mode": "plan-only", "planHash": "c" * 64},
            "result": {"status": "PASS", "blockers": [], "resultHash": "d" * 64},
        }
        with self.assertRaisesRegex(RuntimeError, "MUTATION_MODE_VIOLATION"):
            hosted.execute_request(value, manifest(value), {})

    @patch("tools.hosted_agent_tool.validate_begin_binding")
    @patch("tools.hosted_agent_tool.mutation_dispatch.build_dispatch")
    @patch("tools.hosted_agent_tool.admission.assert_execution_admitted")
    @patch("tools.hosted_agent_tool.admission.collect_guard_proofs")
    @patch("tools.hosted_agent_tool.resolver.resolve_request")
    def test_mutation_execute_emits_dispatch_without_terminal_result(
        self, resolve, collect, admitted, build_dispatch, validate_binding
    ):
        value = request(
            "git.files.mutate",
            target={"branch": "work/operations/at3b"},
            input_value={
                "changes": [{"path": "docs/at3b.txt", "content": "x"}],
                "message": "AT3B",
            },
        )
        plan = {
            "mode": "mutation-execute",
            "planHash": "c" * 64,
            "actor": copy.deepcopy(value["actor"]),
        }
        proof_set = {"proofSetHash": "d" * 64}
        dispatch = {"schemaVersion": "AgentToolMutationDispatch 0.1", "dispatchHash": "e" * 64}
        resolve.return_value = {
            "plan": plan,
            "result": {"status": "PLANNED", "blockers": [], "resultHash": "f" * 64},
        }
        collect.return_value = proof_set
        build_dispatch.return_value = dispatch

        outcome = hosted.prepare_request(
            value,
            manifest(value),
            {},
            meta={"issueNumber": 145, "commentId": 9001},
            hosted_run_id=456,
        )
        self.assertEqual(outcome["kind"], "dispatch")
        self.assertEqual(outcome["dispatch"], dispatch)
        self.assertNotIn("result", outcome)
        admitted.assert_called_once_with(plan, proof_set)
        build_dispatch.assert_called_once_with(
            plan,
            proof_set,
            cycle_instance_id="cycle-instance-" + "c" * 24,
            issue_number=145,
            request_comment_id=9001,
            hosted_run_id=456,
        )
        self.assertFalse(resolve.call_args.kwargs["execute"])

    def test_failure_preserves_raw_request_identity_when_contract_is_invalid(self):
        value = request()
        value["requestId"] = "INVALID"
        payload = hosted.failure_payload(RuntimeError("AGENT_TOOL_REQUEST_ID_INVALID"), value)
        self.assertEqual(payload["status"], "BLOCKED")
        self.assertEqual(payload["requestHash"], stable_hash(value))
        self.assertEqual(payload["begin"], value["begin"])
        self.assertEqual(payload["actor"], value["actor"])


if __name__ == "__main__":
    unittest.main()
