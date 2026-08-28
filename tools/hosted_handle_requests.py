from __future__ import annotations

import copy
import re
from typing import Any

from tools import agent_cycle_identity, hosted_cycle_handle
from tools.agent_tools import contracts

CYCLE_MARKER_V02 = "MOBILIPRESENTER_AGENT_CYCLE_REQUEST_V0_2"
TOOL_MARKER_V02 = "MOBILIPRESENTER_AGENT_TOOL_REQUEST_V0_2"
WRITE_LEASE_MARKER_V02 = "MOBILIPRESENTER_AGENT_WRITE_LEASE_REQUEST_V0_2"

CYCLE_SCHEMA = "HostedAgentCycleCommand 0.2"
TOOL_SCHEMA = "HostedAgentToolRequest 0.2"
WRITE_LEASE_SCHEMA = "HostedAgentWriteLeaseRequest 0.2"

CYCLE_FIELDS = {
    "schemaVersion", "requestId", "action", "handle", "evidenceCommentIds",
    "semanticAuthority", "authorizesMutation",
}
TOOL_FIELDS = {
    "schemaVersion", "requestId", "handle", "toolId", "target", "input",
    "semanticAuthority", "authorizesMutation",
}
WRITE_LEASE_FIELDS = {
    "schemaVersion", "requestId", "handle", "action", "branch",
    "expectedAuthorityHead", "expectedBranchHead", "expectedBindingHash",
    "ttlSeconds", "semanticAuthority", "authorizesMutation",
}
WRITE_LEASE_ACTIONS = {"acquire", "renew", "release"}
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
HASH_RE = re.compile(r"^[0-9a-f]{64}$")


