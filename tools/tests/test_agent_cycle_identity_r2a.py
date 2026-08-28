from __future__ import annotations

import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import agent_cycle_identity, hosted_agent_cycle
from tools.canonical import stable_hash


ACTOR = {
    "role": "manager-gitops",
    "workerId": "manager-gitops-a",
    "sessionId": "session-r2a",
}
CONTEXT_HASH = "c" * 64
SOURCE_SHA = "a" * 40


def source(*, run_id: int = 101, comment_id: int = 201) -> dict:
    return {
        "workflow": "hosted-agent-cycle",
        "sourceSha": SOURCE_SHA,
        "runId": run_id,
        "issueNumber": 145,
        "commentId": comment_id,
    }


def manifest(*, run_id: int = 101, comment_id: int = 201) -> dict:
    item_source = source(run_id=run_id, comment_id=comment_id)
    instance = agent_cycle_identity.hosted_cycle_instance_id(
        item_source, ACTOR, CONTEXT_HASH
    )
    return {
        "source": item_source,
        "actor": copy.deepcopy(ACTOR),
        "contextHash": CONTEXT_HASH,
        "cycleInstanceId": instance,
    }


def old_formula(item_source: dict, actor: dict, context_hash: str) -> str:
    body = {
        "begin": {
            "runId": item_source["runId"],
            "sourceSha": item_source["sourceSha"],
            "contextHash": context_hash,
        },
        "actor": actor,
        "issueNumber": item_source["issueNumber"],
        "beginCommentId": item_source["commentId"],
    }
    return "cycle-instance-" + stable_hash(body)[:24]


