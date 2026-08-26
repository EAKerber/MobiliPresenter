from __future__ import annotations

import copy
import re
from datetime import datetime, timezone
from typing import Any

from tools import coordination, git_observation, hosted_agent_cycle
from tools import remote_canonical_execution as remote
from tools.canonical import stable_hash
from tools.coordination_remote import GhApiTransport, GitHubCoordinationAuthority

REQUEST_MARKER = "MOBILIPRESENTER_AGENT_WRITE_LEASE_REQUEST_V0_1"
DISPATCH_MARKER = "MOBILIPRESENTER_AGENT_WRITE_LEASE_DISPATCH_V0_1"
RESULT_MARKER = "MOBILIPRESENTER_AGENT_WRITE_LEASE_RESULT_V0_1"
ATTEMPT_MARKER = "MOBILIPRESENTER_AGENT_WRITE_LEASE_ATTEMPT_V0_1"

REQUEST_SCHEMA = "AgentWriteLeaseRequest 0.1"
DISPATCH_SCHEMA = "AgentWriteLeaseDispatch 0.1"
RESULT_SCHEMA = "AgentWriteLeaseResult 0.1"
FAILURE_SCHEMA = "AgentWriteLeaseFailure 0.1"
ATTEMPT_SCHEMA = "AgentWriteLeaseAttempt 0.1"
BINDING_SCHEMA = "AgentWriteLeaseBinding 0.1"

ACTIONS = {"acquire", "renew", "release"}
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
CYCLE_RE = re.compile(r"^cycle-instance-[0-9a-f]{24}$")
ACTOR_FIELDS = {"role", "workerId", "sessionId"}
BEGIN_FIELDS = {"runId", "sourceSha", "contextHash"}
REQUEST_FIELDS = {
    "schemaVersion", "requestId", "action", "begin", "actor", "branch",
    "expectedAuthorityHead", "expectedBranchHead", "ttlSeconds",
    "semanticAuthority", "authorizesMutation",
}
SOURCE_FIELDS = {"issueNumber", "requestCommentId", "hostedRunId", "semanticHostSha"}


class AgentWriteLifecycleError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}" if detail else code)