class HostedHandleRequestError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _request_id(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HostedHandleRequestError("HOSTED_HANDLE_REQUEST_ID_INVALID")
    return value


def _boundary(value: dict[str, Any]) -> None:
    if value.get("semanticAuthority") is not False or value.get("authorizesMutation") is not False:
        raise HostedHandleRequestError("HOSTED_HANDLE_REQUEST_MUST_NOT_AUTHORIZE")


def _handle(value: Any, repository: str) -> dict[str, Any]:
    try:
        handle, _ = hosted_cycle_handle.decode_handle(value, repository=repository)
    except RuntimeError as exc:
        raise HostedHandleRequestError("HOSTED_HANDLE_REQUEST_HANDLE_INVALID") from exc
    return handle


def validate_cycle_close(value: Any, *, repository: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != CYCLE_FIELDS:
        raise HostedHandleRequestError("HOSTED_HANDLE_CYCLE_FIELDS_INVALID")
    if value.get("schemaVersion") != CYCLE_SCHEMA or value.get("action") != "close":
        raise HostedHandleRequestError("HOSTED_HANDLE_CYCLE_INVALID")
    _request_id(value.get("requestId"))
    _handle(value.get("handle"), repository)
    evidence = value.get("evidenceCommentIds")
    if (
        not isinstance(evidence, list)
        or any(not isinstance(item, int) or isinstance(item, bool) or item <= 0 for item in evidence)
        or len(evidence) != len(set(evidence))
    ):
        raise HostedHandleRequestError("HOSTED_HANDLE_CYCLE_EVIDENCE_INVALID")
    _boundary(value)
    return value


def validate_tool(value: Any, *, repository: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != TOOL_FIELDS:
        raise HostedHandleRequestError("HOSTED_HANDLE_TOOL_FIELDS_INVALID")
    if value.get("schemaVersion") != TOOL_SCHEMA:
        raise HostedHandleRequestError("HOSTED_HANDLE_TOOL_SCHEMA_UNSUPPORTED")
    request_id = value.get("requestId")
    tool_id = value.get("toolId")
    if not isinstance(request_id, str) or contracts.REQUEST_ID_RE.fullmatch(request_id) is None:
        raise HostedHandleRequestError("HOSTED_HANDLE_TOOL_REQUEST_ID_INVALID")
    if not isinstance(tool_id, str) or contracts.ID_RE.fullmatch(tool_id) is None:
        raise HostedHandleRequestError("HOSTED_HANDLE_TOOL_ID_INVALID")
    if not isinstance(value.get("target"), dict) or not isinstance(value.get("input"), dict):
        raise HostedHandleRequestError("HOSTED_HANDLE_TOOL_PAYLOAD_INVALID")
    _handle(value.get("handle"), repository)
    _boundary(value)
    return value


def validate_write_lease(value: Any, *, repository: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != WRITE_LEASE_FIELDS:
        raise HostedHandleRequestError("HOSTED_HANDLE_WRITE_LEASE_FIELDS_INVALID")
    if value.get("schemaVersion") != WRITE_LEASE_SCHEMA:
        raise HostedHandleRequestError("HOSTED_HANDLE_WRITE_LEASE_SCHEMA_UNSUPPORTED")
    _request_id(value.get("requestId"))
    action = value.get("action")
    if action not in WRITE_LEASE_ACTIONS:
        raise HostedHandleRequestError("HOSTED_HANDLE_WRITE_LEASE_ACTION_INVALID")
    branch = value.get("branch")
    if not isinstance(branch, str) or not branch.strip() or branch == "main":
        raise HostedHandleRequestError("HOSTED_HANDLE_WRITE_LEASE_BRANCH_INVALID")
    for key in ("expectedAuthorityHead", "expectedBranchHead"):
        item = value.get(key)
        if not isinstance(item, str) or SHA_RE.fullmatch(item) is None:
            raise HostedHandleRequestError("HOSTED_HANDLE_WRITE_LEASE_HEAD_INVALID")
    prior = value.get("expectedBindingHash")
    ttl = value.get("ttlSeconds")
    if action == "acquire":
        if prior is not None or not isinstance(ttl, int) or isinstance(ttl, bool) or ttl <= 0:
            raise HostedHandleRequestError("HOSTED_HANDLE_WRITE_LEASE_ACQUIRE_INVALID")
    else:
        if not isinstance(prior, str) or HASH_RE.fullmatch(prior) is None or ttl is not None:
            raise HostedHandleRequestError("HOSTED_HANDLE_WRITE_LEASE_CONTINUATION_INVALID")
    _handle(value.get("handle"), repository)
    _boundary(value)
    return value


def matches_manifest(handle: Any, manifest: Any, *, repository: str) -> bool:
    if not isinstance(manifest, dict):
        return False
    try:
        value, _ = hosted_cycle_handle.decode_handle(handle, repository=repository)
        expected_token = hosted_cycle_handle.build_resume_token(manifest)
        actor = agent_cycle_identity.canonical_actor(manifest.get("actor"))
    except RuntimeError:
        return False
    return (
        value["cycleId"] == manifest.get("cycleId")
        and value["cycleInstanceId"] == manifest.get("cycleInstanceId")
        and value["context"]["contextHash"] == manifest.get("contextHash")
        and value["actor"] == actor
        and value["resumeToken"] == expected_token
    )


def build_cycle_legacy(
    outer: dict[str, Any],
    *,
    begin: dict[str, Any],
    actor: dict[str, Any],
    declared_intent: str,
    machine_scope: str,
) -> dict[str, Any]:
    return {
        "schemaVersion": "HostedAgentCycleCommand 0.1",
        "requestId": outer["requestId"],
        "action": "close",
        "actor": copy.deepcopy(actor),
        "declaredIntent": declared_intent,
        "machineScope": machine_scope,
        "begin": copy.deepcopy(begin),
        "evidenceCommentIds": copy.deepcopy(outer["evidenceCommentIds"]),
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


def build_tool_inner(
    outer: dict[str, Any], *, begin: dict[str, Any], actor: dict[str, Any]
) -> dict[str, Any]:
    value = {
        "schemaVersion": contracts.REQUEST_SCHEMA,
        "requestId": outer["requestId"],
        "begin": copy.deepcopy(begin),
        "actor": copy.deepcopy(actor),
        "toolId": outer["toolId"],
        "target": copy.deepcopy(outer["target"]),
        "input": copy.deepcopy(outer["input"]),
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return contracts.validate_request(value)


def build_write_lease_inner(
    outer: dict[str, Any], *, begin: dict[str, Any], actor: dict[str, Any]
) -> dict[str, Any]:
    return {
        "schemaVersion": "AgentWriteLeaseRequest 0.1",
        "requestId": outer["requestId"],
        "action": outer["action"],
        "begin": copy.deepcopy(begin),
        "actor": copy.deepcopy(actor),
        "branch": outer["branch"],
        "expectedAuthorityHead": outer["expectedAuthorityHead"],
        "expectedBranchHead": outer["expectedBranchHead"],
        "expectedBindingHash": outer["expectedBindingHash"],
        "ttlSeconds": outer["ttlSeconds"],
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
