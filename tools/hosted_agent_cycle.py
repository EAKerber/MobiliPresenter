#!/usr/bin/env python3
"""Hosted carrier for the Agent Cycle begin/close protocol.

The carrier remains non-authoritative. Current begin emits a public
AgentCycleHandle 0.1. Historical HostedAgentCycleCommand 0.1 remains accepted,
handle-first close uses HostedAgentCycleCommand 0.2, and explicit Work-bound
begin uses HostedAgentCycleCommand 0.3. A handle-first close is reduced back to
the existing 0.1 command only after the exact begin artifact has been
materialized and the handle has been rebound to its context and manifest.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import agent_cycle
from tools import agent_cycle_close
from tools import agent_cycle_identity
from tools import agent_failure
from tools import agent_write_lifecycle_guard
from tools import continuation_remote
from tools import hosted_agent_cycle_trace
from tools import hosted_cycle_handle
from tools import remote_canonical_execution
from tools.agent_tools import trace_collect
from tools.canonical import stable_hash

REPOSITORY = "EAKerber/MobiliPresenter"
BUS_TITLE = "MobiliPresenter Remote Canonical Execution Bus"
REQUEST_MARKER = "MOBILIPRESENTER_AGENT_CYCLE_REQUEST_V0_1"
REQUEST_MARKER_V02 = "MOBILIPRESENTER_AGENT_CYCLE_REQUEST_V0_2"
REQUEST_MARKER_V03 = "MOBILIPRESENTER_AGENT_CYCLE_REQUEST_V0_3"
RESULT_MARKER = "MOBILIPRESENTER_AGENT_CYCLE_RESULT_V0_1"
COMMAND_SCHEMA = "HostedAgentCycleCommand 0.1"
COMMAND_SCHEMA_V02 = "HostedAgentCycleCommand 0.2"
COMMAND_SCHEMA_V03 = "HostedAgentCycleCommand 0.3"
LEGACY_BEGIN_MANIFEST_SCHEMA = "HostedAgentCycleBeginManifest 0.1"
TRACE_BEGIN_MANIFEST_SCHEMA = "HostedAgentCycleBeginManifest 0.2"
BEGIN_MANIFEST_SCHEMA = "HostedAgentCycleBeginManifest 0.3"
BEGIN_RESULT_SCHEMA = "HostedAgentCycleBeginResult 0.4"
CLOSE_RESULT_SCHEMA = "HostedAgentCycleCloseResult 0.1"
FAILURE_SCHEMA = agent_failure.HOSTED_CYCLE_FAILURE_SCHEMA
TRACE_FEATURE = "execution-trace-0.1"
WRITE_LEASE_FEATURE = "agent-write-lease-lifecycle-0.1"
CURRENT_FEATURES = sorted([TRACE_FEATURE, WRITE_LEASE_FEATURE])
ACTIONS = {"begin", "close"}
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
CYCLE_INSTANCE_RE = agent_cycle_identity.CYCLE_INSTANCE_RE
COMMAND_FIELDS = {
    "schemaVersion", "requestId", "action", "actor", "declaredIntent",
    "machineScope", "begin", "evidenceCommentIds", "semanticAuthority",
    "authorizesMutation",
}
COMMAND_V02_FIELDS = {
    "schemaVersion", "requestId", "action", "handle", "evidenceCommentIds",
    "semanticAuthority", "authorizesMutation",
}
COMMAND_V03_FIELDS = {
    "schemaVersion", "requestId", "action", "actor", "declaredIntent",
    "machineScope", "workRef", "evidenceCommentIds", "semanticAuthority",
    "authorizesMutation",
}
ACTOR_FIELDS = agent_cycle_identity.ACTOR_FIELDS
BEGIN_REF_FIELDS = agent_cycle_identity.BEGIN_FIELDS


class HostedAgentCycleError(RuntimeError):
    def __init__(
        self,
        code: str,
        detail: str = "",
        *,
        failure_core: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.detail = detail
        self.failure_core = (
            agent_failure.validate_failure_core(failure_core)
            if failure_core is not None
            else None
        )
        super().__init__(f"{code}:{detail}" if detail else code)


def _text(value: Any, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HostedAgentCycleError(code)
    return value.strip()


def _actor(value: Any) -> dict[str, str]:
    try:
        return agent_cycle_identity.canonical_actor(value)
    except RuntimeError as exc:
        raise HostedAgentCycleError("HOSTED_AGENT_ACTOR_INVALID") from exc


def _begin_ref(value: Any) -> dict[str, Any]:
    try:
        return agent_cycle_identity.canonical_begin(value)
    except RuntimeError as exc:
        raise HostedAgentCycleError("HOSTED_AGENT_BEGIN_REF_INVALID") from exc


def _evidence_ids(value: Any) -> list[int]:
    if (
        not isinstance(value, list)
        or any(not isinstance(item, int) or isinstance(item, bool) or item <= 0 for item in value)
        or len(value) != len(set(value))
    ):
        raise HostedAgentCycleError("HOSTED_AGENT_EVIDENCE_IDS_INVALID")
    return value


def validate_command(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != COMMAND_FIELDS:
        raise HostedAgentCycleError("HOSTED_AGENT_COMMAND_FIELDS_INVALID")
    if value.get("schemaVersion") != COMMAND_SCHEMA:
        raise HostedAgentCycleError("HOSTED_AGENT_COMMAND_SCHEMA_UNSUPPORTED")
    _text(value.get("requestId"), "HOSTED_AGENT_REQUEST_ID_INVALID")
    action = value.get("action")
    if action not in ACTIONS:
        raise HostedAgentCycleError("HOSTED_AGENT_ACTION_INVALID")
    actor = _actor(value.get("actor"))
    if actor != value["actor"]:
        raise HostedAgentCycleError("HOSTED_AGENT_ACTOR_NOT_CANONICAL")
    declared = _text(value.get("declaredIntent"), "HOSTED_AGENT_INTENT_INVALID")
    if declared != value["declaredIntent"]:
        raise HostedAgentCycleError("HOSTED_AGENT_INTENT_NOT_CANONICAL")
    if value.get("machineScope") != "live":
        raise HostedAgentCycleError("HOSTED_AGENT_SCOPE_MUST_BE_LIVE")
    evidence = _evidence_ids(value.get("evidenceCommentIds"))
    if action == "begin":
        if value.get("begin") is not None or evidence:
            raise HostedAgentCycleError("HOSTED_AGENT_BEGIN_COMMAND_INVALID")
    else:
        if _begin_ref(value.get("begin")) != value["begin"]:
            raise HostedAgentCycleError("HOSTED_AGENT_BEGIN_REF_NOT_CANONICAL")
    if value.get("semanticAuthority") is not False or value.get("authorizesMutation") is not False:
        raise HostedAgentCycleError("HOSTED_AGENT_COMMAND_MUST_NOT_AUTHORIZE")
    return value


def validate_handle_close_command(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != COMMAND_V02_FIELDS:
        raise HostedAgentCycleError("HOSTED_AGENT_HANDLE_COMMAND_FIELDS_INVALID")
    if value.get("schemaVersion") != COMMAND_SCHEMA_V02 or value.get("action") != "close":
        raise HostedAgentCycleError("HOSTED_AGENT_HANDLE_COMMAND_INVALID")
    _text(value.get("requestId"), "HOSTED_AGENT_REQUEST_ID_INVALID")
    try:
        hosted_cycle_handle.decode_handle(value.get("handle"), repository=REPOSITORY)
    except RuntimeError as exc:
        raise HostedAgentCycleError("HOSTED_AGENT_CYCLE_HANDLE_INVALID") from exc
    _evidence_ids(value.get("evidenceCommentIds"))
    if value.get("semanticAuthority") is not False or value.get("authorizesMutation") is not False:
        raise HostedAgentCycleError("HOSTED_AGENT_COMMAND_MUST_NOT_AUTHORIZE")
    return value


def validate_work_begin_command(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != COMMAND_V03_FIELDS:
        raise HostedAgentCycleError("HOSTED_AGENT_WORK_BEGIN_FIELDS_INVALID")
    if value.get("schemaVersion") != COMMAND_SCHEMA_V03 or value.get("action") != "begin":
        raise HostedAgentCycleError("HOSTED_AGENT_WORK_BEGIN_INVALID")
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
    if _evidence_ids(value.get("evidenceCommentIds")):
        raise HostedAgentCycleError("HOSTED_AGENT_WORK_BEGIN_EVIDENCE_INVALID")
    if value.get("semanticAuthority") is not False or value.get("authorizesMutation") is not False:
        raise HostedAgentCycleError("HOSTED_AGENT_COMMAND_MUST_NOT_AUTHORIZE")
    return value


def validate_transport_command(value: Any) -> dict[str, Any]:
    if isinstance(value, dict) and value.get("schemaVersion") == COMMAND_SCHEMA_V02:
        return validate_handle_close_command(value)
    if isinstance(value, dict) and value.get("schemaVersion") == COMMAND_SCHEMA_V03:
        return validate_work_begin_command(value)
    return validate_command(value)


def command_hash(command: dict[str, Any]) -> str:
    validate_command(command)
    return stable_hash(command)


def transport_command_hash(command: dict[str, Any]) -> str:
    validate_transport_command(command)
    return stable_hash(command)


def parse_event(value: Any) -> tuple[dict[str, Any], dict[str, int]]:
    if not isinstance(value, dict):
        raise HostedAgentCycleError("HOSTED_AGENT_EVENT_INVALID")
    issue = value.get("issue")
    comment = value.get("comment")
    repository = value.get("repository")
    if not isinstance(issue, dict) or not isinstance(comment, dict) or not isinstance(repository, dict):
        raise HostedAgentCycleError("HOSTED_AGENT_EVENT_INVALID")
    if issue.get("pull_request") is not None:
        raise HostedAgentCycleError("HOSTED_AGENT_PR_COMMENT_FORBIDDEN")
    if issue.get("title") != BUS_TITLE:
        raise HostedAgentCycleError("HOSTED_AGENT_BUS_MISMATCH")
    if comment.get("author_association") != "OWNER":
        raise HostedAgentCycleError("HOSTED_AGENT_ACTOR_FORBIDDEN")
    if repository.get("full_name") != REPOSITORY:
        raise HostedAgentCycleError("HOSTED_AGENT_REPOSITORY_MISMATCH")
    body = comment.get("body")
    if not isinstance(body, str):
        raise HostedAgentCycleError("HOSTED_AGENT_MARKER_INVALID")
    markers = {
        REQUEST_MARKER: COMMAND_SCHEMA,
        REQUEST_MARKER_V02: COMMAND_SCHEMA_V02,
        REQUEST_MARKER_V03: COMMAND_SCHEMA_V03,
    }
    marker = next((item for item in markers if body.startswith(item + "\n")), None)
    if marker is None:
        raise HostedAgentCycleError("HOSTED_AGENT_MARKER_INVALID")
    try:
        command = json.loads(body[len(marker) + 1:].strip())
    except json.JSONDecodeError as exc:
        raise HostedAgentCycleError("HOSTED_AGENT_JSON_INVALID") from exc
    command = validate_transport_command(command)
    if command["schemaVersion"] != markers[marker]:
        raise HostedAgentCycleError("HOSTED_AGENT_MARKER_SCHEMA_MISMATCH")
    issue_number = issue.get("number")
    comment_id = comment.get("id")
    if (
        not isinstance(issue_number, int) or isinstance(issue_number, bool) or issue_number <= 0
        or not isinstance(comment_id, int) or isinstance(comment_id, bool) or comment_id <= 0
    ):
        raise HostedAgentCycleError("HOSTED_AGENT_EVENT_IDENTITY_INVALID")
    return command, {"issueNumber": issue_number, "commentId": comment_id}


def _source(meta: dict[str, int]) -> dict[str, Any]:
    sha = os.environ.get("HOSTED_AGENT_SOURCE_SHA") or os.environ.get("GITHUB_SHA", "")
    run = os.environ.get("GITHUB_RUN_ID", "")
    if not SHA_RE.fullmatch(sha):
        raise HostedAgentCycleError("HOSTED_AGENT_SOURCE_SHA_INVALID")
    if not run.isdigit() or int(run) <= 0:
        raise HostedAgentCycleError("HOSTED_AGENT_RUN_ID_INVALID")
    return {
        "workflow": "hosted-agent-cycle",
        "sourceSha": sha,
        "runId": int(run),
        "issueNumber": meta["issueNumber"],
        "commentId": meta["commentId"],
    }


def _cycle_instance_id(source: dict[str, Any], actor: dict[str, str], context_hash: str) -> str:
    try:
        return agent_cycle_identity.hosted_cycle_instance_id(source, actor, context_hash)
    except RuntimeError as exc:
        raise HostedAgentCycleError("HOSTED_AGENT_CYCLE_INSTANCE_INVALID") from exc


def _hosted_resume_token(manifest: dict[str, Any]) -> str:
    return hosted_cycle_handle.build_resume_token(manifest)


def _handle_for_manifest(context: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    agent_cycle.validate_context(context)
    validate_begin_manifest(manifest, context)
    return agent_cycle_identity.build_handle(
        repository=context["repository"],
        cycle_id=context["cycleId"],
        cycle_instance_id=manifest["cycleInstanceId"],
        context_schema_version=context["schemaVersion"],
        context_hash=context["contextHash"],
        actor=manifest["actor"],
        resume_token=_hosted_resume_token(manifest),
    )


def _write_json(path: str | Path, value: dict[str, Any]) -> None:
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _load_json(path: str | Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HostedAgentCycleError("HOSTED_AGENT_ARTIFACT_INVALID") from exc
    if not isinstance(value, dict):
        raise HostedAgentCycleError("HOSTED_AGENT_ARTIFACT_INVALID")
    return value


def _run_agent(args: list[str]) -> tuple[int, dict[str, Any]]:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "agent.py"), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    raw = proc.stdout.strip()
    try:
        payload = json.loads(raw) if raw else {}
    except json.JSONDecodeError as exc:
        detail = (proc.stderr or raw).strip()
        raise HostedAgentCycleError("HOSTED_AGENT_CANONICAL_OUTPUT_INVALID", detail) from exc
    if not isinstance(payload, dict):
        raise HostedAgentCycleError("HOSTED_AGENT_CANONICAL_OUTPUT_INVALID")
    return proc.returncode, payload


def _begin_manifest(command: dict[str, Any], context: dict[str, Any], meta: dict[str, int]) -> dict[str, Any]:
    source = _source(meta)
    artifact_name = f"agent-cycle-begin-{source['runId']}"
    cycle_instance_id = _cycle_instance_id(source, command["actor"], context["contextHash"])
    core = {
        "schemaVersion": BEGIN_MANIFEST_SCHEMA,
        "requestId": command["requestId"],
        "commandHash": transport_command_hash(command),
        "actor": copy.deepcopy(command["actor"]),
        "declaredIntent": command["declaredIntent"],
        "machineScope": "live",
        "source": source,
        "artifactName": artifact_name,
        "cycleId": context["cycleId"],
        "cycleInstanceId": cycle_instance_id,
        "contextHash": context["contextHash"],
        "carrierFeatures": copy.deepcopy(CURRENT_FEATURES),
        "status": "READY",
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**core, "manifestHash": stable_hash(core)}


def validate_begin_manifest(value: Any, context: dict[str, Any] | None = None) -> dict[str, Any]:
    legacy_fields = {
        "schemaVersion", "requestId", "commandHash", "actor", "declaredIntent",
        "machineScope", "source", "artifactName", "cycleId", "contextHash",
        "status", "semanticAuthority", "authorizesMutation", "manifestHash",
    }
    current_fields = legacy_fields | {"cycleInstanceId", "carrierFeatures"}
    if not isinstance(value, dict):
        raise HostedAgentCycleError("HOSTED_AGENT_BEGIN_MANIFEST_FIELDS_INVALID")
    version = value.get("schemaVersion")
    expected_fields = (
        legacy_fields if version == LEGACY_BEGIN_MANIFEST_SCHEMA
        else current_fields if version in {TRACE_BEGIN_MANIFEST_SCHEMA, BEGIN_MANIFEST_SCHEMA}
        else None
    )
    if expected_fields is None or set(value) != expected_fields:
        raise HostedAgentCycleError("HOSTED_AGENT_BEGIN_MANIFEST_FIELDS_INVALID")
    if value.get("status") != "READY":
        raise HostedAgentCycleError("HOSTED_AGENT_BEGIN_MANIFEST_INVALID")
    actor = _actor(value.get("actor"))
    _text(value.get("declaredIntent"), "HOSTED_AGENT_BEGIN_MANIFEST_INVALID")
    if value.get("machineScope") != "live":
        raise HostedAgentCycleError("HOSTED_AGENT_BEGIN_MANIFEST_INVALID")
    source = value.get("source")
    if not isinstance(source, dict) or set(source) != {"workflow", "sourceSha", "runId", "issueNumber", "commentId"}:
        raise HostedAgentCycleError("HOSTED_AGENT_BEGIN_SOURCE_INVALID")
    if source.get("workflow") != "hosted-agent-cycle" or not SHA_RE.fullmatch(str(source.get("sourceSha", ""))):
        raise HostedAgentCycleError("HOSTED_AGENT_BEGIN_SOURCE_INVALID")
    for key in ("runId", "issueNumber", "commentId"):
        item = source.get(key)
        if not isinstance(item, int) or isinstance(item, bool) or item <= 0:
            raise HostedAgentCycleError("HOSTED_AGENT_BEGIN_SOURCE_INVALID")
    if value.get("artifactName") != f"agent-cycle-begin-{source['runId']}":
        raise HostedAgentCycleError("HOSTED_AGENT_BEGIN_ARTIFACT_NAME_INVALID")
    if not isinstance(value.get("contextHash"), str) or not HASH_RE.fullmatch(value["contextHash"]):
        raise HostedAgentCycleError("HOSTED_AGENT_BEGIN_CONTEXT_HASH_INVALID")
    if version in {TRACE_BEGIN_MANIFEST_SCHEMA, BEGIN_MANIFEST_SCHEMA}:
        expected_features = [TRACE_FEATURE] if version == TRACE_BEGIN_MANIFEST_SCHEMA else CURRENT_FEATURES
        if value.get("carrierFeatures") != expected_features:
            raise HostedAgentCycleError("HOSTED_AGENT_BEGIN_FEATURES_INVALID")
        cycle_instance_id = value.get("cycleInstanceId")
        if not isinstance(cycle_instance_id, str) or not CYCLE_INSTANCE_RE.fullmatch(cycle_instance_id):
            raise HostedAgentCycleError("HOSTED_AGENT_CYCLE_INSTANCE_INVALID")
        if cycle_instance_id != _cycle_instance_id(source, actor, value["contextHash"]):
            raise HostedAgentCycleError("HOSTED_AGENT_CYCLE_INSTANCE_MISMATCH")
    if value.get("semanticAuthority") is not False or value.get("authorizesMutation") is not False:
        raise HostedAgentCycleError("HOSTED_AGENT_BEGIN_MANIFEST_MUST_NOT_AUTHORIZE")
    core = {key: copy.deepcopy(item) for key, item in value.items() if key != "manifestHash"}
    if value.get("manifestHash") != stable_hash(core):
        raise HostedAgentCycleError("HOSTED_AGENT_BEGIN_MANIFEST_HASH_MISMATCH")
    if context is not None:
        agent_cycle.validate_context(context)
        if context.get("status") != "READY":
            raise HostedAgentCycleError("HOSTED_AGENT_BEGIN_CONTEXT_NOT_READY")
        if context.get("contextHash") != value["contextHash"] or context.get("cycleId") != value["cycleId"]:
            raise HostedAgentCycleError("HOSTED_AGENT_BEGIN_CONTEXT_MISMATCH")
    return value


def _manifest_requires_trace(manifest: dict[str, Any]) -> bool:
    validate_begin_manifest(manifest)
    return (
        manifest["schemaVersion"] in {TRACE_BEGIN_MANIFEST_SCHEMA, BEGIN_MANIFEST_SCHEMA}
        and TRACE_FEATURE in manifest["carrierFeatures"]
    )


def _manifest_requires_write_lifecycle(manifest: dict[str, Any]) -> bool:
    validate_begin_manifest(manifest)
    return (
        manifest["schemaVersion"] == BEGIN_MANIFEST_SCHEMA
        and WRITE_LEASE_FEATURE in manifest["carrierFeatures"]
    )


def _failure_core(
    *,
    phase: str,
    causes: list[dict[str, str]],
    status: str = "BLOCKED",
    lossy_projection: bool = False,
) -> dict[str, Any]:
    unique: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for cause in causes:
        identity = (cause["code"], cause["source"], cause["phase"])
        if identity in seen:
            continue
        seen.add(identity)
        unique.append(cause)
    return agent_failure.build_failure_core(
        surface="AGENT_CYCLE",
        phase=phase,
        status=status,
        causes=unique,
        observation_retry="UNKNOWN",
        operation_replay="NOT_APPLICABLE",
        mutation_state="NOT_APPLICABLE",
        lossy_projection=lossy_projection,
    )


def _hosted_cause(code: str, phase: str) -> dict[str, str]:
    return {"code": code, "source": "hosted-agent-cycle", "phase": phase}


def _context_failure_core(context: dict[str, Any]) -> dict[str, Any]:
    agent_cycle.validate_context(context)
    status = context["status"] if context["status"] in {"BLOCKED", "UNKNOWN"} else "BLOCKED"
    blockers = context.get("blockingUnknowns")
    causes = [
        {"code": code, "source": "agent-cycle", "phase": "BEGIN"}
        for code in blockers
        if isinstance(code, str) and agent_failure.CODE_RE.fullmatch(code)
    ] if isinstance(blockers, list) else []
    lossy = not causes
    if not causes:
        causes.append(_hosted_cause("HOSTED_AGENT_CANONICAL_BEGIN_FAILED", "BEGIN"))
    causes.append(_hosted_cause("HOSTED_AGENT_BEGIN_NOT_READY", "BEGIN"))
    return _failure_core(
        phase="BEGIN",
        status=status,
        causes=causes,
        lossy_projection=lossy,
    )


def _observe_work_ref(work_ref: Any) -> dict[str, str] | None:
    try:
        normalized = agent_cycle.validate_work_ref(work_ref)
    except RuntimeError as exc:
        raise HostedAgentCycleError("HOSTED_AGENT_WORK_REF_INVALID") from exc
    if normalized is None:
        return None
    try:
        observed = continuation_remote.GitHubContinuationAuthority(
            repository=REPOSITORY
        ).observe()
    except continuation_remote.ContinuationRemoteError as exc:
        raise HostedAgentCycleError("HOSTED_AGENT_WORK_AUTHORITY_UNKNOWN", exc.code) from exc
    if normalized["workId"] not in observed.items:
        raise HostedAgentCycleError("HOSTED_AGENT_WORK_NOT_FOUND")
    return normalized


def begin_from_envelope(
    command: dict[str, Any], meta: dict[str, int], *, context_path: str, manifest_path: str
) -> dict[str, Any]:
    command = validate_transport_command(command)
    if command["action"] != "begin":
        raise HostedAgentCycleError("HOSTED_AGENT_BEGIN_ACTION_REQUIRED")
    work_ref = (
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
    if rc != 0:
        try:
            failure_core = _context_failure_core(context)
        except Exception:
            failure_core = _failure_core(
                phase="BEGIN",
                causes=[
                    _hosted_cause("HOSTED_AGENT_CANONICAL_BEGIN_FAILED", "BEGIN"),
                    _hosted_cause("HOSTED_AGENT_BEGIN_NOT_READY", "BEGIN"),
                ],
                lossy_projection=True,
            )
        raise HostedAgentCycleError(
            "HOSTED_AGENT_BEGIN_NOT_READY",
            failure_core=failure_core,
        )
    agent_cycle.validate_context(context)
    if context["status"] != "READY":
        raise HostedAgentCycleError(
            "HOSTED_AGENT_BEGIN_NOT_READY",
            failure_core=_context_failure_core(context),
        )
    if command["schemaVersion"] == COMMAND_SCHEMA_V03:
        context = agent_cycle.bind_work_ref(context, work_ref)
    manifest = _begin_manifest(command, context, meta)
    validate_begin_manifest(manifest, context)
    handle = _handle_for_manifest(context, manifest)
    _write_json(context_path, context)
    _write_json(manifest_path, manifest)
    _write_json(Path(context_path).with_name("handle.json"), handle)
    core = {
        "schemaVersion": BEGIN_RESULT_SCHEMA,
        "requestId": command["requestId"],
        "commandHash": transport_command_hash(command),
        "runId": manifest["source"]["runId"],
        "sourceSha": manifest["source"]["sourceSha"],
        "artifactName": manifest["artifactName"],
        "cycleId": context["cycleId"],
        "cycleInstanceId": manifest["cycleInstanceId"],
        "contextHash": context["contextHash"],
        "carrierFeatures": copy.deepcopy(manifest["carrierFeatures"]),
        "manifestHash": manifest["manifestHash"],
        "handle": copy.deepcopy(handle),
        "status": "READY",
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**core, "resultHash": stable_hash(core)}


def _gh_comment(comment_id: int) -> dict[str, Any]:
    proc = subprocess.run(
        ["gh", "api", f"repos/{REPOSITORY}/issues/comments/{comment_id}"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise HostedAgentCycleError("HOSTED_AGENT_EVIDENCE_UNAVAILABLE", str(comment_id))
    try:
        value = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise HostedAgentCycleError("HOSTED_AGENT_EVIDENCE_INVALID", str(comment_id)) from exc
    if not isinstance(value, dict) or value.get("user", {}).get("login") != "github-actions[bot]":
        raise HostedAgentCycleError("HOSTED_AGENT_EVIDENCE_ACTOR_INVALID", str(comment_id))
    return value


def _remote_result_payload(comment_id: int) -> dict[str, Any]:
    body = _gh_comment(comment_id).get("body")
    marker = "MOBILIPRESENTER_REMOTE_CANONICAL_RESULT_V0_1\n"
    if not isinstance(body, str) or not body.startswith(marker):
        raise HostedAgentCycleError("HOSTED_AGENT_EVIDENCE_MARKER_INVALID", str(comment_id))
    raw = body[len(marker):].strip()
    if raw.startswith("```json") and raw.endswith("```"):
        raw = raw[len("```json"): -len("```")].strip()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HostedAgentCycleError("HOSTED_AGENT_EVIDENCE_INVALID", str(comment_id)) from exc
    try:
        remote_canonical_execution.validate_receipt(value)
    except RuntimeError as exc:
        raise HostedAgentCycleError("HOSTED_AGENT_EVIDENCE_RECEIPT_INVALID", str(comment_id)) from exc
    return value


def normalize_remote_evidence(receipt: dict[str, Any]) -> dict[str, Any]:
    remote_canonical_execution.validate_receipt(receipt)
    evidence = receipt["evidence"]
    kind = evidence.get("kind")
    if kind == "transition-receipt":
        return {
            "kind": "transition-receipt",
            "plan": copy.deepcopy(evidence["plan"]),
            "receipt": copy.deepcopy(evidence["receipt"]),
        }
    if kind == "git-mutation-plan-readback":
        return {
            "kind": "git-mutation-plan-readback",
            "plan": copy.deepcopy(evidence["plan"]),
            "observed": copy.deepcopy(evidence["observed"]),
        }
    if kind == "git-mutation-bundle-readback":
        return {
            "kind": "git-mutation-bundle-readback",
            "bundle": copy.deepcopy(evidence["bundle"]),
            "providerReadback": copy.deepcopy(evidence["providerReadback"]),
        }
    raise HostedAgentCycleError("HOSTED_AGENT_EVIDENCE_KIND_UNSUPPORTED")


def _validate_close_binding(
    command: dict[str, Any], manifest: dict[str, Any], context: dict[str, Any]
) -> None:
    validate_begin_manifest(manifest, context)
    try:
        agent_cycle_identity.validate_hosted_binding(
            command["begin"], command["actor"], manifest
        )
    except RuntimeError as exc:
        code = str(exc).split(":", 1)[0]
        if code == "AGENT_CYCLE_IDENTITY_BEGIN_MISMATCH":
            raise HostedAgentCycleError("HOSTED_AGENT_BEGIN_REF_MISMATCH") from exc
        raise HostedAgentCycleError("HOSTED_AGENT_CYCLE_IDENTITY_MISMATCH") from exc
    if command["declaredIntent"] != manifest["declaredIntent"]:
        raise HostedAgentCycleError("HOSTED_AGENT_CYCLE_IDENTITY_MISMATCH")
    if command["machineScope"] != manifest["machineScope"]:
        raise HostedAgentCycleError("HOSTED_AGENT_SCOPE_SUBSTITUTION")


def _validate_optional_handle(
    begin_root: Path,
    context: dict[str, Any],
    manifest: dict[str, Any],
) -> None:
    path = begin_root / "handle.json"
    if not path.exists():
        return
    handle = _load_json(path)
    try:
        hosted_cycle_handle.bind(
            handle,
            context=context,
            manifest=manifest,
            repository=REPOSITORY,
        )
    except RuntimeError as exc:
        raise HostedAgentCycleError("HOSTED_AGENT_CYCLE_HANDLE_MISMATCH") from exc


def _legacy_close_from_handle(
    outer: dict[str, Any], context: dict[str, Any], manifest: dict[str, Any]
) -> dict[str, Any]:
    validate_handle_close_command(outer)
    validate_begin_manifest(manifest, context)
    try:
        binding = hosted_cycle_handle.bind(
            outer["handle"], context=context, manifest=manifest, repository=REPOSITORY
        )
    except RuntimeError as exc:
        raise HostedAgentCycleError("HOSTED_AGENT_CYCLE_HANDLE_MISMATCH") from exc
    value = {
        "schemaVersion": COMMAND_SCHEMA,
        "requestId": outer["requestId"],
        "action": "close",
        "actor": copy.deepcopy(binding["actor"]),
        "declaredIntent": manifest["declaredIntent"],
        "machineScope": manifest["machineScope"],
        "begin": copy.deepcopy(binding["begin"]),
        "evidenceCommentIds": copy.deepcopy(outer["evidenceCommentIds"]),
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return validate_command(value)


def _write_lifecycle_failure_core(
    report: dict[str, Any],
    wrapper: str,
) -> dict[str, Any]:
    blockers = report.get("blockers")
    causes = [
        {"code": code, "source": "agent-write-lifecycle-guard", "phase": "CLOSE"}
        for code in blockers
        if isinstance(code, str) and agent_failure.CODE_RE.fullmatch(code)
    ] if isinstance(blockers, list) else []
    if not causes:
        causes.append(_hosted_cause(wrapper, "CLOSE"))
        lossy = True
    else:
        causes.append(_hosted_cause(wrapper, "CLOSE"))
        lossy = False
    return _failure_core(
        phase="CLOSE",
        causes=causes,
        lossy_projection=lossy,
    )


def _require_clean_write_lifecycle(
    manifest: dict[str, Any], meta: dict[str, int], *, output_path: str
) -> None:
    if not _manifest_requires_write_lifecycle(manifest):
        return
    issue_number = manifest["source"]["issueNumber"]
    close_comment_id = meta.get("commentId")
    if not isinstance(close_comment_id, int) or isinstance(close_comment_id, bool) or close_comment_id <= 0:
        raise HostedAgentCycleError("HOSTED_AGENT_WRITE_LIFECYCLE_CLOSE_COMMENT_INVALID")

    last_report: dict[str, Any] | None = None
    for attempt in range(hosted_agent_cycle_trace.TRACE_STABILIZATION_ATTEMPTS):
        comments = trace_collect.fetch_issue_comments(REPOSITORY, issue_number)
        try:
            report = agent_write_lifecycle_guard.inspect_cycle(
                comments,
                manifest,
                close_comment_id=close_comment_id,
            )
        except agent_write_lifecycle_guard.AgentWriteLifecycleGuardError as exc:
            core = _failure_core(
                phase="CLOSE",
                causes=[{
                    "code": exc.code,
                    "source": "agent-write-lifecycle-guard",
                    "phase": "CLOSE",
                }],
                lossy_projection=False,
            )
            raise HostedAgentCycleError(exc.code, failure_core=core) from exc
        last_report = report
        if report["state"] in {"NONE", "RELEASED"}:
            _write_json(Path(output_path).with_name("agent-write-lifecycle-close.json"), report)
            return
        if attempt + 1 < hosted_agent_cycle_trace.TRACE_STABILIZATION_ATTEMPTS:
            time.sleep(hosted_agent_cycle_trace.TRACE_STABILIZATION_DELAY_SECONDS)

    assert last_report is not None
    _write_json(Path(output_path).with_name("agent-write-lifecycle-close.json"), last_report)
    if last_report["state"] == "ACTIVE":
        code = "AGENT_WRITE_LIFECYCLE_ACTIVE_AT_CLOSE"
    elif last_report["state"] == "EXPIRED":
        code = "AGENT_WRITE_LIFECYCLE_EXPIRED_AT_CLOSE"
    else:
        code = "AGENT_WRITE_LIFECYCLE_UNKNOWN_AT_CLOSE"
    raise HostedAgentCycleError(
        code,
        failure_core=_write_lifecycle_failure_core(last_report, code),
    )


def _closure_failure_core(
    closure: dict[str, Any],
    context: dict[str, Any],
    evidence: list[dict[str, Any]],
) -> dict[str, Any] | None:
    try:
        agent_cycle_close.validate_closure(closure, context, evidence=evidence)
    except Exception:
        return None
    if closure["status"] == "PASS":
        return None
    blockers = closure["receipt"].get("blockers")
    causes = [
        {"code": code, "source": "agent-cycle-close", "phase": "CLOSE"}
        for code in blockers
        if isinstance(code, str) and agent_failure.CODE_RE.fullmatch(code)
    ] if isinstance(blockers, list) else []
    lossy = not causes
    if not causes:
        causes.append(_hosted_cause("HOSTED_AGENT_CANONICAL_CLOSE_FAILED", "CLOSE"))
    causes.append(_hosted_cause("HOSTED_AGENT_CLOSE_NOT_PASS", "CLOSE"))
    return _failure_core(
        phase="CLOSE",
        status=closure["status"],
        causes=causes,
        lossy_projection=lossy,
    )


def close_from_envelope(
    command: dict[str, Any],
    meta: dict[str, int],
    *,
    begin_dir: str,
    output_path: str,
    evidence_dir: str,
) -> dict[str, Any]:
    outer = validate_transport_command(command)
    if outer["action"] != "close":
        raise HostedAgentCycleError("HOSTED_AGENT_CLOSE_ACTION_REQUIRED")
    begin_root = Path(begin_dir)
    context_path = begin_root / "context.json"
    manifest_path = begin_root / "manifest.json"
    context = _load_json(context_path)
    manifest = _load_json(manifest_path)
    effective_command = (
        _legacy_close_from_handle(outer, context, manifest)
        if outer["schemaVersion"] == COMMAND_SCHEMA_V02
        else validate_command(outer)
    )
    _validate_close_binding(effective_command, manifest, context)
    _validate_optional_handle(begin_root, context, manifest)

    if _manifest_requires_trace(manifest):
        try:
            effective_command, trace_value = hosted_agent_cycle_trace.prepare_close_stabilized(
                effective_command,
                meta,
                manifest,
                context,
                repository=REPOSITORY,
            )
        except hosted_agent_cycle_trace.HostedAgentCycleTraceError as exc:
            causes = [{
                "code": exc.code,
                "source": "hosted-agent-cycle-trace",
                "phase": "CLOSE",
            }]
            code = exc.code
            if exc.code == "EXECUTION_TRACE_INCOMPLETE":
                code = "HOSTED_AGENT_EXECUTION_TRACE_INCOMPLETE"
                causes.append(_hosted_cause(code, "CLOSE"))
            raise HostedAgentCycleError(
                code,
                failure_core=_failure_core(
                    phase="CLOSE",
                    causes=causes,
                    lossy_projection=False,
                ),
            ) from exc
        effective_command = validate_command(effective_command)
        trace_path = Path(output_path).with_name("execution-trace.json")
        _write_json(trace_path, trace_value)

    _require_clean_write_lifecycle(manifest, meta, output_path=output_path)

    evidence_root = Path(evidence_dir)
    evidence_root.mkdir(parents=True, exist_ok=True)
    evidence_paths: list[str] = []
    for index, comment_id in enumerate(effective_command["evidenceCommentIds"]):
        normalized = normalize_remote_evidence(_remote_result_payload(comment_id))
        path = evidence_root / f"evidence-{index:03d}.json"
        _write_json(path, normalized)
        evidence_paths.append(str(path))

    args = [
        "close",
        "--context", str(context_path),
        "--machine-scope", "live",
        "--json",
    ]
    for path in evidence_paths:
        args.extend(["--evidence", path])
    rc, closure = _run_agent(args)
    evidence = agent_cycle_close.load_evidence(evidence_paths)
    structured_failure = _closure_failure_core(closure, context, evidence)
    if structured_failure is not None:
        raise HostedAgentCycleError(
            "HOSTED_AGENT_CLOSE_NOT_PASS",
            failure_core=structured_failure,
        )
    if rc != 0:
        raise HostedAgentCycleError(
            "HOSTED_AGENT_CLOSE_NOT_PASS",
            failure_core=_failure_core(
                phase="CLOSE",
                causes=[
                    _hosted_cause("HOSTED_AGENT_CANONICAL_CLOSE_FAILED", "CLOSE"),
                    _hosted_cause("HOSTED_AGENT_CLOSE_NOT_PASS", "CLOSE"),
                ],
                lossy_projection=True,
            ),
        )
    agent_cycle_close.validate_closure(closure, context, evidence=evidence)
    if closure["status"] != "PASS":
        raise HostedAgentCycleError("HOSTED_AGENT_CLOSE_NOT_PASS")
    _write_json(output_path, closure)
    source = _source(meta)
    receipt = closure["receipt"]
    core = {
        "schemaVersion": CLOSE_RESULT_SCHEMA,
        "requestId": outer["requestId"],
        "commandHash": transport_command_hash(outer),
        "runId": source["runId"],
        "sourceSha": source["sourceSha"],
        "beginRunId": manifest["source"]["runId"],
        "cycleId": closure["cycleId"],
        "contextHash": manifest["contextHash"],
        "receiptHash": receipt["receiptHash"],
        "closureHash": closure["closureHash"],
        "status": "PASS",
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**core, "resultHash": stable_hash(core)}


def _correlation(command: dict[str, Any] | None) -> tuple[str | None, str | None]:
    if not isinstance(command, dict):
        return None, None
    try:
        value = validate_transport_command(command)
    except Exception:
        return None, None
    return value["requestId"], stable_hash(value)


def failure_payload(
    exc: BaseException,
    command: dict[str, Any] | None = None,
    *,
    phase: str,
) -> dict[str, Any]:
    if phase not in agent_failure.PHASES:
        raise HostedAgentCycleError("HOSTED_AGENT_FAILURE_PHASE_INVALID")
    embedded = getattr(exc, "failure_core", None)
    if isinstance(embedded, dict):
        failure_core = agent_failure.validate_failure_core(embedded)
        if failure_core["phase"] != phase:
            raise HostedAgentCycleError("HOSTED_AGENT_FAILURE_PHASE_MISMATCH")
    else:
        code = getattr(exc, "code", None)
        if not isinstance(code, str) or not agent_failure.CODE_RE.fullmatch(code):
            code = "HOSTED_AGENT_UNEXPECTED_FAILURE"
        failure_core = _failure_core(
            phase=phase,
            causes=[_hosted_cause(code, phase)],
            lossy_projection=True,
        )
    request_id, digest = _correlation(command)
    body = {
        "schemaVersion": FAILURE_SCHEMA,
        "requestId": request_id,
        "commandHash": digest,
        "status": "BLOCKED",
        "failureCore": failure_core,
    }
    value = {**body, "failureHash": stable_hash(body)}
    return agent_failure.validate_hosted_cycle_failure(value)


def _emit_output(path: str, key: str, value: str) -> None:
    with Path(path).open("a", encoding="utf-8") as handle:
        handle.write(f"{key}={value}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hosted-agent-cycle")
    sub = parser.add_subparsers(dest="command_name", required=True)

    parse = sub.add_parser("parse-event")
    parse.add_argument("--event", required=True)
    parse.add_argument("--command-out", required=True)
    parse.add_argument("--meta-out", required=True)
    parse.add_argument("--github-output", required=True)

    begin = sub.add_parser("begin")
    begin.add_argument("--command", required=True)
    begin.add_argument("--meta", required=True)
    begin.add_argument("--context", required=True)
    begin.add_argument("--manifest", required=True)
    begin.add_argument("--result", required=True)

    close = sub.add_parser("close")
    close.add_argument("--command", required=True)
    close.add_argument("--meta", required=True)
    close.add_argument("--begin-dir", required=True)
    close.add_argument("--closure", required=True)
    close.add_argument("--evidence-dir", required=True)
    close.add_argument("--result", required=True)

    failure = sub.add_parser("failure")
    failure.add_argument("--error", required=True)
    failure.add_argument("--phase", required=True, choices=sorted(agent_failure.PHASES))
    failure.add_argument("--command")
    failure.add_argument("--result", required=True)

    args = parser.parse_args(argv)
    command_value: dict[str, Any] | None = None
    try:
        if args.command_name == "parse-event":
            event = json.loads(Path(args.event).read_text(encoding="utf-8"))
            command_value, meta = parse_event(event)
            _write_json(args.command_out, command_value)
            _write_json(args.meta_out, meta)
            _emit_output(args.github_output, "action", command_value["action"])
            if command_value["action"] == "close":
                if command_value["schemaVersion"] == COMMAND_SCHEMA_V02:
                    _, locator = hosted_cycle_handle.decode_handle(
                        command_value["handle"], repository=REPOSITORY
                    )
                    _emit_output(args.github_output, "begin_run_id", str(locator["runId"]))
                    _emit_output(args.github_output, "begin_source_sha", locator["sourceSha"])
                else:
                    begin_ref = _begin_ref(command_value["begin"])
                    _emit_output(args.github_output, "begin_run_id", str(begin_ref["runId"]))
                    _emit_output(args.github_output, "begin_source_sha", begin_ref["sourceSha"])
            return 0

        command_value = _load_json(args.command) if getattr(args, "command", None) else None
        if args.command_name == "begin":
            meta = _load_json(args.meta)
            result = begin_from_envelope(
                command_value, meta, context_path=args.context, manifest_path=args.manifest
            )
        elif args.command_name == "close":
            meta = _load_json(args.meta)
            result = close_from_envelope(
                command_value,
                meta,
                begin_dir=args.begin_dir,
                output_path=args.closure,
                evidence_dir=args.evidence_dir,
            )
        else:
            exc = HostedAgentCycleError(args.error)
            result = failure_payload(exc, command_value, phase=args.phase)
        _write_json(args.result, result)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as exc:
        result_path = getattr(args, "result", None)
        if result_path:
            phase = (
                "BEGIN"
                if args.command_name == "begin"
                else "CLOSE"
                if args.command_name == "close"
                else getattr(args, "phase", "TRANSPORT")
            )
            payload = failure_payload(exc, command_value, phase=phase)
            _write_json(result_path, payload)
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
