from __future__ import annotations

import copy
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tools.agent_tools import dispatch_host
from tools.canonical import stable_hash


HOST_SHA = "a" * 40
HOSTED_RUN_ID = 456
REQUEST_HASH = "b" * 64
DISPATCH_HASH = "c" * 64
EXPECTED_HEAD = "d" * 40
CYCLE_INSTANCE_ID = "cycle-instance-" + "1" * 24
ACTOR = {
    "role": "manager-gitops",
    "workerId": "manager-gitops-a",
    "sessionId": "session-1",
}
BEGIN = {"runId": 123, "sourceSha": HOST_SHA, "contextHash": "e" * 64}


def bundle():
    request = {
        "requestId": "agent-tool-test",
        "begin": copy.deepcopy(BEGIN),
        "actor": copy.deepcopy(ACTOR),
        "toolId": "git.files.mutate",
    }
    plan = {
        "target": {"branch": "work/operations/test"},
    }
    dispatch = {
        "cycleInstanceId": CYCLE_INSTANCE_ID,
        "dispatchHash": DISPATCH_HASH,
        "requestHash": REQUEST_HASH,
        "begin": copy.deepcopy(BEGIN),
        "actor": copy.deepcopy(ACTOR),
        "source": {
            "issueNumber": 145,
            "requestCommentId": 101,
            "hostedRunId": HOSTED_RUN_ID,
            "semanticHostSha": HOST_SHA,
        },
        "command": {
            "expected": {"branchHead": EXPECTED_HEAD},
        },
    }
    return {
        "request": request,
        "plan": plan,
        "proofSet": {},
        "dispatch": dispatch,
        "context": {},
        "manifest": {},
    }


def attempt(dispatch, *, run_id=900):
    core = {
        "schemaVersion": dispatch_host.ATTEMPT_SCHEMA,
        "dispatchHash": dispatch["dispatchHash"],
        "requestHash": dispatch["requestHash"],
        "hostSha": dispatch["source"]["semanticHostSha"],
        "runId": run_id,
        "status": "STARTED",
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**core, "attemptHash": stable_hash(core)}


def bot_comment(marker, payload):
    return {
        "id": 500,
        "user": {"login": "github-actions[bot]"},
        "body": marker + "\n```json\n" + json.dumps(payload) + "\n```",
    }


class FakeTransport:
    def __init__(self):
        self.calls = []

    def request(self, method, endpoint, *, payload=None, include_headers=False):
        self.calls.append((method.upper(), endpoint, copy.deepcopy(payload)))
        return SimpleNamespace(body=json.dumps({}))


