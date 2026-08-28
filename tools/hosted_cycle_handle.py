from __future__ import annotations

import json
import re
from typing import Any

from tools import agent_cycle_identity

HOSTED_TOKEN_PREFIX = "hosted-v1:"
LOCATOR_FIELDS = {
    "artifactName",
    "runId",
    "sourceSha",
    "issueNumber",
    "beginCommentId",
    "contextHash",
    "cycleInstanceId",
}
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
HASH_RE = re.compile(r"^[0-9a-f]{64}$")


class HostedCycleHandleError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _positive_int(value: Any) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise HostedCycleHandleError("HOSTED_CYCLE_HANDLE_LOCATOR_INVALID")
    return value


def _locator_from_manifest(manifest: Any) -> dict[str, Any]:
    if not isinstance(manifest, dict) or not isinstance(manifest.get("source"), dict):
        raise HostedCycleHandleError("HOSTED_CYCLE_HANDLE_MANIFEST_INVALID")
    source = manifest["source"]
    locator = {
        "artifactName": manifest.get("artifactName"),
        "runId": source.get("runId"),
        "sourceSha": source.get("sourceSha"),
        "issueNumber": source.get("issueNumber"),
        "beginCommentId": source.get("commentId"),
        "contextHash": manifest.get("contextHash"),
        "cycleInstanceId": manifest.get("cycleInstanceId"),
    }
    return validate_locator(locator)


def validate_locator(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != LOCATOR_FIELDS:
        raise HostedCycleHandleError("HOSTED_CYCLE_HANDLE_LOCATOR_INVALID")
    artifact_name = value.get("artifactName")
    run_id = _positive_int(value.get("runId"))
    source_sha = value.get("sourceSha")
    issue_number = _positive_int(value.get("issueNumber"))
    begin_comment_id = _positive_int(value.get("beginCommentId"))
    context_hash = value.get("contextHash")
    cycle_instance_id = value.get("cycleInstanceId")
    if artifact_name != f"agent-cycle-begin-{run_id}":
        raise HostedCycleHandleError("HOSTED_CYCLE_HANDLE_ARTIFACT_MISMATCH")
    if not isinstance(source_sha, str) or SHA_RE.fullmatch(source_sha) is None:
        raise HostedCycleHandleError("HOSTED_CYCLE_HANDLE_LOCATOR_INVALID")
    if not isinstance(context_hash, str) or HASH_RE.fullmatch(context_hash) is None:
        raise HostedCycleHandleError("HOSTED_CYCLE_HANDLE_LOCATOR_INVALID")
    if (
        not isinstance(cycle_instance_id, str)
        or agent_cycle_identity.CYCLE_INSTANCE_RE.fullmatch(cycle_instance_id) is None
    ):
        raise HostedCycleHandleError("HOSTED_CYCLE_HANDLE_LOCATOR_INVALID")
    return {
        "artifactName": artifact_name,
        "runId": run_id,
        "sourceSha": source_sha,
        "issueNumber": issue_number,
        "beginCommentId": begin_comment_id,
        "contextHash": context_hash,
        "cycleInstanceId": cycle_instance_id,
    }


def build_resume_token(manifest: dict[str, Any]) -> str:
    locator = _locator_from_manifest(manifest)
    return HOSTED_TOKEN_PREFIX + json.dumps(locator, sort_keys=True, separators=(",", ":"))


def decode_handle(handle: Any, *, repository: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        value = agent_cycle_identity.validate_handle(handle)
    except RuntimeError as exc:
        raise HostedCycleHandleError("HOSTED_CYCLE_HANDLE_INVALID") from exc
    if repository is not None and value["repository"] != repository:
        raise HostedCycleHandleError("HOSTED_CYCLE_HANDLE_REPOSITORY_MISMATCH")
    token = value["resumeToken"]
    if not token.startswith(HOSTED_TOKEN_PREFIX):
        raise HostedCycleHandleError("HOSTED_CYCLE_HANDLE_PROVIDER_UNSUPPORTED")
    try:
        locator = json.loads(token[len(HOSTED_TOKEN_PREFIX):])
    except json.JSONDecodeError as exc:
        raise HostedCycleHandleError("HOSTED_CYCLE_HANDLE_TOKEN_INVALID") from exc
    locator = validate_locator(locator)
    canonical_token = HOSTED_TOKEN_PREFIX + json.dumps(
        locator, sort_keys=True, separators=(",", ":")
    )
    if token != canonical_token:
        raise HostedCycleHandleError("HOSTED_CYCLE_HANDLE_TOKEN_NOT_CANONICAL")
    if locator["contextHash"] != value["context"]["contextHash"]:
        raise HostedCycleHandleError("HOSTED_CYCLE_HANDLE_CONTEXT_MISMATCH")
    if locator["cycleInstanceId"] != value["cycleInstanceId"]:
        raise HostedCycleHandleError("HOSTED_CYCLE_HANDLE_INSTANCE_MISMATCH")
    return value, locator


def bind(
    handle: Any,
    *,
    context: dict[str, Any],
    manifest: dict[str, Any],
    repository: str | None = None,
) -> dict[str, Any]:
    value, locator = decode_handle(handle, repository=repository)
    expected_locator = _locator_from_manifest(manifest)
    if locator != expected_locator:
        raise HostedCycleHandleError("HOSTED_CYCLE_HANDLE_LOCATOR_MISMATCH")
    try:
        agent_cycle_identity.validate_handle_binding(
            value,
            context=context,
            actor=manifest.get("actor"),
            cycle_instance_id=manifest.get("cycleInstanceId"),
            resume_token=build_resume_token(manifest),
        )
        begin = agent_cycle_identity.begin_from_manifest(manifest)
        actor = agent_cycle_identity.canonical_actor(manifest.get("actor"))
    except RuntimeError as exc:
        raise HostedCycleHandleError("HOSTED_CYCLE_HANDLE_BINDING_MISMATCH") from exc
    return {
        "handle": value,
        "locator": locator,
        "begin": begin,
        "actor": actor,
    }
