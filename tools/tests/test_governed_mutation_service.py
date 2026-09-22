from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import governed_mutation_service as service
from tools.canonical import stable_hash


REQUEST = {
    "schemaVersion": service.REQUEST_SCHEMA,
    "workId": "e4-counter-canary",
    "branch": "work/operations/e4-counter-canary",
    "changes": [
        {"path": "docs/e4-a.txt", "content": "a\n"},
        {"path": "docs/e4-b.txt", "content": "b\n"},
    ],
    "message": "E4 governed mutation canary",
    "semanticAuthority": False,
    "authorizesMutation": False,
}


def handle():
    body = {
        "schemaVersion": "AgentCycleHandle 0.1",
        "repository": service.REPOSITORY,
        "cycleId": "cycle-" + "1" * 20,
        "cycleInstanceId": "cycle-instance-" + "2" * 24,
        "context": {
            "schemaVersion": "AgentContext 0.1",
            "contextHash": "3" * 64,
        },
        "actor": {
            "role": "manager-gitops",
            "workerId": "manager-gitops-a",
            "sessionId": "session-e4",
        },
        "resumeToken": "hosted-v1:{}",
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**body, "handleHash": stable_hash(body)}


class GovernedMutationServiceTests(unittest.TestCase):
    def test_request_has_only_four_semantic_inputs(self):
        value = service.validate_request(REQUEST)
        self.assertEqual(
            set(value) - {
                "schemaVersion", "semanticAuthority", "authorizesMutation"
            },
            {"workId", "branch", "changes", "message"},
        )

    @patch("tools.governed_mutation_service._semantic_host_supports_service", return_value=True)
    @patch("tools.governed_mutation_service.hosted_cycle_handle.decode_handle")
    @patch("tools.governed_mutation_service.agent_reentry_guidance.observe_turnover_context")
    def test_prepare_reuses_exact_cycle_without_creating_authority(
        self, observe, decode, supports
    ):
        h = handle()
        locator = {
            "artifactName": "agent-cycle-begin-123",
            "runId": 123,
            "sourceSha": "4" * 40,
            "issueNumber": 145,
            "beginCommentId": 200,
            "contextHash": "3" * 64,
            "cycleInstanceId": "cycle-instance-" + "2" * 24,
        }
        observe.return_value = {
            "work": {
                "id": REQUEST["workId"],
                "branch": REQUEST["branch"],
                "status": "IN_PROGRESS",
            },
            "reentry": {"nextSafeAction": "RESUME_EXACT_CYCLE"},
            "handle": h,
            "actor": h["actor"],
            "currentIntent": "governed-mutation",
            "busIssueNumber": 145,
        }
        decode.return_value = (h, locator)
        value = service.prepare_request(REQUEST, transport=object())
        self.assertEqual(value["state"], "READY")
        self.assertEqual(value["nextSafeAction"], "EXECUTE_MUTATION")
        self.assertEqual(value["locator"], locator)
        self.assertEqual(supports.call_args.args[0], "4" * 40)

    @patch("tools.governed_mutation_service.agent_reentry_guidance.observe_turnover_context")
    def test_prepare_blocks_when_canonical_reentry_requires_new_cycle(self, observe):
        observe.return_value = {
            "work": {
                "id": REQUEST["workId"],
                "branch": REQUEST["branch"],
                "status": "IN_PROGRESS",
            },
            "reentry": {"nextSafeAction": "BEGIN_NEW_CYCLE"},
            "handle": None,
            "actor": None,
            "currentIntent": None,
            "busIssueNumber": 145,
        }
        value = service.prepare_request(REQUEST, transport=object())
        self.assertEqual(value["state"], "BLOCKED")
        self.assertEqual(value["nextSafeAction"], "BEGIN_NEW_CYCLE")
        self.assertIn("GOVERNED_MUTATION_EXACT_CYCLE_REQUIRED", value["blockers"])

    @patch("tools.governed_mutation_service.agent_reentry_guidance.observe_turnover_context")
    def test_prepare_blocks_work_branch_mismatch(self, observe):
        observe.return_value = {
            "work": {
                "id": REQUEST["workId"],
                "branch": "work/operations/other",
                "status": "IN_PROGRESS",
            },
            "reentry": {"nextSafeAction": "RESUME_EXACT_CYCLE"},
            "handle": handle(),
            "actor": None,
            "currentIntent": "governed-mutation",
            "busIssueNumber": 145,
        }
        value = service.prepare_request(REQUEST, transport=object())
        self.assertEqual(value["state"], "BLOCKED")
        self.assertEqual(value["nextSafeAction"], "ALIGN_WORK_BRANCH")

    def test_blocked_result_is_compact_and_windows_are_pull_based(self):
        preparation = service._preparation(
            REQUEST,
            state="BLOCKED",
            blockers=["GOVERNED_MUTATION_EXACT_CYCLE_REQUIRED"],
            next_safe_action="BEGIN_NEW_CYCLE",
            work={"id": REQUEST["workId"], "branch": REQUEST["branch"]},
            reentry={"nextSafeAction": "BEGIN_NEW_CYCLE"},
            handle=None,
            locator=None,
            bus_issue_number=145,
            semantic_host_supported=None,
        )
        with tempfile.TemporaryDirectory() as tmp:
            result = service.result_from_preparation(
                REQUEST,
                preparation,
                run_id=900,
                run_attempt=1,
                evidence_dir=tmp,
            )
            self.assertEqual(result["status"], "BLOCKED")
            self.assertNotIn("plan", result)
            self.assertNotIn("proofSet", result)
            self.assertNotIn("receipt", result)
            self.assertIsNotNone(result["windows"]["work"])
            work_window = service.inspect_window(
                result, window="work", evidence_dir=tmp
            )
            self.assertEqual(work_window["work"]["id"], REQUEST["workId"])

    @patch("tools.governed_mutation_service.mutation_host.execute_plan")
    @patch("tools.governed_mutation_service.resolver.resolve_request")
    @patch("tools.governed_mutation_service.hosted_agent_tool.derive_handle_request")
    @patch("tools.governed_mutation_service.hosted_cycle_handle.bind")
    @patch("tools.governed_mutation_service.hosted_agent_cycle.validate_begin_manifest")
    def test_execute_delegates_to_shared_host_and_materializes_kitchen_windows(
        self, validate_manifest, bind, derive, resolve, execute_plan
    ):
        h = handle()
        locator = {
            "artifactName": "agent-cycle-begin-123",
            "runId": 123,
            "sourceSha": "4" * 40,
            "issueNumber": 145,
            "beginCommentId": 200,
            "contextHash": "3" * 64,
            "cycleInstanceId": "cycle-instance-" + "2" * 24,
        }
        preparation = service._preparation(
            REQUEST,
            state="READY",
            blockers=[],
            next_safe_action="EXECUTE_MUTATION",
            work={"id": REQUEST["workId"], "branch": REQUEST["branch"]},
            reentry={"nextSafeAction": "RESUME_EXACT_CYCLE"},
            handle=h,
            locator=locator,
            bus_issue_number=145,
            semantic_host_supported=True,
        )
        canonical_request = {
            "schemaVersion": "AgentToolRequest 0.1",
            "requestId": "agent-tool-" + "5" * 24,
            "begin": {"runId": 123, "sourceSha": "4" * 40, "contextHash": "3" * 64},
            "actor": h["actor"],
            "toolId": "git.files.mutate",
            "target": {"branch": REQUEST["branch"]},
            "input": {"changes": REQUEST["changes"], "message": REQUEST["message"]},
            "semanticAuthority": False,
            "authorizesMutation": False,
        }
        command = {
            "expected": {"branchHead": "6" * 40},
        }
        plan = {
            "mode": "mutation-execute",
            "status": "READY",
            "input": canonical_request["input"],
            "concrete": {"command": command},
        }
        derive.return_value = canonical_request
        resolve.return_value = {"plan": plan, "result": {}}
        bind.return_value = {"locator": locator}
        execute_plan.return_value = {
            "status": "PASS",
            "blockers": [],
            "executionProofSet": {"proofSetHash": "7" * 64},
            "remoteReceipt": {
                "aggregateReadback": {
                    "branchHead": "8" * 40,
                    "changedPaths": ["docs/e4-a.txt", "docs/e4-b.txt"],
                }
            },
            "observedBranchHead": "8" * 40,
        }
        with tempfile.TemporaryDirectory() as tmp:
            begin = Path(tmp) / "begin"
            begin.mkdir()
            (begin / "context.json").write_text(
                json.dumps({"contextHash": "3" * 64}), encoding="utf-8"
            )
            (begin / "manifest.json").write_text(
                json.dumps(
                    {
                        "source": {"sourceSha": "4" * 40},
                        "cycleInstanceId": "cycle-instance-" + "2" * 24,
                    }
                ),
                encoding="utf-8",
            )
            evidence = Path(tmp) / "evidence"
            result = service.execute_prepared(
                REQUEST,
                {"issueNumber": 145, "commentId": 300},
                preparation,
                begin_dir=begin,
                run_id=900,
                run_attempt=1,
                evidence_dir=evidence,
                transport=object(),
            )
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["summary"]["parentHead"], "6" * 40)
            self.assertEqual(result["summary"]["branchHead"], "8" * 40)
            self.assertEqual(result["nextSafeAction"], "CONTINUE")
            self.assertIsNotNone(result["windows"]["decision"])
            self.assertIsNotNone(result["windows"]["authority"])
            self.assertIsNotNone(result["windows"]["execution"])
            self.assertIsNotNone(result["windows"]["git"])
            kwargs = execute_plan.call_args.kwargs
            self.assertEqual(
                kwargs["lifecycle_context"],
                {
                    "cycleInstanceId": "cycle-instance-" + "2" * 24,
                    "issueNumber": 145,
                    "beforeCommentId": 300,
                },
            )

    def test_window_hash_tamper_fails_closed(self):
        preparation = service._preparation(
            REQUEST,
            state="BLOCKED",
            blockers=["X"],
            next_safe_action="RESOLVE_BLOCKERS",
            work={"id": REQUEST["workId"], "branch": REQUEST["branch"]},
            reentry={"nextSafeAction": "NONE"},
            handle=None,
            locator=None,
            bus_issue_number=145,
            semantic_host_supported=None,
        )
        with tempfile.TemporaryDirectory() as tmp:
            result = service.result_from_preparation(
                REQUEST, preparation, run_id=901, run_attempt=1, evidence_dir=tmp
            )
            member = result["windows"]["work"]["member"]
            Path(tmp, member).write_text('{"tampered":true}\n', encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "WINDOW_HASH_MISMATCH"):
                service.inspect_window(result, window="work", evidence_dir=tmp)


if __name__ == "__main__":
    unittest.main()
