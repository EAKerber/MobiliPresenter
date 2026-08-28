from __future__ import annotations

import copy
import unittest
from unittest.mock import patch

from tools import (
    agent_cycle_identity,
    agent_write_lifecycle,
    hosted_agent_tool,
    hosted_agent_write_lease,
    hosted_cycle_handle,
)
from tools.agent_tools import contracts


def manifest():
    return {
        "source": {
            "runId": 123,
            "sourceSha": "a" * 40,
            "issueNumber": 145,
            "commentId": 9001,
        },
        "artifactName": "agent-cycle-begin-123",
        "contextHash": "b" * 64,
        "cycleInstanceId": "cycle-instance-" + "c" * 24,
        "actor": {
            "role": "manager-gitops",
            "workerId": "manager-gitops-a",
            "sessionId": "session-1",
        },
    }


def context():
    return {
        "schemaVersion": "AgentCycleContext 0.3",
        "repository": "EAKerber/MobiliPresenter",
        "cycleId": "cycle-" + "d" * 20,
        "contextHash": "b" * 64,
    }


def handle():
    value = manifest()
    return agent_cycle_identity.build_handle(
        repository="EAKerber/MobiliPresenter",
        cycle_id=context()["cycleId"],
        cycle_instance_id=value["cycleInstanceId"],
        context_schema_version=context()["schemaVersion"],
        context_hash=value["contextHash"],
        actor=value["actor"],
        resume_token=hosted_cycle_handle.build_resume_token(value),
    )


def begin():
    value = manifest()
    return {
        "runId": value["source"]["runId"],
        "sourceSha": value["source"]["sourceSha"],
        "contextHash": value["contextHash"],
    }


class HostedCycleHandleR2B1Tests(unittest.TestCase):
    def test_r2a_token_encoding_is_canonical_and_round_trips(self):
        token = hosted_cycle_handle.build_resume_token(manifest())
        self.assertTrue(token.startswith("hosted-v1:"))
        value, locator = hosted_cycle_handle.decode_handle(
            handle(), repository="EAKerber/MobiliPresenter"
        )
        self.assertEqual(token, value["resumeToken"])
        self.assertEqual(123, locator["runId"])
        self.assertEqual("a" * 40, locator["sourceSha"])

    def test_binding_derives_legacy_identity(self):
        binding = hosted_cycle_handle.bind(
            handle(),
            context=context(),
            manifest=manifest(),
            repository="EAKerber/MobiliPresenter",
        )
        self.assertEqual(
            {"runId": 123, "sourceSha": "a" * 40, "contextHash": "b" * 64},
            binding["begin"],
        )
        self.assertEqual(manifest()["actor"], binding["actor"])

    def test_locator_context_and_instance_mismatch_fail(self):
        bad_manifest = manifest()
        bad_manifest["contextHash"] = "e" * 64
        with self.assertRaisesRegex(RuntimeError, "HOSTED_CYCLE_HANDLE_LOCATOR_MISMATCH"):
            hosted_cycle_handle.bind(
                handle(), context=context(), manifest=bad_manifest,
                repository="EAKerber/MobiliPresenter"
            )
        bad_manifest = manifest()
        bad_manifest["cycleInstanceId"] = "cycle-instance-" + "f" * 24
        with self.assertRaisesRegex(RuntimeError, "HOSTED_CYCLE_HANDLE_LOCATOR_MISMATCH"):
            hosted_cycle_handle.bind(
                handle(), context=context(), manifest=bad_manifest,
                repository="EAKerber/MobiliPresenter"
            )

    def test_rehashed_actor_substitution_cannot_bind(self):
        original = handle()
        altered = agent_cycle_identity.build_handle(
            repository=original["repository"],
            cycle_id=original["cycleId"],
            cycle_instance_id=original["cycleInstanceId"],
            context_schema_version=original["context"]["schemaVersion"],
            context_hash=original["context"]["contextHash"],
            actor={**original["actor"], "sessionId": "session-2"},
            resume_token=original["resumeToken"],
        )
        with self.assertRaisesRegex(RuntimeError, "HOSTED_CYCLE_HANDLE_BINDING_MISMATCH"):
            hosted_cycle_handle.bind(
                altered, context=context(), manifest=manifest(),
                repository="EAKerber/MobiliPresenter"
            )

    def test_tool_v01_and_v02_derive_the_same_exact_request_hash(self):
        legacy = {
            "schemaVersion": contracts.REQUEST_SCHEMA,
            "requestId": "agent-tool-replay",
            "begin": begin(),
            "actor": copy.deepcopy(manifest()["actor"]),
            "toolId": "git.files.mutate",
            "target": {"branch": "work/operations/replay"},
            "input": {
                "changes": [{"path": "docs/replay.txt", "content": "same"}],
                "message": "Replay identity",
            },
            "semanticAuthority": False,
            "authorizesMutation": False,
        }
        contracts.validate_request(legacy)
        outer = {
            "schemaVersion": hosted_agent_tool.HANDLE_REQUEST_SCHEMA,
            "requestId": legacy["requestId"],
            "handle": handle(),
            "toolId": legacy["toolId"],
            "target": copy.deepcopy(legacy["target"]),
            "input": copy.deepcopy(legacy["input"]),
            "semanticAuthority": False,
            "authorizesMutation": False,
        }
        with patch("tools.hosted_agent_tool.hosted_agent_cycle.validate_begin_manifest"):
            derived = hosted_agent_tool.derive_handle_request(
                outer, manifest(), context()
            )
        self.assertEqual(legacy, derived)
        self.assertEqual(contracts.request_hash(legacy), contracts.request_hash(derived))

    def test_write_lease_v01_and_v02_derive_the_same_exact_request_hash(self):
        legacy = {
            "schemaVersion": agent_write_lifecycle.REQUEST_SCHEMA,
            "requestId": "lease-replay",
            "action": "acquire",
            "begin": begin(),
            "actor": copy.deepcopy(manifest()["actor"]),
            "branch": "work/operations/replay",
            "expectedAuthorityHead": "e" * 40,
            "expectedBranchHead": "f" * 40,
            "expectedBindingHash": None,
            "ttlSeconds": 3600,
            "semanticAuthority": False,
            "authorizesMutation": False,
        }
        agent_write_lifecycle.validate_request(legacy)
        outer = {
            "schemaVersion": hosted_agent_write_lease.HANDLE_REQUEST_SCHEMA,
            "requestId": legacy["requestId"],
            "handle": handle(),
            "action": legacy["action"],
            "branch": legacy["branch"],
            "expectedAuthorityHead": legacy["expectedAuthorityHead"],
            "expectedBranchHead": legacy["expectedBranchHead"],
            "expectedBindingHash": legacy["expectedBindingHash"],
            "ttlSeconds": legacy["ttlSeconds"],
            "semanticAuthority": False,
            "authorizesMutation": False,
        }
        with patch("tools.hosted_agent_write_lease.hosted_agent_cycle.validate_begin_manifest"):
            derived = hosted_agent_write_lease.derive_handle_request(
                outer, manifest(), context()
            )
        self.assertEqual(legacy, derived)
        self.assertEqual(
            agent_write_lifecycle.request_hash(legacy),
            agent_write_lifecycle.request_hash(derived),
        )


if __name__ == "__main__":
    unittest.main()
