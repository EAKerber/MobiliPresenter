from __future__ import annotations

import copy
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tools import agent_cycle_identity, hosted_agent_cycle, hosted_cycle_handle
from tools.agent_tools import journey_entry

REPOSITORY = "EAKerber/MobiliPresenter"
WORK_ID = "r6a-hosted-entry-composition"
WORKER_ID = "manager-gitops-chat"
ROLE = "manager-gitops"
INTENT = "continue paved-path refactor"
SURFACES = ["github.repo.read", "github.issue.comment.write"]


class FakeTransport:
    def __init__(self, comments=None):
        self.comments = list(comments or [])
        self.calls: list[tuple[str, str, object]] = []
        self.next_comment_id = 900

    def request(self, method: str, endpoint: str, *, payload=None, include_headers=False):
        del include_headers
        self.calls.append((method, endpoint, copy.deepcopy(payload)))
        if method == "GET" and endpoint.endswith("issues?state=open&per_page=100&page=1"):
            return SimpleNamespace(body=json.dumps([
                {"number": 145, "title": hosted_agent_cycle.BUS_TITLE, "pull_request": None}
            ]))
        if method == "GET" and endpoint.endswith("issues/145/comments?per_page=100&page=1"):
            return SimpleNamespace(body=json.dumps(self.comments))
        if method == "POST" and endpoint.endswith("issues/145/comments"):
            return SimpleNamespace(body=json.dumps({"id": self.next_comment_id}))
        raise AssertionError((method, endpoint, payload))


def _work():
    return {"id": WORK_ID, "workerId": WORKER_ID, "status": "READY"}


def _command():
    return journey_entry.build_begin_request(
        role=ROLE,
        declared_intent=INTENT,
        work_id=WORK_ID,
        worker_id=WORKER_ID,
        tool_surfaces=SURFACES,
        inventory_complete=True,
    )


def _request_comment(command, *, comment_id=500):
    return {
        "id": comment_id,
        "author_association": "OWNER",
        "body": hosted_agent_cycle.REQUEST_MARKER_V04 + "\n" + json.dumps(command, separators=(",", ":")),
        "user": {"login": "EAKerber"},
    }


def _handle(command):
    locator = {
        "artifactName": "agent-cycle-begin-123",
        "runId": 123,
        "sourceSha": "a" * 40,
        "issueNumber": 145,
        "beginCommentId": 500,
        "contextHash": "b" * 64,
        "cycleInstanceId": "cycle-instance-" + "7" * 24,
    }
    token = hosted_cycle_handle.HOSTED_TOKEN_PREFIX + json.dumps(
        locator, sort_keys=True, separators=(",", ":")
    )
    return agent_cycle_identity.build_handle(
        repository=REPOSITORY,
        cycle_id="cycle-" + "6" * 20,
        cycle_instance_id=locator["cycleInstanceId"],
        context_schema_version="AgentCycleContext 0.4",
        context_hash=locator["contextHash"],
        actor=command["actor"],
        resume_token=token,
    )


def _ready_result(command):
    return {
        "schemaVersion": journey_entry.BEGIN_RESULT_SCHEMA,
        "requestId": command["requestId"],
        "commandHash": hosted_agent_cycle.transport_command_hash(command),
        "status": "READY",
        "handle": _handle(command),
    }