class AgentCycleIdentityR2ATests(unittest.TestCase):
    def test_kernel_preserves_exact_pre_r2a_hosted_instance_formula(self):
        item_source = source()
        self.assertEqual(
            agent_cycle_identity.hosted_cycle_instance_id(
                item_source, ACTOR, CONTEXT_HASH
            ),
            old_formula(item_source, ACTOR, CONTEXT_HASH),
        )

    def test_same_context_fingerprint_can_have_distinct_concrete_instances(self):
        first = agent_cycle_identity.hosted_cycle_instance_id(
            source(run_id=101, comment_id=201), ACTOR, CONTEXT_HASH
        )
        second = agent_cycle_identity.hosted_cycle_instance_id(
            source(run_id=102, comment_id=202), ACTOR, CONTEXT_HASH
        )
        self.assertNotEqual(first, second)

    def test_actor_and_begin_have_one_closed_canonical_definition(self):
        begin = {
            "runId": 101,
            "sourceSha": SOURCE_SHA,
            "contextHash": CONTEXT_HASH,
        }
        self.assertEqual(agent_cycle_identity.canonical_actor(ACTOR), ACTOR)
        self.assertEqual(agent_cycle_identity.canonical_begin(begin), begin)

        bad_actor = copy.deepcopy(ACTOR)
        bad_actor["sessionId"] = " session-r2a "
        with self.assertRaisesRegex(RuntimeError, "ACTOR_NOT_CANONICAL"):
            agent_cycle_identity.canonical_actor(bad_actor)
        with self.assertRaisesRegex(RuntimeError, "BEGIN_INVALID"):
            agent_cycle_identity.canonical_begin({**begin, "runId": True})

    def test_hosted_binding_rejects_cross_instance_or_cross_actor(self):
        item = manifest()
        begin = agent_cycle_identity.begin_from_manifest(item)
        self.assertEqual(
            agent_cycle_identity.validate_hosted_binding(begin, ACTOR, item),
            item["cycleInstanceId"],
        )

        other = manifest(run_id=102, comment_id=202)
        with self.assertRaisesRegex(RuntimeError, "BEGIN_MISMATCH"):
            agent_cycle_identity.validate_hosted_binding(begin, ACTOR, other)

        other_actor = copy.deepcopy(ACTOR)
        other_actor["sessionId"] = "session-r2a-other"
        with self.assertRaisesRegex(RuntimeError, "ACTOR_MISMATCH"):
            agent_cycle_identity.validate_hosted_binding(begin, other_actor, item)

        tampered = copy.deepcopy(item)
        tampered["cycleInstanceId"] = "cycle-instance-" + "f" * 24
        with self.assertRaisesRegex(RuntimeError, "INSTANCE_MISMATCH"):
            agent_cycle_identity.validate_hosted_binding(begin, ACTOR, tampered)

    def test_handle_is_non_authoritative_hash_bound_projection(self):
        item = manifest()
        handle = agent_cycle_identity.build_handle(
            repository="EAKerber/MobiliPresenter",
            cycle_id="cycle-" + "b" * 20,
            cycle_instance_id=item["cycleInstanceId"],
            context_schema_version="AgentCycleContext 0.3",
            context_hash=CONTEXT_HASH,
            actor=ACTOR,
            resume_token="hosted-v1:opaque-locator",
        )
        self.assertEqual(agent_cycle_identity.validate_handle(handle), handle)
        self.assertTrue(handle["readOnly"])
        self.assertFalse(handle["semanticAuthority"])
        self.assertFalse(handle["authorizesMutation"])

        for path, value in (
            (("repository",), "EAKerber/Other"),
            (("cycleInstanceId",), "cycle-instance-" + "f" * 24),
            (("context", "contextHash"), "d" * 64),
            (("actor", "sessionId"), "session-other"),
            (("resumeToken",), "hosted-v1:other"),
        ):
            changed = copy.deepcopy(handle)
            target = changed
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            with self.assertRaises(RuntimeError):
                agent_cycle_identity.validate_handle(changed)

    def test_rehashed_handle_still_cannot_cross_authoritative_binding(self):
        item = manifest()
        context = {
            "schemaVersion": "AgentCycleContext 0.3",
            "repository": "EAKerber/MobiliPresenter",
            "cycleId": "cycle-" + "b" * 20,
            "contextHash": CONTEXT_HASH,
        }
        handle = agent_cycle_identity.build_handle(
            repository=context["repository"],
            cycle_id=context["cycleId"],
            cycle_instance_id=item["cycleInstanceId"],
            context_schema_version=context["schemaVersion"],
            context_hash=context["contextHash"],
            actor=ACTOR,
            resume_token="hosted-v1:opaque-locator",
        )
        agent_cycle_identity.validate_handle_binding(
            handle,
            context=context,
            actor=ACTOR,
            cycle_instance_id=item["cycleInstanceId"],
            resume_token="hosted-v1:opaque-locator",
        )

        other = manifest(run_id=102, comment_id=202)
        rehashed_other = agent_cycle_identity.build_handle(
            repository=context["repository"],
            cycle_id=context["cycleId"],
            cycle_instance_id=other["cycleInstanceId"],
            context_schema_version=context["schemaVersion"],
            context_hash=context["contextHash"],
            actor=ACTOR,
            resume_token="hosted-v1:other-locator",
        )
        with self.assertRaisesRegex(RuntimeError, "INSTANCE_BINDING_MISMATCH"):
            agent_cycle_identity.validate_handle_binding(
                rehashed_other,
                context=context,
                actor=ACTOR,
                cycle_instance_id=item["cycleInstanceId"],
            )

    def test_current_hosted_begin_materializes_handle_next_to_existing_artifacts(self):
        command = {
            "schemaVersion": hosted_agent_cycle.COMMAND_SCHEMA,
            "requestId": "r2a-begin",
            "action": "begin",
            "actor": copy.deepcopy(ACTOR),
            "declaredIntent": "inspect-and-plan",
            "machineScope": "live",
            "begin": None,
            "evidenceCommentIds": [],
            "semanticAuthority": False,
            "authorizesMutation": False,
        }
        context = {
            "schemaVersion": "AgentCycleContext 0.3",
            "repository": hosted_agent_cycle.REPOSITORY,
            "cycleId": "cycle-" + "b" * 20,
            "contextHash": CONTEXT_HASH,
            "status": "READY",
        }
        meta = {"issueNumber": 145, "commentId": 201}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context_path = root / "context.json"
            manifest_path = root / "manifest.json"
            with (
                mock.patch.object(hosted_agent_cycle, "_run_agent", return_value=(0, context)),
                mock.patch.object(hosted_agent_cycle.agent_cycle, "validate_context"),
                mock.patch.dict(
                    os.environ,
                    {"GITHUB_RUN_ID": "101", "GITHUB_SHA": SOURCE_SHA},
                    clear=False,
                ),
            ):
                result = hosted_agent_cycle.begin_from_envelope(
                    command,
                    meta,
                    context_path=str(context_path),
                    manifest_path=str(manifest_path),
                )
            handle = json.loads((root / "handle.json").read_text(encoding="utf-8"))
            stored_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "READY")
            agent_cycle_identity.validate_handle_binding(
                handle,
                context=context,
                actor=ACTOR,
                cycle_instance_id=stored_manifest["cycleInstanceId"],
                resume_token=hosted_agent_cycle._hosted_resume_token(stored_manifest),
            )

    def test_legacy_begin_directory_without_handle_remains_readable(self):
        item = manifest()
        context = {
            "schemaVersion": "AgentCycleContext 0.3",
            "repository": hosted_agent_cycle.REPOSITORY,
            "cycleId": "cycle-" + "b" * 20,
            "contextHash": CONTEXT_HASH,
        }
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(hosted_agent_cycle.agent_cycle, "validate_context"):
                hosted_agent_cycle._validate_optional_handle(Path(tmp), context, item)


if __name__ == "__main__":
    unittest.main()
