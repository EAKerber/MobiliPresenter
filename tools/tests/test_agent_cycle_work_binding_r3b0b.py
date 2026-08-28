from __future__ import annotations

import copy
import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tools import agent_cycle, continuation_remote, hosted_agent_cycle as hosted
from tools import project_machine, runtime_capabilities


WORK_ID = "m12-at3d-r3b0b-test"
ACTOR = {
    "role": "manager-gitops",
    "workerId": "manager-gitops-a",
    "sessionId": "r3b0b-test",
}


def _context(work_ref=None):
    machine = project_machine.inspect_local()
    runtime = runtime_capabilities.build_inspection(
        {"schemaVersion": runtime_capabilities.PROVIDER_OBSERVATIONS_SCHEMA, "providers": {}}
    )
    profile = agent_cycle.entry_profile("manager-gitops", "inspect-and-plan")
    return agent_cycle.build_context(
        role="manager-gitops",
        declared_intent="inspect-and-plan",
        lifecycle_phase=profile["lifecyclePhase"],
        objects=profile["objects"],
        operations=profile["operations"],
        scopes=profile["scope"],
        machine=machine,
        runtime_inspection=runtime,
        work_ref=work_ref,
    )


def _work_begin(work_ref=None):
    return {
        "schemaVersion": hosted.COMMAND_SCHEMA_V03,
        "requestId": "r3b0b-work-begin",
        "action": "begin",
        "actor": copy.deepcopy(ACTOR),
        "declaredIntent": "inspect-and-plan",
        "machineScope": "live",
        "workRef": copy.deepcopy(work_ref),
        "evidenceCommentIds": [],
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


def _event(command):
    return {
        "issue": {"number": 145, "title": hosted.BUS_TITLE},
        "comment": {
            "id": 9901,
            "author_association": "OWNER",
            "body": hosted.REQUEST_MARKER_V03 + "\n" + json.dumps(command),
        },
        "repository": {"full_name": hosted.REPOSITORY},
    }


class AgentCycleWorkBindingR3B0bTests(unittest.TestCase):
    def test_context_04_has_explicit_nullable_work_ref(self):
        context = _context()
        self.assertEqual("AgentCycleContext 0.4", context["schemaVersion"])
        self.assertIsNone(context["workRef"])
        self.assertEqual(context, agent_cycle.validate_context(context))

    def test_work_binding_changes_context_only_not_baseline_or_cycle_identity(self):
        unbound = _context()
        bound = agent_cycle.bind_work_ref(unbound, {"workId": WORK_ID})

        self.assertEqual({"workId": WORK_ID}, bound["workRef"])
        self.assertEqual(unbound["baseline"], bound["baseline"])
        self.assertEqual(unbound["cycleId"], bound["cycleId"])
        self.assertNotEqual(unbound["contextHash"], bound["contextHash"])
        self.assertEqual(bound, agent_cycle.validate_context(bound))

        with self.assertRaisesRegex(RuntimeError, "WORK_REF_REBIND_FORBIDDEN"):
            agent_cycle.bind_work_ref(bound, {"workId": "different-work"})

    def test_work_ref_is_closed_and_reuses_canonical_work_id_definition(self):
        self.assertEqual({"workId": WORK_ID}, agent_cycle.validate_work_ref({"workId": WORK_ID}))
        self.assertIsNone(agent_cycle.validate_work_ref(None))
        with self.assertRaisesRegex(RuntimeError, "WORK_REF_FIELDS_INVALID"):
            agent_cycle.validate_work_ref({"workId": WORK_ID, "status": "IN_PROGRESS"})
        with self.assertRaisesRegex(RuntimeError, "WORK_ID_INVALID"):
            agent_cycle.validate_work_ref({"workId": "work:invalid"})

    def test_hosted_v03_is_begin_only_closed_and_marker_bound(self):
        command = _work_begin({"workId": WORK_ID})
        self.assertEqual(command, hosted.validate_work_begin_command(command))
        parsed, meta = hosted.parse_event(_event(command))
        self.assertEqual(command, parsed)
        self.assertEqual({"issueNumber": 145, "commentId": 9901}, meta)

        bad = copy.deepcopy(command)
        bad["begin"] = None
        with self.assertRaisesRegex(RuntimeError, "WORK_BEGIN_FIELDS_INVALID"):
            hosted.validate_work_begin_command(bad)

        mismatched = _event(command)
        mismatched["comment"]["body"] = hosted.REQUEST_MARKER + "\n" + json.dumps(command)
        with self.assertRaisesRegex(RuntimeError, "MARKER_SCHEMA_MISMATCH"):
            hosted.parse_event(mismatched)

    @patch("tools.hosted_agent_cycle.continuation_remote.GitHubContinuationAuthority")
    def test_hosted_work_observation_is_read_only_existence_proof(self, authority_cls):
        authority = authority_cls.return_value
        authority.observe.return_value = SimpleNamespace(items={WORK_ID: {"id": WORK_ID}})

        self.assertEqual(
            {"workId": WORK_ID},
            hosted._observe_work_ref({"workId": WORK_ID}),
        )
        authority_cls.assert_called_once_with(repository=hosted.REPOSITORY)
        authority.observe.assert_called_once_with()

        authority.reset_mock()
        authority.observe.return_value = SimpleNamespace(items={})
        with self.assertRaisesRegex(RuntimeError, "HOSTED_AGENT_WORK_NOT_FOUND"):
            hosted._observe_work_ref({"workId": WORK_ID})

    @patch("tools.hosted_agent_cycle.continuation_remote.GitHubContinuationAuthority")
    def test_hosted_work_observation_fails_closed_when_authority_is_unknown(self, authority_cls):
        authority_cls.return_value.observe.side_effect = continuation_remote.ContinuationRemoteError(
            "CONTINUATION_REMOTE_UNAVAILABLE", "test"
        )
        with self.assertRaisesRegex(RuntimeError, "HOSTED_AGENT_WORK_AUTHORITY_UNKNOWN"):
            hosted._observe_work_ref({"workId": WORK_ID})

    @patch("tools.hosted_agent_cycle._observe_work_ref")
    @patch("tools.hosted_agent_cycle._run_agent")
    def test_hosted_v03_binds_work_before_manifest_and_handle(self, run_agent, observe_work):
        context = _context()
        self.assertEqual("READY", context["status"])
        run_agent.return_value = (0, context)
        observe_work.return_value = {"workId": WORK_ID}

        with patch.dict(
            "os.environ",
            {"GITHUB_SHA": "a" * 40, "GITHUB_RUN_ID": "123"},
            clear=False,
        ):
            import tempfile
            from pathlib import Path

            with tempfile.TemporaryDirectory() as tmp:
                result = hosted.begin_from_envelope(
                    _work_begin({"workId": WORK_ID}),
                    {"issueNumber": 145, "commentId": 9901},
                    context_path=f"{tmp}/context.json",
                    manifest_path=f"{tmp}/manifest.json",
                )
                materialized = json.loads(Path(f"{tmp}/context.json").read_text())
                manifest = json.loads(Path(f"{tmp}/manifest.json").read_text())
                handle = json.loads(Path(f"{tmp}/handle.json").read_text())

        self.assertEqual({"workId": WORK_ID}, materialized["workRef"])
        self.assertEqual(materialized["contextHash"], manifest["contextHash"])
        self.assertEqual(materialized["contextHash"], handle["context"]["contextHash"])
        self.assertEqual(materialized["schemaVersion"], handle["context"]["schemaVersion"])
        self.assertEqual(hosted.transport_command_hash(_work_begin({"workId": WORK_ID})), result["commandHash"])
        observe_work.assert_called_once_with({"workId": WORK_ID})


if __name__ == "__main__":
    unittest.main()