class AgentToolDispatchHostTests(unittest.TestCase):
    @patch("tools.agent_tools.dispatch_host.validate_bundle")
    @patch("tools.agent_tools.dispatch_host.hosted_issue_bus.list_comments")
    @patch("tools.agent_tools.dispatch_host.mutation_host.observe_branch_head", return_value=EXPECTED_HEAD)
    @patch("tools.agent_tools.dispatch_host.mutation_dispatch.build_execution_result")
    @patch("tools.agent_tools.dispatch_host.admission.collect_guard_proofs")
    def test_prior_attempt_without_terminal_is_unknown_and_never_reproofs_or_writes(
        self, collect, build_result, observe, comments, validate_bundle
    ):
        value = bundle()
        comments.return_value = [
            bot_comment(dispatch_host.ATTEMPT_MARKER, attempt(value["dispatch"]))
        ]
        build_result.return_value = {
            "status": "UNKNOWN",
            "blockers": ["AGENT_TOOL_MUTATION_PRIOR_ATTEMPT_WITHOUT_TERMINAL"],
        }
        with patch("tools.agent_tools.dispatch_host._hosted_terminal", return_value={"status": "UNKNOWN"}):
            result = dispatch_host.inspect_protocol(
                value,
                host_sha=HOST_SHA,
                hosted_run_id=HOSTED_RUN_ID,
                run_id=901,
                transport=FakeTransport(),
            )
        self.assertEqual(result["state"], "PRIOR_ATTEMPT_UNKNOWN")
        self.assertEqual(result["terminal"]["status"], "UNKNOWN")
        collect.assert_not_called()
        build_result.assert_called_once()

    @patch("tools.agent_tools.dispatch_host.validate_bundle")
    @patch("tools.agent_tools.dispatch_host.hosted_issue_bus.list_comments")
    @patch("tools.agent_tools.dispatch_host.mutation_host.observe_branch_head", return_value=EXPECTED_HEAD)
    @patch("tools.agent_tools.dispatch_host.mutation_dispatch.build_execution_result")
    @patch("tools.agent_tools.dispatch_host.admission.collect_guard_proofs")
    def test_same_request_hash_prior_attempt_fences_even_when_dispatch_changed(
        self, collect, build_result, observe, comments, validate_bundle
    ):
        value = bundle()
        prior_dispatch = copy.deepcopy(value["dispatch"])
        prior_dispatch["dispatchHash"] = "9" * 64
        prior_dispatch["source"]["requestCommentId"] = 99
        prior_dispatch["source"]["hostedRunId"] = 455
        comments.return_value = [
            bot_comment(dispatch_host.ATTEMPT_MARKER, attempt(prior_dispatch, run_id=899))
        ]
        build_result.return_value = {
            "status": "UNKNOWN",
            "blockers": ["AGENT_TOOL_MUTATION_PRIOR_ATTEMPT_WITHOUT_TERMINAL"],
        }
        with patch("tools.agent_tools.dispatch_host._hosted_terminal", return_value={"status": "UNKNOWN"}):
            result = dispatch_host.inspect_protocol(
                value,
                host_sha=HOST_SHA,
                hosted_run_id=HOSTED_RUN_ID,
                run_id=901,
                transport=FakeTransport(),
            )
        self.assertEqual("PRIOR_ATTEMPT_UNKNOWN", result["state"])
        collect.assert_not_called()
        build_result.assert_called_once()

    @patch("tools.agent_tools.dispatch_host.validate_bundle")
    @patch("tools.agent_tools.dispatch_host.hosted_issue_bus.list_comments")
    @patch("tools.agent_tools.dispatch_host.admission.collect_guard_proofs")
    def test_existing_terminal_short_circuits_without_reproof_or_new_attempt(
        self, collect, comments, validate_bundle
    ):
        value = bundle()
        terminal = {
            "requestHash": REQUEST_HASH,
            "begin": copy.deepcopy(BEGIN),
            "actor": copy.deepcopy(ACTOR),
            "status": "PASS",
        }
        comments.return_value = [
            bot_comment("MOBILIPRESENTER_AGENT_TOOL_RESULT_V0_1", terminal)
        ]
        result = dispatch_host.inspect_protocol(
            value,
            host_sha=HOST_SHA,
            hosted_run_id=HOSTED_RUN_ID,
            run_id=901,
            transport=FakeTransport(),
        )
        self.assertEqual(result["state"], "TERMINAL_EXISTS")
        self.assertEqual(result["terminal"], terminal)
        collect.assert_not_called()

    @patch("tools.agent_tools.dispatch_host.contracts.validate_request", return_value={})
    @patch("tools.agent_tools.dispatch_host.contracts.validate_plan", return_value={})
    @patch("tools.agent_tools.dispatch_host.admission.guard_proofs.validate_proof_set")
    @patch("tools.agent_tools.dispatch_host.mutation_dispatch.validate_dispatch")
    @patch("tools.agent_tools.dispatch_host.hosted_agent_tool.validate_begin_binding")
    @patch("tools.agent_tools.dispatch_host.contracts.request_hash", return_value=REQUEST_HASH)
    def test_originating_hosted_run_id_is_part_of_bundle_provenance(
        self, request_hash, begin_binding, validate_dispatch, validate_proofs,
        validate_plan, validate_request
    ):
        value = bundle()
        value["manifest"] = {"cycleInstanceId": CYCLE_INSTANCE_ID}
        validate_dispatch.return_value = value["dispatch"]
        validate_proofs.return_value = {
            "proofs": {
                "agent-write-lifecycle-bound": {
                    "cycleInstanceId": CYCLE_INSTANCE_ID,
                }
            }
        }
        with self.assertRaisesRegex(RuntimeError, "AGENT_TOOL_DISPATCH_HOSTED_RUN_MISMATCH"):
            dispatch_host.validate_bundle(
                value,
                host_sha=HOST_SHA,
                hosted_run_id=HOSTED_RUN_ID + 1,
                transport=FakeTransport(),
            )

    @patch("tools.agent_tools.dispatch_host.validate_bundle")
    @patch("tools.agent_tools.dispatch_host.hosted_issue_bus.get_comment")
    @patch("tools.agent_tools.dispatch_host.validate_attempt")
    @patch("tools.agent_tools.dispatch_host.mutation_host.execute_plan")
    @patch("tools.agent_tools.dispatch_host.mutation_dispatch.build_execution_result")
    @patch("tools.agent_tools.dispatch_host._hosted_terminal")
    def test_hosted_execute_delegates_to_shared_mutation_host(
        self, hosted_terminal, build_result, execute_plan, validate_attempt,
        comment, validate_bundle
    ):
        value = bundle()
        current_attempt = attempt(value["dispatch"])
        comment.return_value = bot_comment(
            dispatch_host.ATTEMPT_MARKER, current_attempt
        )
        execute_plan.return_value = {
            "status": "PASS",
            "blockers": [],
            "executionProofSet": {"proofSetHash": "f" * 64},
            "remoteReceipt": {"receiptHash": "1" * 64},
            "mutableCallCount": 3,
            "observedBranchHead": "9" * 40,
        }
        build_result.return_value = {"status": "PASS", "blockers": []}
        hosted_terminal.return_value = {"status": "PASS"}
        result = dispatch_host.execute_dispatch(
            value,
            host_sha=HOST_SHA,
            hosted_run_id=HOSTED_RUN_ID,
            run_id=900,
            attempt_comment_id=500,
            transport=FakeTransport(),
        )
        self.assertEqual(result["status"], "PASS")
        execute_plan.assert_called_once()
        kwargs = execute_plan.call_args.kwargs
        self.assertEqual(
            kwargs["lifecycle_context"],
            {
                "cycleInstanceId": CYCLE_INSTANCE_ID,
                "issueNumber": 145,
                "beforeCommentId": None,
            },
        )
        self.assertEqual(kwargs["source"]["kind"], "hosted-comment")
        build_kwargs = build_result.call_args.kwargs
        self.assertEqual(build_kwargs["mutable_call_count"], 3)
        self.assertEqual(build_kwargs["observed_branch_head"], "9" * 40)

    @patch("tools.agent_tools.dispatch_host.validate_bundle")
    @patch("tools.agent_tools.dispatch_host.hosted_issue_bus.get_comment")
    @patch("tools.agent_tools.dispatch_host.validate_attempt")
    @patch("tools.agent_tools.dispatch_host.mutation_host.execute_plan")
    @patch("tools.agent_tools.dispatch_host.mutation_dispatch.build_execution_result")
    @patch("tools.agent_tools.dispatch_host._hosted_terminal")
    def test_shared_host_blocked_outcome_preserves_hosted_terminal_shape(
        self, hosted_terminal, build_result, execute_plan, validate_attempt,
        comment, validate_bundle
    ):
        value = bundle()
        comment.return_value = bot_comment(
            dispatch_host.ATTEMPT_MARKER, attempt(value["dispatch"])
        )
        execute_plan.return_value = {
            "status": "BLOCKED",
            "blockers": ["LEASE_STALE"],
            "executionProofSet": None,
            "remoteReceipt": None,
            "mutableCallCount": 0,
            "observedBranchHead": EXPECTED_HEAD,
        }
        build_result.return_value = {
            "status": "BLOCKED",
            "blockers": ["LEASE_STALE"],
        }
        hosted_terminal.return_value = {
            "status": "BLOCKED",
            "blockers": ["LEASE_STALE"],
        }
        result = dispatch_host.execute_dispatch(
            value,
            host_sha=HOST_SHA,
            hosted_run_id=HOSTED_RUN_ID,
            run_id=900,
            attempt_comment_id=500,
            transport=FakeTransport(),
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(
            build_result.call_args.kwargs["blockers"], ["LEASE_STALE"]
        )


if __name__ == "__main__":
    unittest.main()