class JourneyEntryR6aTests(unittest.TestCase):
    def test_build_uses_current_v04_only_and_semantic_runtime_inputs(self) -> None:
        command = _command()
        self.assertEqual(hosted_agent_cycle.COMMAND_SCHEMA_V04, command["schemaVersion"])
        self.assertEqual({"workId": WORK_ID}, command["workRef"])
        self.assertEqual(sorted(SURFACES), command["runtimeEnvironment"]["toolSurfaces"])
        self.assertTrue(command["runtimeEnvironment"]["inventoryComplete"])
        self.assertFalse(command["semanticAuthority"])
        self.assertFalse(command["authorizesMutation"])

    def test_incomplete_inventory_is_unknown_and_has_no_transport_side_effect(self) -> None:
        transport = FakeTransport()
        value = journey_entry.compose_entry(
            role=ROLE,
            declared_intent=INTENT,
            work_id=WORK_ID,
            tool_surfaces=SURFACES,
            inventory_complete=False,
            submit=True,
            transport=transport,
        )
        self.assertEqual("UNKNOWN", value["status"])
        self.assertIn("TOOL_SURFACE_INVENTORY_INCOMPLETE", value["blockers"])
        self.assertEqual([], transport.calls)
        self.assertFalse(value["submitted"])

    @patch.object(journey_entry, "_work", return_value=_work())
    def test_build_only_observes_without_posting(self, _mock_work) -> None:
        transport = FakeTransport()
        value = journey_entry.compose_entry(
            role=ROLE,
            declared_intent=INTENT,
            work_id=WORK_ID,
            tool_surfaces=SURFACES,
            inventory_complete=True,
            submit=False,
            transport=transport,
        )
        self.assertEqual("PENDING", value["status"])
        self.assertEqual("BUILD_ONLY", value["disposition"])
        self.assertFalse(any(method == "POST" for method, _, _ in transport.calls))

    @patch.object(journey_entry, "_work", return_value=_work())
    def test_identical_pending_request_is_idempotent(self, _mock_work) -> None:
        command = _command()
        transport = FakeTransport([_request_comment(command)])
        value = journey_entry.compose_entry(
            role=ROLE,
            declared_intent=INTENT,
            work_id=WORK_ID,
            tool_surfaces=SURFACES,
            inventory_complete=True,
            submit=True,
            transport=transport,
        )
        self.assertEqual("PENDING", value["status"])
        self.assertEqual("REQUEST_PENDING", value["disposition"])
        self.assertFalse(any(method == "POST" for method, _, _ in transport.calls))

    @patch.object(journey_entry, "_work", return_value=_work())
    def test_ready_result_reuses_canonical_handle_without_new_begin(self, _mock_work) -> None:
        command = _command()
        comments = [
            _request_comment(command),
            {
                "id": 501,
                "author_association": "COLLABORATOR",
                "body": hosted_agent_cycle.RESULT_MARKER + "\n" + json.dumps(_ready_result(command)),
                "user": {"login": "github-actions[bot]"},
            },
        ]
        transport = FakeTransport(comments)
        value = journey_entry.compose_entry(
            role=ROLE,
            declared_intent=INTENT,
            work_id=WORK_ID,
            tool_surfaces=SURFACES,
            inventory_complete=True,
            submit=True,
            transport=transport,
        )
        self.assertEqual("PASS", value["status"])
        self.assertEqual("REUSED", value["disposition"])
        self.assertEqual(command["actor"], value["handle"]["actor"])
        self.assertFalse(any(method == "POST" for method, _, _ in transport.calls))

    @patch.object(journey_entry, "_work", return_value=_work())
    def test_same_request_id_with_different_payload_fails_closed(self, _mock_work) -> None:
        command = _command()
        conflicting = copy.deepcopy(command)
        conflicting["declaredIntent"] = "different intent"
        transport = FakeTransport([_request_comment(conflicting)])
        with self.assertRaisesRegex(journey_entry.JourneyEntryError, "JOURNEY_ENTRY_REQUEST_ID_CONFLICT"):
            journey_entry.compose_entry(
                role=ROLE,
                declared_intent=INTENT,
                work_id=WORK_ID,
                tool_surfaces=SURFACES,
                inventory_complete=True,
                submit=True,
                transport=transport,
            )
        self.assertFalse(any(method == "POST" for method, _, _ in transport.calls))

    def test_invalid_surface_is_rejected_by_canonical_runtime_validator(self) -> None:
        with self.assertRaisesRegex(journey_entry.JourneyEntryError, "JOURNEY_ENTRY_BEGIN_REQUEST_INVALID"):
            journey_entry.build_begin_request(
                role=ROLE,
                declared_intent=INTENT,
                work_id=WORK_ID,
                worker_id=WORKER_ID,
                tool_surfaces=["not-a-real-surface"],
                inventory_complete=True,
            )


if __name__ == "__main__":
    unittest.main()
