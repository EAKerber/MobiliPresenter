from __future__ import annotations

import copy
import re
from typing import Any

from tools.canonical import stable_hash

HANDLE_SCHEMA = "AgentCycleHandle 0.1"
ACTOR_FIELDS = {"role", "workerId", "sessionId"}
BEGIN_FIELDS = {"runId", "sourceSha", "contextHash"}
HANDLE_FIELDS = {
    "schemaVersion", "repository", "cycleId", "cycleInstanceId", "context",
    "actor", "resumeToken", "readOnly", "semanticAuthority", "authorizesMutation",
    "handleHash",
}
CONTEXT_FIELDS = {"schemaVersion", "contextHash"}
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
CYCLE_RE = re.compile(r"^cycle-[0-9a-f]{20}$")
CYCLE_INSTANCE_RE = re.compile(r"^cycle-instance-[0-9a-f]{24}$")


def _text(value: Any, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(code)
    return value.strip()


def canonical_actor(value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != ACTOR_FIELDS:
        raise RuntimeError("AGENT_CYCLE_IDENTITY_ACTOR_INVALID")
    result = {
        "role": _text(value["role"], "AGENT_CYCLE_IDENTITY_ACTOR_INVALID"),
        "workerId": _text(value["workerId"], "AGENT_CYCLE_IDENTITY_ACTOR_INVALID"),
        "sessionId": _text(value["sessionId"], "AGENT_CYCLE_IDENTITY_ACTOR_INVALID"),
    }
    if result != value:
        raise RuntimeError("AGENT_CYCLE_IDENTITY_ACTOR_NOT_CANONICAL")
    return result


def canonical_begin(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != BEGIN_FIELDS:
        raise RuntimeError("AGENT_CYCLE_IDENTITY_BEGIN_INVALID")
    run_id = value.get("runId")
    source_sha = value.get("sourceSha")
    context_hash = value.get("contextHash")
    if not isinstance(run_id, int) or isinstance(run_id, bool) or run_id <= 0:
        raise RuntimeError("AGENT_CYCLE_IDENTITY_BEGIN_INVALID")
    if not isinstance(source_sha, str) or not SHA_RE.fullmatch(source_sha):
        raise RuntimeError("AGENT_CYCLE_IDENTITY_BEGIN_INVALID")
    if not isinstance(context_hash, str) or not HASH_RE.fullmatch(context_hash):
        raise RuntimeError("AGENT_CYCLE_IDENTITY_BEGIN_INVALID")
    return {"runId": run_id, "sourceSha": source_sha, "contextHash": context_hash}


def begin_from_manifest(manifest: Any) -> dict[str, Any]:
    if not isinstance(manifest, dict) or not isinstance(manifest.get("source"), dict):
        raise RuntimeError("AGENT_CYCLE_IDENTITY_MANIFEST_INVALID")
    source = manifest["source"]
    return canonical_begin({
        "runId": source.get("runId"),
        "sourceSha": source.get("sourceSha"),
        "contextHash": manifest.get("contextHash"),
    })


def hosted_cycle_instance_id(
    source: Any,
    actor: Any,
    context_hash: Any,
) -> str:
    if not isinstance(source, dict):
        raise RuntimeError("AGENT_CYCLE_IDENTITY_SOURCE_INVALID")
    begin = canonical_begin({
        "runId": source.get("runId"),
        "sourceSha": source.get("sourceSha"),
        "contextHash": context_hash,
    })
    canonical = canonical_actor(actor)
    issue_number = source.get("issueNumber")
    comment_id = source.get("commentId")
    for item in (issue_number, comment_id):
        if not isinstance(item, int) or isinstance(item, bool) or item <= 0:
            raise RuntimeError("AGENT_CYCLE_IDENTITY_SOURCE_INVALID")
    body = {
        "begin": begin,
        "actor": canonical,
        "issueNumber": issue_number,
        "beginCommentId": comment_id,
    }
    return "cycle-instance-" + stable_hash(body)[:24]


def validate_hosted_binding(begin: Any, actor: Any, manifest: Any) -> str:
    supplied_begin = canonical_begin(begin)
    supplied_actor = canonical_actor(actor)
    expected_begin = begin_from_manifest(manifest)
    if supplied_begin != expected_begin:
        raise RuntimeError("AGENT_CYCLE_IDENTITY_BEGIN_MISMATCH")
    if not isinstance(manifest, dict) or supplied_actor != manifest.get("actor"):
        raise RuntimeError("AGENT_CYCLE_IDENTITY_ACTOR_MISMATCH")
    expected_instance = hosted_cycle_instance_id(
        manifest.get("source"), supplied_actor, expected_begin["contextHash"]
    )
    declared = manifest.get("cycleInstanceId")
    if declared is not None and declared != expected_instance:
        raise RuntimeError("AGENT_CYCLE_IDENTITY_INSTANCE_MISMATCH")
    return expected_instance


def build_handle(
    *,
    repository: str,
    cycle_id: str,
    cycle_instance_id: str,
    context_schema_version: str,
    context_hash: str,
    actor: dict[str, Any],
    resume_token: str,
) -> dict[str, Any]:
    repository = _text(repository, "AGENT_CYCLE_HANDLE_REPOSITORY_INVALID")
    if not isinstance(cycle_id, str) or not CYCLE_RE.fullmatch(cycle_id):
        raise RuntimeError("AGENT_CYCLE_HANDLE_CYCLE_ID_INVALID")
    if not isinstance(cycle_instance_id, str) or not CYCLE_INSTANCE_RE.fullmatch(cycle_instance_id):
        raise RuntimeError("AGENT_CYCLE_HANDLE_INSTANCE_ID_INVALID")
    context_schema_version = _text(
        context_schema_version, "AGENT_CYCLE_HANDLE_CONTEXT_SCHEMA_INVALID"
    )
    if not isinstance(context_hash, str) or not HASH_RE.fullmatch(context_hash):
        raise RuntimeError("AGENT_CYCLE_HANDLE_CONTEXT_HASH_INVALID")
    canonical = canonical_actor(actor)
    resume_token = _text(resume_token, "AGENT_CYCLE_HANDLE_RESUME_TOKEN_INVALID")
    body = {
        "schemaVersion": HANDLE_SCHEMA,
        "repository": repository,
        "cycleId": cycle_id,
        "cycleInstanceId": cycle_instance_id,
        "context": {
            "schemaVersion": context_schema_version,
            "contextHash": context_hash,
        },
        "actor": canonical,
        "resumeToken": resume_token,
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**body, "handleHash": stable_hash(body)}


def validate_handle(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != HANDLE_FIELDS:
        raise RuntimeError("AGENT_CYCLE_HANDLE_FIELDS_INVALID")
    if value.get("schemaVersion") != HANDLE_SCHEMA:
        raise RuntimeError("AGENT_CYCLE_HANDLE_SCHEMA_UNSUPPORTED")
    context = value.get("context")
    if not isinstance(context, dict) or set(context) != CONTEXT_FIELDS:
        raise RuntimeError("AGENT_CYCLE_HANDLE_CONTEXT_INVALID")
    expected = build_handle(
        repository=value.get("repository"),
        cycle_id=value.get("cycleId"),
        cycle_instance_id=value.get("cycleInstanceId"),
        context_schema_version=context.get("schemaVersion"),
        context_hash=context.get("contextHash"),
        actor=value.get("actor"),
        resume_token=value.get("resumeToken"),
    )
    if value != expected:
        if value.get("handleHash") != expected["handleHash"]:
            raise RuntimeError("AGENT_CYCLE_HANDLE_HASH_MISMATCH")
        raise RuntimeError("AGENT_CYCLE_HANDLE_NOT_CANONICAL")
    return value


def validate_handle_binding(
    handle: Any,
    *,
    context: Any,
    actor: Any,
    cycle_instance_id: str,
    resume_token: str | None = None,
) -> dict[str, Any]:
    value = validate_handle(handle)
    if not isinstance(context, dict):
        raise RuntimeError("AGENT_CYCLE_HANDLE_CONTEXT_BINDING_INVALID")
    expected_context = {
        "schemaVersion": context.get("schemaVersion"),
        "contextHash": context.get("contextHash"),
    }
    if (
        value["repository"] != context.get("repository")
        or value["cycleId"] != context.get("cycleId")
        or value["context"] != expected_context
    ):
        raise RuntimeError("AGENT_CYCLE_HANDLE_CONTEXT_BINDING_MISMATCH")
    if value["actor"] != canonical_actor(actor):
        raise RuntimeError("AGENT_CYCLE_HANDLE_ACTOR_BINDING_MISMATCH")
    if value["cycleInstanceId"] != cycle_instance_id:
        raise RuntimeError("AGENT_CYCLE_HANDLE_INSTANCE_BINDING_MISMATCH")
    if resume_token is not None and value["resumeToken"] != resume_token:
        raise RuntimeError("AGENT_CYCLE_HANDLE_RESUME_BINDING_MISMATCH")
    return value


def copy_handle(value: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(validate_handle(value))
