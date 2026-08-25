from __future__ import annotations

import copy
import json
import unittest
from unittest.mock import patch

from tools import hosted_agent_tool as hosted
from tools.agent_tools import contracts
from tools.canonical import stable_hash


def request(tool_id="project.inspect"):
    begin = {"runId": 123, "sourceSha": "a" * 40, "contextHash": "b" * 64}
    actor = {"role": "manager-gitops", "workerId": "manager-gitops-a", "sessionId": "session-1"}
    target = {}
    input_value = {}
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
        result = {"status": "PASS", "blockers": [], "resultHash": "d" * 64}
        resolve.return_value = {"plan": plan, "result": result}
        payload = hosted.execute_request(value, manifest(value), {})
        self.assertEqual(payload["status"], "PASS")
        self.assertFalse(payload["semanticAuthority"])
        self.assertFalse(payload["authorizesMutation"])
        core = {key: item for key, item in payload.items() if key != "hostedResultHash"}
        self.assertEqual(payload["hostedResultHash"], stable_hash(core))
        resolve.assert_called_once()

    @patch("tools.hosted_agent_tool.validate_begin_binding")
    @patch("tools.hosted_agent_tool.resolver.resolve_request")
    def test_plan_only_tool_cannot_report_executed_mutation(self, resolve, validate_binding):
        value = request("git.file.create")
        resolve.return_value = {
            "plan": {"mode": "plan-only", "planHash": "c" * 64},
            "result": {"status": "PASS", "blockers": [], "resultHash": "d" * 64},
        }
        with self.assertRaisesRegex(RuntimeError, "MUTATION_MODE_VIOLATION"):
            hosted.execute_request(value, manifest(value), {})

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