def _text(value: Any, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AgentWriteLifecycleError(code)
    return value.strip()


def _sha(value: Any, code: str) -> str:
    if not isinstance(value, str) or not SHA_RE.fullmatch(value):
        raise AgentWriteLifecycleError(code)
    return value


def _hash(value: Any, code: str) -> str:
    if not isinstance(value, str) or not HASH_RE.fullmatch(value):
        raise AgentWriteLifecycleError(code)
    return value


def _positive_int(value: Any, code: str) -> int:
    if isinstance(value, str) and value.isdigit():
        value = int(value)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise AgentWriteLifecycleError(code)
    return value


def _actor(value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != ACTOR_FIELDS:
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_ACTOR_INVALID")
    return {key: _text(value[key], "AGENT_WRITE_LIFECYCLE_ACTOR_INVALID") for key in sorted(ACTOR_FIELDS)}


def _begin(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != BEGIN_FIELDS:
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_BEGIN_INVALID")
    return {
        "runId": _positive_int(value["runId"], "AGENT_WRITE_LIFECYCLE_BEGIN_INVALID"),
        "sourceSha": _sha(value["sourceSha"], "AGENT_WRITE_LIFECYCLE_BEGIN_INVALID"),
        "contextHash": _hash(value["contextHash"], "AGENT_WRITE_LIFECYCLE_BEGIN_INVALID"),
    }


def validate_request(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != REQUEST_FIELDS:
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_REQUEST_FIELDS_INVALID")
    if value.get("schemaVersion") != REQUEST_SCHEMA:
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_REQUEST_SCHEMA_UNSUPPORTED")
    _text(value.get("requestId"), "AGENT_WRITE_LIFECYCLE_REQUEST_ID_INVALID")
    if value.get("action") not in ACTIONS:
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_ACTION_INVALID")
    if _begin(value.get("begin")) != value["begin"] or _actor(value.get("actor")) != value["actor"]:
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_REQUEST_NOT_CANONICAL")
    branch = git_observation.canonical_branch(_text(value.get("branch"), "AGENT_WRITE_LIFECYCLE_BRANCH_INVALID"))
    if branch != value["branch"] or branch == "main":
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_BRANCH_FORBIDDEN")
    _sha(value.get("expectedAuthorityHead"), "AGENT_WRITE_LIFECYCLE_AUTHORITY_HEAD_INVALID")
    _sha(value.get("expectedBranchHead"), "AGENT_WRITE_LIFECYCLE_BRANCH_HEAD_INVALID")
    ttl = value.get("ttlSeconds")
    if value["action"] == "acquire":
        if not isinstance(ttl, int) or isinstance(ttl, bool) or ttl <= 0 or ttl > coordination.MAX_TTL_SECONDS:
            raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_TTL_INVALID")
    elif ttl is not None:
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_TTL_FORBIDDEN")
    if value.get("semanticAuthority") is not False or value.get("authorizesMutation") is not False:
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_REQUEST_MUST_NOT_AUTHORIZE")
    return value


def request_hash(value: dict[str, Any]) -> str:
    return stable_hash(validate_request(value))


def validate_begin_binding(request: dict[str, Any], manifest: dict[str, Any], context: dict[str, Any]) -> None:
    validate_request(request)
    hosted_agent_cycle.validate_begin_manifest(manifest, context)
    begin = request["begin"]
    source = manifest["source"]
    if begin["runId"] != source["runId"] or begin["sourceSha"] != source["sourceSha"] or begin["contextHash"] != manifest["contextHash"]:
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_BEGIN_MISMATCH")
    if request["actor"] != manifest["actor"]:
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_IDENTITY_MISMATCH")
    semantic = context.get("semanticContext")
    if not isinstance(semantic, dict) or semantic.get("declaredIntent") != "governed-mutation":
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_INTENT_FORBIDDEN")


def _owner(request: dict[str, Any]) -> dict[str, Any]:
    return {"role": request["actor"]["role"], "session": request["actor"]["sessionId"], "branch": request["branch"], "pr": None}


def _active_session_leases(observation: Any, session_id: str) -> list[dict[str, Any]]:
    return [
        lease for lease in coordination.active_leases(observation.state, observation.authority_now)
        if isinstance(lease.get("owner"), dict) and lease["owner"].get("session") == session_id
    ]


def _check_session_scope(request: dict[str, Any], observation: Any) -> list[dict[str, Any]]:
    resource = f"branch:{request['branch']}"
    session_leases = _active_session_leases(observation, request["actor"]["sessionId"])
    if request["action"] == "acquire":
        if session_leases:
            raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_SESSION_ALREADY_OWNS_LEASE")
        return []
    matching = [lease for lease in session_leases if lease.get("resource") == resource]
    if len(matching) != 1:
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_BOUND_LEASE_NOT_FOUND")
    if request["action"] == "renew" and len(session_leases) != 1:
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_RENEW_SCOPE_AMBIGUOUS")
    return matching


def prepare_dispatch(
    request: dict[str, Any], manifest: dict[str, Any], context: dict[str, Any], *,
    issue_number: int, request_comment_id: int, hosted_run_id: int, transport: Any | None = None,
) -> dict[str, Any]:
    validate_begin_binding(request, manifest, context)
    carrier = transport or GhApiTransport()
    observed_branch = git_observation.observe_branch(request["branch"], transport=carrier)
    if observed_branch["branchHead"] != request["expectedBranchHead"]:
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_BRANCH_DRIFT")
    authority = GitHubCoordinationAuthority(transport=carrier)
    authority_observation = authority.observe()
    if authority_observation.head_sha != request["expectedAuthorityHead"]:
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_AUTHORITY_DRIFT")
    matching_before = _check_session_scope(request, authority_observation)

    action = request["action"]
    transition_id = f"agent-write-{request['requestId']}"
    payload: dict[str, Any] = {"owner": _owner(request), "transitionId": transition_id}
    if action == "acquire":
        payload.update({
            "resources": [f"branch:{request['branch']}"],
            "reason": f"Agent write lifecycle {manifest['cycleInstanceId']}",
            "ttlSeconds": request["ttlSeconds"],
        })
    elif action == "release":
        payload.update({"resources": [f"branch:{request['branch']}"], "mine": False})

    command = {
        "schemaVersion": "RemoteCanonicalCommand 0.1",
        "executionId": transition_id,
        "kind": "domain",
        "actor": copy.deepcopy(request["actor"]),
        "declaredIntent": {"intent": "agent-write-lease-lifecycle", "cycleInstanceId": manifest["cycleInstanceId"], "action": action},
        "target": {"domain": "coordination", "action": action, "subject": {"kind": "coordination", "id": "leases"}},
        "expected": {"authorityRevision": authority_observation.head_sha},
        "payload": payload,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    remote.validate_command(command)
    core = {
        "schemaVersion": DISPATCH_SCHEMA,
        "cycleInstanceId": manifest["cycleInstanceId"],
        "requestHash": request_hash(request),
        "action": action,
        "begin": copy.deepcopy(request["begin"]),
        "actor": copy.deepcopy(request["actor"]),
        "branch": request["branch"],
        "expectedBranchHead": request["expectedBranchHead"],
        "authorityHead": authority_observation.head_sha,
        "leaseIdsBefore": sorted(lease["leaseId"] for lease in matching_before),
        "command": command,
        "commandHash": remote.command_hash(command),
        "source": {
            "issueNumber": _positive_int(issue_number, "AGENT_WRITE_LIFECYCLE_SOURCE_INVALID"),
            "requestCommentId": _positive_int(request_comment_id, "AGENT_WRITE_LIFECYCLE_SOURCE_INVALID"),
            "hostedRunId": _positive_int(hosted_run_id, "AGENT_WRITE_LIFECYCLE_SOURCE_INVALID"),
            "semanticHostSha": request["begin"]["sourceSha"],
        },
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**core, "dispatchHash": stable_hash(core)}


def validate_dispatch(value: Any) -> dict[str, Any]:
    fields = {
        "schemaVersion", "cycleInstanceId", "requestHash", "action", "begin", "actor", "branch",
        "expectedBranchHead", "authorityHead", "leaseIdsBefore", "command", "commandHash", "source",
        "semanticAuthority", "authorizesMutation", "dispatchHash",
    }
    if not isinstance(value, dict) or set(value) != fields or value.get("schemaVersion") != DISPATCH_SCHEMA:
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_DISPATCH_INVALID")
    if not isinstance(value.get("cycleInstanceId"), str) or not CYCLE_RE.fullmatch(value["cycleInstanceId"]):
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_CYCLE_INVALID")
    _hash(value.get("requestHash"), "AGENT_WRITE_LIFECYCLE_DISPATCH_INVALID")
    _begin(value.get("begin")); _actor(value.get("actor"))
    if value.get("action") not in ACTIONS:
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_ACTION_INVALID")
    git_observation.canonical_branch(value.get("branch"))
    _sha(value.get("expectedBranchHead"), "AGENT_WRITE_LIFECYCLE_DISPATCH_INVALID")
    _sha(value.get("authorityHead"), "AGENT_WRITE_LIFECYCLE_DISPATCH_INVALID")
    lease_ids = value.get("leaseIdsBefore")
    if not isinstance(lease_ids, list) or lease_ids != sorted(set(lease_ids)) or any(not isinstance(item, str) or not item for item in lease_ids):
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_LEASE_IDS_INVALID")
    command = remote.validate_command(value.get("command"))
    if value.get("commandHash") != remote.command_hash(command):
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_COMMAND_HASH_MISMATCH")
    source = value.get("source")
    if not isinstance(source, dict) or set(source) != SOURCE_FIELDS:
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_SOURCE_INVALID")
    _positive_int(source.get("issueNumber"), "AGENT_WRITE_LIFECYCLE_SOURCE_INVALID")
    _positive_int(source.get("requestCommentId"), "AGENT_WRITE_LIFECYCLE_SOURCE_INVALID")
    _positive_int(source.get("hostedRunId"), "AGENT_WRITE_LIFECYCLE_SOURCE_INVALID")
    _sha(source.get("semanticHostSha"), "AGENT_WRITE_LIFECYCLE_SOURCE_INVALID")
    if value.get("semanticAuthority") is not False or value.get("authorizesMutation") is not False:
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_DISPATCH_MUST_NOT_AUTHORIZE")
    core = {key: copy.deepcopy(item) for key, item in value.items() if key != "dispatchHash"}
    if value.get("dispatchHash") != stable_hash(core):
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_DISPATCH_HASH_MISMATCH")
    return value


def build_attempt(dispatch: dict[str, Any], *, run_id: int, host_sha: str) -> dict[str, Any]:
    validate_dispatch(dispatch)
    core = {
        "schemaVersion": ATTEMPT_SCHEMA,
        "dispatchHash": dispatch["dispatchHash"],
        "requestHash": dispatch["requestHash"],
        "runId": _positive_int(run_id, "AGENT_WRITE_LIFECYCLE_ATTEMPT_INVALID"),
        "hostSha": _sha(host_sha, "AGENT_WRITE_LIFECYCLE_ATTEMPT_INVALID"),
        "status": "STARTED",
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**core, "attemptHash": stable_hash(core)}


def build_binding(dispatch: dict[str, Any], *, authority_head_after: str, active_lease: dict[str, Any] | None, receipt_hash: str) -> dict[str, Any]:
    validate_dispatch(dispatch)
    state = "RELEASED" if dispatch["action"] == "release" else "ACTIVE"
    core = {
        "schemaVersion": BINDING_SCHEMA,
        "cycleInstanceId": dispatch["cycleInstanceId"],
        "begin": copy.deepcopy(dispatch["begin"]),
        "actor": copy.deepcopy(dispatch["actor"]),
        "branch": dispatch["branch"],
        "state": state,
        "leaseId": None if active_lease is None else active_lease.get("leaseId"),
        "expiresAt": None if active_lease is None else active_lease.get("expiresAt"),
        "authorityHead": _sha(authority_head_after, "AGENT_WRITE_LIFECYCLE_AUTHORITY_HEAD_INVALID"),
        "dispatchHash": dispatch["dispatchHash"],
        "receiptHash": _hash(receipt_hash, "AGENT_WRITE_LIFECYCLE_RECEIPT_HASH_INVALID"),
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**core, "bindingHash": stable_hash(core)}


def validate_binding(value: Any) -> dict[str, Any]:
    fields = {
        "schemaVersion", "cycleInstanceId", "begin", "actor", "branch", "state", "leaseId", "expiresAt",
        "authorityHead", "dispatchHash", "receiptHash", "semanticAuthority", "authorizesMutation", "bindingHash",
    }
    if not isinstance(value, dict) or set(value) != fields or value.get("schemaVersion") != BINDING_SCHEMA:
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_BINDING_INVALID")
    if not isinstance(value.get("cycleInstanceId"), str) or not CYCLE_RE.fullmatch(value["cycleInstanceId"]):
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_BINDING_INVALID")
    _begin(value.get("begin")); _actor(value.get("actor")); git_observation.canonical_branch(value.get("branch"))
    if value.get("state") not in {"ACTIVE", "RELEASED"}:
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_BINDING_INVALID")
    if value["state"] == "ACTIVE":
        _text(value.get("leaseId"), "AGENT_WRITE_LIFECYCLE_BINDING_INVALID")
        _text(value.get("expiresAt"), "AGENT_WRITE_LIFECYCLE_BINDING_INVALID")
    elif value.get("leaseId") is not None or value.get("expiresAt") is not None:
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_BINDING_INVALID")
    _sha(value.get("authorityHead"), "AGENT_WRITE_LIFECYCLE_BINDING_INVALID")
    _hash(value.get("dispatchHash"), "AGENT_WRITE_LIFECYCLE_BINDING_INVALID")
    _hash(value.get("receiptHash"), "AGENT_WRITE_LIFECYCLE_BINDING_INVALID")
    if value.get("semanticAuthority") is not False or value.get("authorizesMutation") is not False:
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_BINDING_INVALID")
    core = {key: copy.deepcopy(item) for key, item in value.items() if key != "bindingHash"}
    if value.get("bindingHash") != stable_hash(core):
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_BINDING_HASH_MISMATCH")
    return value


def build_success_result(request: dict[str, Any], dispatch: dict[str, Any], *, receipt: dict[str, Any], binding: dict[str, Any]) -> dict[str, Any]:
    validate_request(request); validate_dispatch(dispatch); validate_binding(binding); remote.validate_receipt(receipt)
    core = {
        "schemaVersion": RESULT_SCHEMA,
        "requestId": request["requestId"],
        "requestHash": request_hash(request),
        "action": request["action"],
        "begin": copy.deepcopy(request["begin"]),
        "cycleInstanceId": dispatch["cycleInstanceId"],
        "actor": copy.deepcopy(request["actor"]),
        "branch": request["branch"],
        "dispatchHash": dispatch["dispatchHash"],
        "binding": copy.deepcopy(binding),
        "remoteReceipt": copy.deepcopy(receipt),
        "remoteReceiptHash": receipt["receiptHash"],
        "status": "PASS",
        "blockers": [],
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**core, "resultHash": stable_hash(core)}


def validate_result(value: Any) -> dict[str, Any]:
    fields = {
        "schemaVersion", "requestId", "requestHash", "action", "begin", "cycleInstanceId", "actor", "branch",
        "dispatchHash", "binding", "remoteReceipt", "remoteReceiptHash", "status", "blockers",
        "semanticAuthority", "authorizesMutation", "resultHash",
    }
    if not isinstance(value, dict) or set(value) != fields or value.get("schemaVersion") != RESULT_SCHEMA:
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_RESULT_INVALID")
    if value.get("status") != "PASS" or value.get("blockers") != [] or value.get("action") not in ACTIONS:
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_RESULT_INVALID")
    _text(value.get("requestId"), "AGENT_WRITE_LIFECYCLE_RESULT_INVALID")
    _hash(value.get("requestHash"), "AGENT_WRITE_LIFECYCLE_RESULT_INVALID")
    _begin(value.get("begin")); _actor(value.get("actor")); validate_binding(value.get("binding"))
    receipt = remote.validate_receipt(value.get("remoteReceipt"))
    if value.get("remoteReceiptHash") != receipt["receiptHash"]:
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_RESULT_INVALID")
    if value.get("semanticAuthority") is not False or value.get("authorizesMutation") is not False:
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_RESULT_INVALID")
    core = {key: copy.deepcopy(item) for key, item in value.items() if key != "resultHash"}
    if value.get("resultHash") != stable_hash(core):
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_RESULT_HASH_MISMATCH")
    return value


def build_failure(request: dict[str, Any] | None, *, status: str, blockers: list[str], authority_head: str | None = None) -> dict[str, Any]:
    if status not in {"BLOCKED", "UNKNOWN"}:
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_FAILURE_STATUS_INVALID")
    core = {
        "schemaVersion": FAILURE_SCHEMA,
        "requestId": request.get("requestId") if isinstance(request, dict) else None,
        "requestHash": request_hash(request) if isinstance(request, dict) else None,
        "action": request.get("action") if isinstance(request, dict) else None,
        "begin": copy.deepcopy(request.get("begin")) if isinstance(request, dict) else None,
        "actor": copy.deepcopy(request.get("actor")) if isinstance(request, dict) else None,
        "branch": request.get("branch") if isinstance(request, dict) else None,
        "authorityHead": authority_head,
        "status": status,
        "blockers": sorted(set(blockers)),
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**core, "failureHash": stable_hash(core)}


def binding_is_expired(binding: dict[str, Any], now: datetime) -> bool:
    validate_binding(binding)
    if binding["state"] != "ACTIVE":
        return False
    parsed = datetime.fromisoformat(binding["expiresAt"].replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_TIME_INVALID")
    return parsed.astimezone(timezone.utc) <= now.astimezone(timezone.utc)
