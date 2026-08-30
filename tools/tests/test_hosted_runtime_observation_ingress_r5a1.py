from __future__ import annotations

import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import hosted_agent_cycle as hosted


SURFACE = "github-connector-tools"


def runtime_begin_command(*, surfaces=None, complete=True, work_ref=None):
    return {
        "schemaVersion": hosted.COMMAND_SCHEMA_V04,
        "requestId": "hosted-runtime-begin-1",
        "action": "begin",
        "actor": {
            "role": "manager-gitops",
            "workerId": "manager-gitops-a",
            "sessionId": "session-r5a1",
        },
        "declaredIntent": "inspect-and-plan",
        "machineScope": "live",
        "workRef": work_ref,
        "runtimeEnvironment": {
            "toolSurfaces": [SURFACE] if surfaces is None else surfaces,
            "inventoryComplete": complete,
        },
        "evidenceCommentIds": [],
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


def event(command):
    return {
        "issue": {"number": 145, "title": hosted.BUS_TITLE},
        "comment": {
            "id": 9001,
            "author_association": "OWNER",
            "body": hosted.REQUEST_MARKER_V04 + "\n" + json.dumps(command),
        },
        "repository": {"full_name": hosted.REPOSITORY},
    }


class HostedRuntimeObservationIngressR5A1Tests(unittest.TestCase):
    def test_v04_runtime_environment_is_closed_canonical_and_non_authoritative(self):
        command = runtime_begin_command()
        self.assertEqual(command, hosted.validate_runtime_begin_command(command))
        self.assertEqual(command, hosted.validate_transport_command(command))

        bad = copy.deepcopy(command)
        bad["runtimeEnvironment"]["provider"] = "github-connector"
        with self.assertRaisesRegex(RuntimeError, "RUNTIME_ENVIRONMENT_FIELDS_INVALID"):
            hosted.validate_transport_command(bad)

        bad = copy.deepcopy(command)
        bad["runtimeEnvironment"]["toolSurfaces"] = [SURFACE, SURFACE]
        with self.assertRaisesRegex(RuntimeError, "RUNTIME_PROVIDER_SURFACES_DUPLICATE"):
            hosted.validate_transport_command(bad)

        bad = copy.deepcopy(command)
        bad["runtimeEnvironment"]["toolSurfaces"] = ["unknown-runtime-surface"]
        with self.assertRaisesRegex(RuntimeError, "RUNTIME_PROVIDER_SURFACE_UNKNOWN"):
            hosted.validate_transport_command(bad)

        bad = copy.deepcopy(command)
        bad["runtimeEnvironment"]["toolSurfaces"] = ["python-module-cli", SURFACE]
        with self.assertRaisesRegex(RuntimeError, "RUNTIME_ENVIRONMENT_NOT_CANONICAL"):
            hosted.validate_transport_command(bad)

        for field in ("semanticAuthority", "authorizesMutation"):
            bad = copy.deepcopy(command)
            bad[field] = True
            with self.assertRaisesRegex(RuntimeError, "MUST_NOT_AUTHORIZE"):
                hosted.validate_transport_command(bad)

    def test_v04_nullable_work_ref_and_marker_are_valid(self):
        unbound = runtime_begin_command(work_ref=None)
        parsed, meta = hosted.parse_event(event(unbound))
        self.assertEqual(parsed, unbound)
        self.assertEqual(meta, {"issueNumber": 145, "commentId": 9001})

        bound = runtime_begin_command(work_ref={"workId": "m12-at3d-r5a1"})
        self.assertEqual(bound, hosted.validate_transport_command(bound))

    @patch("tools.hosted_agent_cycle.agent_cycle.bind_work_ref")
    @patch("tools.hosted_agent_cycle.agent_cycle.validate_context")
    @patch("tools.hosted_agent_cycle._run_agent")
    def test_complete_runtime_environment_reduces_to_existing_d3c_surface_flags(
        self, run_agent, validate_context, bind_work_ref
    ):
        context = {
            "schemaVersion": hosted.agent_cycle.SCHEMA_VERSION,
            "repository": hosted.REPOSITORY,
            "cycleId": "cycle-" + "c" * 20,
            "contextHash": "d" * 64,
            "status": "READY",
        }
        run_agent.return_value = (0, context)
        bind_work_ref.return_value = context
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"GITHUB_SHA": "a" * 40, "GITHUB_RUN_ID": "123"},
            clear=False,
        ):
            result = hosted.begin_from_envelope(
                runtime_begin_command(),
                {"issueNumber": 145, "commentId": 9001},
                context_path=f"{tmp}/context.json",
                manifest_path=f"{tmp}/manifest.json",
            )
        args = run_agent.call_args.args[0]
        self.assertEqual(args[0], "begin")
        self.assertEqual(args.count("--runtime-tool-surface"), 1)
        self.assertEqual(args[args.index("--runtime-tool-surface") + 1], SURFACE)
        self.assertIn("--runtime-tool-surfaces-complete", args)
        self.assertEqual(args[-1], "--json")
        self.assertEqual(result["status"], "READY")
        bind_work_ref.assert_called_once_with(context, None)
        validate_context.assert_called()

    @patch("tools.hosted_agent_cycle.agent_cycle.bind_work_ref")
    @patch("tools.hosted_agent_cycle.agent_cycle.validate_context")
    @patch("tools.hosted_agent_cycle._run_agent")
    def test_incomplete_runtime_environment_preserves_incomplete_d3c_ingress(
        self, run_agent, validate_context, bind_work_ref
    ):
        context = {
            "schemaVersion": hosted.agent_cycle.SCHEMA_VERSION,
            "repository": hosted.REPOSITORY,
            "cycleId": "cycle-" + "c" * 20,
            "contextHash": "d" * 64,
            "status": "READY",
        }
        run_agent.return_value = (0, context)
        bind_work_ref.return_value = context
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"GITHUB_SHA": "a" * 40, "GITHUB_RUN_ID": "123"},
            clear=False,
        ):
            hosted.begin_from_envelope(
                runtime_begin_command(complete=False),
                {"issueNumber": 145, "commentId": 9001},
                context_path=f"{tmp}/context.json",
                manifest_path=f"{tmp}/manifest.json",
            )
        args = run_agent.call_args.args[0]
        self.assertIn("--runtime-tool-surface", args)
        self.assertNotIn("--runtime-tool-surfaces-complete", args)
        bind_work_ref.assert_called_once_with(context, None)
        validate_context.assert_called()

    def test_historical_transport_schemas_remain_accepted_and_v04_is_begin_only(self):
        legacy = {
            "schemaVersion": hosted.COMMAND_SCHEMA,
            "requestId": "legacy-begin",
            "action": "begin",
            "actor": copy.deepcopy(runtime_begin_command()["actor"]),
            "declaredIntent": "inspect-and-plan",
            "machineScope": "live",
            "begin": None,
            "evidenceCommentIds": [],
            "semanticAuthority": False,
            "authorizesMutation": False,
        }
        self.assertEqual(legacy, hosted.validate_transport_command(legacy))

        bad = runtime_begin_command()
        bad["action"] = "close"
        with self.assertRaisesRegex(RuntimeError, "RUNTIME_BEGIN_INVALID"):
            hosted.validate_transport_command(bad)


if __name__ == "__main__":
    unittest.main()
