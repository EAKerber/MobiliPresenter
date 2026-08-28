from __future__ import annotations

import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import agent_failure
from tools import hosted_agent_cycle as hosted
from tools.canonical import stable_hash


def begin_command():
    return {
        "schemaVersion": hosted.COMMAND_SCHEMA,
        "requestId": "hosted-cycle-begin-1",
        "action": "begin",
        "actor": {
            "role": "manager-gitops",
            "workerId": "manager-gitops-a",
            "sessionId": "session-1",
        },
        "declaredIntent": "inspect-and-plan",
        "machineScope": "live",
        "begin": None,
        "evidenceCommentIds": [],
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


def close_command():
    value = begin_command()
    value["requestId"] = "hosted-cycle-close-1"
    value["action"] = "close"
    value["begin"] = {
        "runId": 123,
        "sourceSha": "a" * 40,
        "contextHash": "b" * 64,
    }
    return value


def event(command, *, association="OWNER", title=hosted.BUS_TITLE):
    return {
        "issue": {"number": 145, "title": title},
        "comment": {
            "id": 9001,
            "author_association": association,
            "body": hosted.REQUEST_MARKER + "\n" + json.dumps(command),
        },
        "repository": {"full_name": hosted.REPOSITORY},
    }


class HostedAgentCycleTests(unittest.TestCase):
    def test_command_is_closed_live_and_non_authoritative(self):
        command = begin_command()
        self.assertEqual(command, hosted.validate_command(command))
        self.assertEqual(hosted.command_hash(command), stable_hash(command))
        for key in ("semanticAuthority", "authorizesMutation"):
            bad = copy.deepcopy(command)
            bad[key] = True
            with self.assertRaisesRegex(RuntimeError, "MUST_NOT_AUTHORIZE"):
                hosted.validate_command(bad)
        bad = copy.deepcopy(command)
        bad["machineScope"] = "base"
        with self.assertRaisesRegex(RuntimeError, "SCOPE_MUST_BE_LIVE"):
            hosted.validate_command(bad)

    def test_begin_and_close_shapes_are_distinct(self):
        hosted.validate_command(begin_command())
        hosted.validate_command(close_command())
        bad = begin_command()
        bad["evidenceCommentIds"] = [42]
        with self.assertRaisesRegex(RuntimeError, "BEGIN_COMMAND_INVALID"):
            hosted.validate_command(bad)
        bad = close_command()
        bad["begin"] = None
        with self.assertRaisesRegex(RuntimeError, "BEGIN_REF_INVALID"):
            hosted.validate_command(bad)

    def test_issue_transport_is_owner_only_and_raw_json(self):
        command, meta = hosted.parse_event(event(begin_command()))
        self.assertEqual(command["action"], "begin")
        self.assertEqual(meta, {"issueNumber": 145, "commentId": 9001})
        with self.assertRaisesRegex(RuntimeError, "ACTOR_FORBIDDEN"):
            hosted.parse_event(event(begin_command(), association="MEMBER"))
        fenced = event(begin_command())
        fenced["comment"]["body"] = hosted.REQUEST_MARKER + "\n```json\n{}\n```"
        with self.assertRaisesRegex(RuntimeError, "JSON_INVALID"):
            hosted.parse_event(fenced)

    @patch("tools.hosted_agent_cycle.agent_cycle.validate_context")
    @patch("tools.hosted_agent_cycle._run_agent")
    def test_begin_delegates_to_canonical_agent_and_preserves_hash_bound_manifest(
        self, run_agent, validate_context
    ):
        context = {
            "cycleId": "cycle-" + "c" * 20,
            "contextHash": "d" * 64,
            "status": "READY",
        }
        run_agent.return_value = (0, context)
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"GITHUB_SHA": "a" * 40, "GITHUB_RUN_ID": "123"},
            clear=False,
        ):
            result = hosted.begin_from_envelope(
                begin_command(),
                {"issueNumber": 145, "commentId": 9001},
                context_path=f"{tmp}/context.json",
                manifest_path=f"{tmp}/manifest.json",
            )
            args = run_agent.call_args.args[0]
            self.assertEqual(args[0], "begin")
            self.assertIn("--machine-scope", args)
            self.assertEqual(args[args.index("--machine-scope") + 1], "live")
            manifest = json.loads(Path(f"{tmp}/manifest.json").read_text())
            self.assertEqual(manifest["schemaVersion"], hosted.BEGIN_MANIFEST_SCHEMA)
            self.assertEqual(manifest["contextHash"], context["contextHash"])
            self.assertEqual(manifest["source"]["sourceSha"], "a" * 40)
            self.assertEqual(manifest["artifactName"], "agent-cycle-begin-123")
            self.assertEqual(manifest["carrierFeatures"], hosted.CURRENT_FEATURES)
            self.assertTrue(manifest["cycleInstanceId"].startswith("cycle-instance-"))
            self.assertTrue(hosted._manifest_requires_trace(manifest))
            self.assertTrue(hosted._manifest_requires_write_lifecycle(manifest))
            self.assertEqual(result["cycleInstanceId"], manifest["cycleInstanceId"])
            self.assertEqual(result["carrierFeatures"], hosted.CURRENT_FEATURES)
            self.assertEqual(result["status"], "READY")
            self.assertFalse(result["authorizesMutation"])
            validate_context.assert_called()

    @patch("tools.hosted_agent_cycle.agent_cycle.validate_context")
    @patch("tools.hosted_agent_cycle._run_agent")
    def test_begin_failure_preserves_structured_blockers_root_to_wrapper(
        self, run_agent, validate_context
    ):
        run_agent.return_value = (
            2,
            {
                "status": "BLOCKED",
                "blockingUnknowns": [
                    "ROOT_PROVIDER_SCOPE_MISSING",
                    "ROUTINE_INSPECTION_FAIL",
                ],
            },
        )
        with self.assertRaises(hosted.HostedAgentCycleError) as raised:
            hosted.begin_from_envelope(
                begin_command(),
                {"issueNumber": 145, "commentId": 9001},
                context_path="/unused/context.json",
                manifest_path="/unused/manifest.json",
            )
        core = raised.exception.failure_core
        self.assertIsNotNone(core)
        self.assertEqual(
            [
                "ROOT_PROVIDER_SCOPE_MISSING",
                "ROUTINE_INSPECTION_FAIL",
                "HOSTED_AGENT_BEGIN_NOT_READY",
            ],
            [item["code"] for item in core["causes"]],
        )
        self.assertFalse(core["lossyProjection"])
        self.assertEqual("BEGIN", core["phase"])
        validate_context.assert_called()

    def test_legacy_begin_manifest_remains_valid_without_trace_requirement(self):
        source = {
            "workflow": "hosted-agent-cycle",
            "sourceSha": "a" * 40,
            "runId": 123,
            "issueNumber": 145,
            "commentId": 9001,
        }
        core = {
            "schemaVersion": hosted.LEGACY_BEGIN_MANIFEST_SCHEMA,
            "requestId": "legacy-begin",
            "commandHash": "b" * 64,
            "actor": copy.deepcopy(begin_command()["actor"]),
            "declaredIntent": "inspect-and-plan",
            "machineScope": "live",
            "source": source,
            "artifactName": "agent-cycle-begin-123",
            "cycleId": "cycle-" + "c" * 20,
            "contextHash": "d" * 64,
            "status": "READY",
            "semanticAuthority": False,
            "authorizesMutation": False,
        }
        manifest = {**core, "manifestHash": stable_hash(core)}
        self.assertEqual(hosted.validate_begin_manifest(manifest), manifest)
        self.assertFalse(hosted._manifest_requires_trace(manifest))
        self.assertFalse(hosted._manifest_requires_write_lifecycle(manifest))

    @patch("tools.hosted_agent_cycle.remote_canonical_execution.validate_receipt")
    def test_remote_receipt_normalization_keeps_only_agent_close_evidence(self, validate):
        domain = {
            "evidence": {
                "kind": "transition-receipt",
                "request": {"transport": "not-close-evidence"},
                "plan": {"plan": 1},
                "receipt": {"receipt": 1},
            }
        }
        self.assertEqual(
            hosted.normalize_remote_evidence(domain),
            {
                "kind": "transition-receipt",
                "plan": {"plan": 1},
                "receipt": {"receipt": 1},
            },
        )
        git_plan = {
            "evidence": {
                "kind": "git-mutation-plan-readback",
                "plan": {"plan": 2},
                "observed": {"status": "PASS"},
            }
        }
        self.assertEqual(
            hosted.normalize_remote_evidence(git_plan),
            {
                "kind": "git-mutation-plan-readback",
                "plan": {"plan": 2},
                "observed": {"status": "PASS"},
            },
        )
        bundle = {
            "evidence": {
                "kind": "git-mutation-bundle-readback",
                "plan": {"ignored": True},
                "observed": {"ignored": True},
                "bundle": {"bundle": 3},
                "providerReadback": {"provider": 3},
                "bundleReadback": {"ignored": True},
            }
        }
        self.assertEqual(
            hosted.normalize_remote_evidence(bundle),
            {
                "kind": "git-mutation-bundle-readback",
                "bundle": {"bundle": 3},
                "providerReadback": {"provider": 3},
            },
        )

    @patch("tools.hosted_agent_cycle.validate_begin_manifest")
    def test_close_binding_pins_begin_source_context_identity_and_scope(self, validate_manifest):
        command = close_command()
        manifest = {
            "source": {"runId": 123, "sourceSha": "a" * 40},
            "contextHash": "b" * 64,
            "actor": copy.deepcopy(command["actor"]),
            "declaredIntent": command["declaredIntent"],
            "machineScope": "live",
        }
        hosted._validate_close_binding(command, manifest, {})
        bad = copy.deepcopy(command)
        bad["begin"]["sourceSha"] = "c" * 40
        with self.assertRaisesRegex(RuntimeError, "BEGIN_REF_MISMATCH"):
            hosted._validate_close_binding(bad, manifest, {})
        bad = copy.deepcopy(command)
        bad["actor"]["sessionId"] = "other"
        with self.assertRaisesRegex(RuntimeError, "CYCLE_IDENTITY_MISMATCH"):
            hosted._validate_close_binding(bad, manifest, {})

    def test_failure_shell_is_hash_bound_and_semantics_live_only_in_core(self):
        payload = hosted.failure_payload(
            hosted.HostedAgentCycleError("TEST_BLOCK"),
            begin_command(),
            phase="BEGIN",
        )
        self.assertEqual(payload["schemaVersion"], "HostedAgentCycleFailure 0.2")
        self.assertEqual(payload["status"], "BLOCKED")
        self.assertEqual(payload["requestId"], begin_command()["requestId"])
        self.assertEqual(payload["commandHash"], hosted.command_hash(begin_command()))
        self.assertNotIn("blockers", payload)
        self.assertNotIn("detail", payload)
        self.assertNotIn("semanticAuthority", payload)
        self.assertNotIn("authorizesMutation", payload)
        core = payload["failureCore"]
        self.assertEqual(["TEST_BLOCK"], [item["code"] for item in core["causes"]])
        self.assertTrue(core["readOnly"])
        self.assertFalse(core["semanticAuthority"])
        self.assertFalse(core["authorizesMutation"])
        self.assertEqual(core, agent_failure.normalize_failure(payload))
        body = {key: value for key, value in payload.items() if key != "failureHash"}
        self.assertEqual(payload["failureHash"], stable_hash(body))

    def test_invalid_command_cannot_break_failure_materialization(self):
        payload = hosted.failure_payload(
            hosted.HostedAgentCycleError("TEST_BLOCK"),
            {"requestId": "partial"},
            phase="PARSE",
        )
        self.assertIsNone(payload["requestId"])
        self.assertIsNone(payload["commandHash"])
        self.assertEqual("TEST_BLOCK", payload["failureCore"]["causes"][0]["code"])

    def test_unexpected_exception_text_is_not_promoted_to_semantics(self):
        payload = hosted.failure_payload(
            RuntimeError("FAKE_ROOT: human diagnostic"),
            phase="TRANSPORT",
        )
        self.assertEqual(
            ["HOSTED_AGENT_UNEXPECTED_FAILURE"],
            [item["code"] for item in payload["failureCore"]["causes"]],
        )
        self.assertNotIn("detail", payload)
        self.assertTrue(payload["failureCore"]["lossyProjection"])


if __name__ == "__main__":
    unittest.main()
