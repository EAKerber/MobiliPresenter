from __future__ import annotations

from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 match, found {count}")
    return text.replace(old, new, 1)


def patch_hosted_cycle() -> None:
    path = Path("tools/hosted_agent_cycle.py")
    text = path.read_text(encoding="utf-8")

    text = replace_once(
        text,
        """handle-first close uses HostedAgentCycleCommand 0.2, and explicit Work-bound
begin uses HostedAgentCycleCommand 0.3. A handle-first close is reduced back to
the existing 0.1 command only after the exact begin artifact has been
materialized and the handle has been rebound to its context and manifest.""",
        """handle-first close uses HostedAgentCycleCommand 0.2, explicit Work-bound begin
uses HostedAgentCycleCommand 0.3, and current host-observed begin uses
HostedAgentCycleCommand 0.4. A handle-first close is reduced back to the existing
0.1 command only after the exact begin artifact has been materialized and the
handle has been rebound to its context and manifest.""",
        "docstring",
    )
    text = replace_once(
        text,
        "from tools import remote_canonical_execution\n",
        "from tools import remote_canonical_execution\nfrom tools import runtime_provider_adapter\n",
        "runtime-provider-adapter-import",
    )
    text = replace_once(
        text,
        'REQUEST_MARKER_V03 = "MOBILIPRESENTER_AGENT_CYCLE_REQUEST_V0_3"\n',
        'REQUEST_MARKER_V03 = "MOBILIPRESENTER_AGENT_CYCLE_REQUEST_V0_3"\n'
        'REQUEST_MARKER_V04 = "MOBILIPRESENTER_AGENT_CYCLE_REQUEST_V0_4"\n',
        "request-marker-v04",
    )
    text = replace_once(
        text,
        'COMMAND_SCHEMA_V03 = "HostedAgentCycleCommand 0.3"\n',
        'COMMAND_SCHEMA_V03 = "HostedAgentCycleCommand 0.3"\n'
        'COMMAND_SCHEMA_V04 = "HostedAgentCycleCommand 0.4"\n',
        "command-schema-v04",
    )
    text = replace_once(
        text,
        """COMMAND_V03_FIELDS = {
    "schemaVersion", "requestId", "action", "actor", "declaredIntent",
    "machineScope", "workRef", "evidenceCommentIds", "semanticAuthority",
    "authorizesMutation",
}
ACTOR_FIELDS = agent_cycle_identity.ACTOR_FIELDS""",
        """COMMAND_V03_FIELDS = {
    "schemaVersion", "requestId", "action", "actor", "declaredIntent",
    "machineScope", "workRef", "evidenceCommentIds", "semanticAuthority",
    "authorizesMutation",
}
COMMAND_V04_FIELDS = COMMAND_V03_FIELDS | {"runtimeEnvironment"}
RUNTIME_ENVIRONMENT_FIELDS = {"toolSurfaces", "inventoryComplete"}
ACTOR_FIELDS = agent_cycle_identity.ACTOR_FIELDS""",
        "v04-fields",
    )

    old_validation = """def validate_transport_command(value: Any) -> dict[str, Any]:
    if isinstance(value, dict) and value.get("schemaVersion") == COMMAND_SCHEMA_V02:
        return validate_handle_close_command(value)
    if isinstance(value, dict) and value.get("schemaVersion") == COMMAND_SCHEMA_V03:
        return validate_work_begin_command(value)
    return validate_command(value)
"""
    new_validation = """def validate_runtime_environment(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != RUNTIME_ENVIRONMENT_FIELDS:
        raise HostedAgentCycleError("HOSTED_AGENT_RUNTIME_ENVIRONMENT_FIELDS_INVALID")
    inventory_complete = value.get("inventoryComplete")
    if not isinstance(inventory_complete, bool):
        raise HostedAgentCycleError("HOSTED_AGENT_RUNTIME_ENVIRONMENT_COMPLETENESS_INVALID")
    try:
        runtime_provider_adapter.observations_from_tool_surfaces(
            value.get("toolSurfaces"),
            inventory_complete=inventory_complete,
        )
    except RuntimeError as exc:
        code = str(exc).split(":", 1)[0] or "HOSTED_AGENT_RUNTIME_ENVIRONMENT_INVALID"
        raise HostedAgentCycleError(code) from exc
    surfaces = value["toolSurfaces"]
    normalized = sorted(item.strip() for item in surfaces)
    if surfaces != normalized:
        raise HostedAgentCycleError("HOSTED_AGENT_RUNTIME_ENVIRONMENT_NOT_CANONICAL")
    return {
        "toolSurfaces": list(surfaces),
        "inventoryComplete": inventory_complete,
    }


def validate_runtime_begin_command(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != COMMAND_V04_FIELDS:
        raise HostedAgentCycleError("HOSTED_AGENT_RUNTIME_BEGIN_FIELDS_INVALID")
    if value.get("schemaVersion") != COMMAND_SCHEMA_V04 or value.get("action") != "begin":
        raise HostedAgentCycleError("HOSTED_AGENT_RUNTIME_BEGIN_INVALID")
    _text(value.get("requestId"), "HOSTED_AGENT_REQUEST_ID_INVALID")
    actor = _actor(value.get("actor"))
    if actor != value["actor"]:
        raise HostedAgentCycleError("HOSTED_AGENT_ACTOR_NOT_CANONICAL")
    declared = _text(value.get("declaredIntent"), "HOSTED_AGENT_INTENT_INVALID")
    if declared != value["declaredIntent"]:
        raise HostedAgentCycleError("HOSTED_AGENT_INTENT_NOT_CANONICAL")
    if value.get("machineScope") != "live":
        raise HostedAgentCycleError("HOSTED_AGENT_SCOPE_MUST_BE_LIVE")
    try:
        work_ref = agent_cycle.validate_work_ref(value.get("workRef"))
    except RuntimeError as exc:
        raise HostedAgentCycleError("HOSTED_AGENT_WORK_REF_INVALID") from exc
    if work_ref != value.get("workRef"):
        raise HostedAgentCycleError("HOSTED_AGENT_WORK_REF_NOT_CANONICAL")
    if validate_runtime_environment(value.get("runtimeEnvironment")) != value["runtimeEnvironment"]:
        raise HostedAgentCycleError("HOSTED_AGENT_RUNTIME_ENVIRONMENT_NOT_CANONICAL")
    if _evidence_ids(value.get("evidenceCommentIds")):
        raise HostedAgentCycleError("HOSTED_AGENT_RUNTIME_BEGIN_EVIDENCE_INVALID")
    if value.get("semanticAuthority") is not False or value.get("authorizesMutation") is not False:
        raise HostedAgentCycleError("HOSTED_AGENT_COMMAND_MUST_NOT_AUTHORIZE")
    return value


def validate_transport_command(value: Any) -> dict[str, Any]:
    if isinstance(value, dict) and value.get("schemaVersion") == COMMAND_SCHEMA_V02:
        return validate_handle_close_command(value)
    if isinstance(value, dict) and value.get("schemaVersion") == COMMAND_SCHEMA_V03:
        return validate_work_begin_command(value)
    if isinstance(value, dict) and value.get("schemaVersion") == COMMAND_SCHEMA_V04:
        return validate_runtime_begin_command(value)
    return validate_command(value)
"""
    text = replace_once(text, old_validation, new_validation, "runtime-validation")
    text = replace_once(
        text,
        """        REQUEST_MARKER_V02: COMMAND_SCHEMA_V02,
        REQUEST_MARKER_V03: COMMAND_SCHEMA_V03,
""",
        """        REQUEST_MARKER_V02: COMMAND_SCHEMA_V02,
        REQUEST_MARKER_V03: COMMAND_SCHEMA_V03,
        REQUEST_MARKER_V04: COMMAND_SCHEMA_V04,
""",
        "marker-map",
    )

    old_begin = """    work_ref = (
        _observe_work_ref(command["workRef"])
        if command["schemaVersion"] == COMMAND_SCHEMA_V03
        else None
    )
    rc, context = _run_agent([
        "begin",
        "--role", command["actor"]["role"],
        "--intent", command["declaredIntent"],
        "--machine-scope", "live",
        "--json",
    ])
"""
    new_begin = """    work_ref = (
        _observe_work_ref(command["workRef"])
        if command["schemaVersion"] in {COMMAND_SCHEMA_V03, COMMAND_SCHEMA_V04}
        else None
    )
    agent_args = [
        "begin",
        "--role", command["actor"]["role"],
        "--intent", command["declaredIntent"],
        "--machine-scope", "live",
    ]
    if command["schemaVersion"] == COMMAND_SCHEMA_V04:
        runtime_environment = validate_runtime_environment(command["runtimeEnvironment"])
        for surface_id in runtime_environment["toolSurfaces"]:
            agent_args.extend(["--runtime-tool-surface", surface_id])
        if runtime_environment["inventoryComplete"]:
            agent_args.append("--runtime-tool-surfaces-complete")
    agent_args.append("--json")
    rc, context = _run_agent(agent_args)
"""
    text = replace_once(text, old_begin, new_begin, "begin-ingress")
    text = replace_once(
        text,
        '    if command["schemaVersion"] == COMMAND_SCHEMA_V03:\n'
        '        context = agent_cycle.bind_work_ref(context, work_ref)\n',
        '    if command["schemaVersion"] in {COMMAND_SCHEMA_V03, COMMAND_SCHEMA_V04}:\n'
        '        context = agent_cycle.bind_work_ref(context, work_ref)\n',
        "work-binding-v04",
    )
    path.write_text(text, encoding="utf-8")


