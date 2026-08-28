from __future__ import annotations

import copy
import unittest

from tools import agent_cycle_identity, hosted_cycle_handle


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


if __name__ == "__main__":
    unittest.main()