def patch_workflow() -> None:
    path = Path(".github/workflows/hosted-agent-cycle.yml")
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        """      (startsWith(github.event.comment.body, 'MOBILIPRESENTER_AGENT_CYCLE_REQUEST_V0_1') ||
       startsWith(github.event.comment.body, 'MOBILIPRESENTER_AGENT_CYCLE_REQUEST_V0_2') ||
       startsWith(github.event.comment.body, 'MOBILIPRESENTER_AGENT_CYCLE_REQUEST_V0_3'))""",
        """      (startsWith(github.event.comment.body, 'MOBILIPRESENTER_AGENT_CYCLE_REQUEST_V0_1') ||
       startsWith(github.event.comment.body, 'MOBILIPRESENTER_AGENT_CYCLE_REQUEST_V0_2') ||
       startsWith(github.event.comment.body, 'MOBILIPRESENTER_AGENT_CYCLE_REQUEST_V0_3') ||
       startsWith(github.event.comment.body, 'MOBILIPRESENTER_AGENT_CYCLE_REQUEST_V0_4'))""",
        "workflow-marker-v04",
    )
    path.write_text(text, encoding="utf-8")


def create_tests() -> None:
    path = Path("tools/tests/test_hosted_runtime_observation_ingress_r5a1.py")
    path.write_text('''from __future__ import annotations

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
            "body": hosted.REQUEST_MARKER_V04 + "\\n" + json.dumps(command),
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
''', encoding="utf-8")


def cleanup_scaffold() -> None:
    Path(".github/workflows/r5a1-branch-patcher.yml").unlink()
    Path("tools/r5a1_branch_patcher.py").unlink()


def main() -> None:
    patch_hosted_cycle()
    patch_workflow()
    create_tests()
    cleanup_scaffold()


if __name__ == "__main__":
    main()
