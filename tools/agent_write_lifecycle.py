from __future__ import annotations

import copy
import json
import re
from datetime import datetime, timezone
from typing import Any

from tools import agent_cycle_identity, coordination, git_observation, hosted_agent_cycle
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
CYCLE_RE = agent_cycle_identity.CYCLE_INSTANCE_RE
ACTOR_FIELDS = agent_cycle_identity.ACTOR_FIELDS
BEGIN_FIELDS = agent_cycle_identity.BEGIN_FIELDS
REQUEST_FIELDS = {
    "schemaVersion", "requestId", "action", "begin", "actor", "branch",
    "expectedAuthorityHead", "expectedBranchHead", "expectedBindingHash",
    "ttlSeconds", "semanticAuthority", "authorizesMutation",
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
    try:
        return agent_cycle_identity.canonical_actor(value)
    except RuntimeError as exc:
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_ACTOR_INVALID") from exc


def _begin(value: Any) -> dict[str, Any]:
    try:
        return agent_cycle_identity.canonical_begin(value)
    except RuntimeError as exc:
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_BEGIN_INVALID") from exc


def validate_request(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != REQUEST_FIELDS:
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_REQUEST_FIELDS_INVALID")
    if value.get("schemaVersion") != REQUEST_SCHEMA:
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_REQUEST_SCHEMA_UNSUPPORTED")
    _text(value.get("requestId"), "AGENT_WRITE_LIFECYCLE_REQUEST_ID_INVALID")
    action = value.get("action")
    if action not in ACTIONS:
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_ACTION_INVALID")
    if _begin(value.get("begin")) != value["begin"] or _actor(value.get("actor")) != value["actor"]:
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_REQUEST_NOT_CANONICAL")
    branch = git_observation.canonical_branch(
        _text(value.get("branch"), "AGENT_WRITE_LIFECYCLE_BRANCH_INVALID")
    )
    if branch != value["branch"] or branch == "main":
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_BRANCH_FORBIDDEN")
    _sha(value.get("expectedAuthorityHead"), "AGENT_WRITE_LIFECYCLE_AUTHORITY_HEAD_INVALID")
    _sha(value.get("expectedBranchHead"), "AGENT_WRITE_LIFECYCLE_BRANCH_HEAD_INVALID")

    expected_binding = value.get("expectedBindingHash")
    ttl = value.get("ttlSeconds")
    if action == "acquire":
        if expected_binding is not None:
            raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_PRIOR_BINDING_FORBIDDEN")
        if (
            not isinstance(ttl, int)
            or isinstance(ttl, bool)
            or ttl <= 0
            or ttl > coordination.MAX_TTL_SECONDS
        ):
            raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_TTL_INVALID")
    else:
        _hash(expected_binding, "AGENT_WRITE_LIFECYCLE_PRIOR_BINDING_REQUIRED")
        if ttl is not None:
            raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_TTL_FORBIDDEN")

    if value.get("semanticAuthority") is not False or value.get("authorizesMutation") is not False:
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_REQUEST_MUST_NOT_AUTHORIZE")
    return value


def request_hash(value: dict[str, Any]) -> str:
    return stable_hash(validate_request(value))


def validate_begin_binding(
    request: dict[str, Any],
    manifest: dict[str, Any],
    context: dict[str, Any],
) -> None:
    validate_request(request)
    hosted_agent_cycle.validate_begin_manifest(manifest, context)
    try:
        agent_cycle_identity.validate_hosted_binding(
            request["begin"], request["actor"], manifest
        )
    except RuntimeError as exc:
        code = str(exc).split(":", 1)[0]
        if code == "AGENT_CYCLE_IDENTITY_BEGIN_MISMATCH":
            raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_BEGIN_MISMATCH") from exc
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_IDENTITY_MISMATCH") from exc
    semantic = context.get("semanticContext")
    if not isinstance(semantic, dict) or semantic.get("declaredIntent") != "governed-mutation":
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_INTENT_FORBIDDEN")


def _owner(request: dict[str, Any]) -> dict[str, Any]:
    return {
        "role": request["actor"]["role"],
        "session": request["actor"]["sessionId"],
        "branch": request["branch"],
        "pr": None,
    }


def _json_response(response: Any, code: str) -> Any:
    try:
        return json.loads(response.body)
    except (AttributeError, json.JSONDecodeError) as exc:
        raise AgentWriteLifecycleError(code) from exc


def _payload(body: Any, marker: str) -> Any | None:
    prefix = marker + "\n"
    if not isinstance(body, str) or not body.startswith(prefix):
        return None
    raw = body[len(prefix):].strip()
    if raw.startswith("```json") and raw.endswith("```"):
        raw = raw[len("```json"):-len("```")].strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _comments_before(
    transport: Any,
    issue_number: int,
    request_comment_id: int,
) -> list[dict[str, Any]]:
    comments: list[dict[str, Any]] = []
    for page in range(1, 101):
        value = _json_response(
            transport.request(
                "GET",
                f"repos/{hosted_agent_cycle.REPOSITORY}/issues/{issue_number}/comments?per_page=100&page={page}",
            ),
            "AGENT_WRITE_LIFECYCLE_COMMENTS_INVALID",
        )
        if not isinstance(value, list):
            raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_COMMENTS_INVALID")
        comments.extend(item for item in value if isinstance(item, dict))
        if any(item.get("id") == request_comment_id for item in value if isinstance(item, dict)):
            break
        if len(value) < 100:
            break
    for index, item in enumerate(comments):
        if item.get("id") == request_comment_id:
            return comments[:index]
    raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_REQUEST_COMMENT_NOT_FOUND")


def _latest_binding_before(
    transport: Any,
    *,
    issue_number: int,
    request_comment_id: int,
    request: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[str, Any] | None:
    expected_begin = request["begin"]
    expected_actor = request["actor"]
    expected_cycle = manifest["cycleInstanceId"]
    candidates: list[dict[str, Any]] = []
    for comment in _comments_before(transport, issue_number, request_comment_id):
        user = comment.get("user")
        if not isinstance(user, dict) or user.get("login") != "github-actions[bot]":
            continue
        value = _payload(comment.get("body"), RESULT_MARKER)
        if not isinstance(value, dict) or value.get("schemaVersion") != RESULT_SCHEMA:
            continue
        validate_result(value)
        if (
            value["begin"] == expected_begin
            and value["actor"] == expected_actor
            and value["cycleInstanceId"] == expected_cycle
            and value["branch"] == request["branch"]
        ):
            candidates.append(value["binding"])
    if not candidates:
        return None
    return candidates[-1]


def _active_session_leases(observation: Any, session_id: str) -> list[dict[str, Any]]:
    return [
        lease
        for lease in coordination.active_leases(observation.state, observation.authority_now)
        if isinstance(lease.get("owner"), dict)
        and lease["owner"].get("session") == session_id
    ]


def _exact_active_lease(
    request: dict[str, Any],
    observation: Any,
    *,
    lease_id: str,
) -> dict[str, Any]:
    resource = f"branch:{request['branch']}"
    expected_owner = _owner(request)
    matches = [
        lease
        for lease in coordination.active_leases(observation.state, observation.authority_now)
        if lease.get("leaseId") == lease_id
        and lease.get("resource") == resource
        and lease.get("owner") == expected_owner
    ]
    if len(matches) != 1:
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_BOUND_LEASE_NOT_FOUND")
    return matches[0]


def _prepare_previous_binding(
    request: dict[str, Any],
    manifest: dict[str, Any],
    observation: Any,
    *,
    issue_number: int,
    request_comment_id: int,
    transport: Any,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    action = request["action"]
    latest = _latest_binding_before(
        transport,
        issue_number=issue_number,
        request_comment_id=request_comment_id,
        request=request,
        manifest=manifest,
    )
    if action == "acquire":
        if latest is not None:
            raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_ALREADY_STARTED")
        return None, None

    if latest is None:
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_BINDING_REQUIRED")
    if latest["bindingHash"] != request["expectedBindingHash"]:
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_BINDING_DRIFT")
    if latest["state"] != "ACTIVE":
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_NOT_ACTIVE")

    bound_lease = _exact_active_lease(
        request,
        observation,
        lease_id=latest["leaseId"],
    )
    if action == "renew":
        session_leases = _active_session_leases(
            observation,
            request["actor"]["sessionId"],
        )
        if len(session_leases) != 1 or session_leases[0].get("leaseId") != latest["leaseId"]:
            raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_RENEW_SCOPE_AMBIGUOUS")
    return latest, bound_lease


def prepare_dispatch(
    request: dict[str, Any],
    manifest: dict[str, Any],
    context: dict[str, Any],
    *,
    issue_number: int,
    request_comment_id: int,
    hosted_run_id: int,
    transport: Any | None = None,
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

    previous_binding, bound_lease = _prepare_previous_binding(
        request,
        manifest,
        authority_observation,
        issue_number=issue_number,
        request_comment_id=request_comment_id,
        transport=carrier,
    )

    action = request["action"]
    transition_id = f"agent-write-{request['requestId']}"
    payload: dict[str, Any] = {
        "owner": _owner(request),
        "transitionId": transition_id,
    }
    if action == "acquire":
        payload.update(
            {
                "resources": [f"branch:{request['branch']}"],
                "reason": f"Agent write lifecycle {manifest['cycleInstanceId']}",
                "ttlSeconds": request["ttlSeconds"],
            }
        )
    elif action == "release":
        payload.update(
            {
                "resources": [f"branch:{request['branch']}"],
                "mine": False,
            }
        )

    command = {
        "schemaVersion": "RemoteCanonicalCommand 0.1",
        "executionId": transition_id,
        "kind": "domain",
        "actor": copy.deepcopy(request["actor"]),
        "declaredIntent": {
            "intent": "agent-write-lease-lifecycle",
            "cycleInstanceId": manifest["cycleInstanceId"],
            "action": action,
        },
        "target": {
            "domain": "coordination",
            "action": action,
            "subject": {"kind": "coordination", "id": "leases"},
        },
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
        "previousBindingHash": (
            None if previous_binding is None else previous_binding["bindingHash"]
        ),
        "previousLeaseId": (
            None if bound_lease is None else bound_lease["leaseId"]
        ),
        "command": command,
        "commandHash": remote.command_hash(command),
        "source": {
            "issueNumber": _positive_int(
                issue_number, "AGENT_WRITE_LIFECYCLE_SOURCE_INVALID"
            ),
            "requestCommentId": _positive_int(
                request_comment_id, "AGENT_WRITE_LIFECYCLE_SOURCE_INVALID"
            ),
            "hostedRunId": _positive_int(
                hosted_run_id, "AGENT_WRITE_LIFECYCLE_SOURCE_INVALID"
            ),
            "semanticHostSha": request["begin"]["sourceSha"],
        },
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**core, "dispatchHash": stable_hash(core)}


def validate_dispatch(value: Any) -> dict[str, Any]:
    fields = {
        "schemaVersion", "cycleInstanceId", "requestHash", "action", "begin",
        "actor", "branch", "expectedBranchHead", "authorityHead",
        "previousBindingHash", "previousLeaseId", "command", "commandHash",
        "source", "semanticAuthority", "authorizesMutation", "dispatchHash",
    }
    if (
        not isinstance(value, dict)
        or set(value) != fields
        or value.get("schemaVersion") != DISPATCH_SCHEMA
    ):
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_DISPATCH_INVALID")
    if (
        not isinstance(value.get("cycleInstanceId"), str)
        or not CYCLE_RE.fullmatch(value["cycleInstanceId"])
    ):
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_CYCLE_INVALID")
    _hash(value.get("requestHash"), "AGENT_WRITE_LIFECYCLE_DISPATCH_INVALID")
    _begin(value.get("begin"))
    _actor(value.get("actor"))
    action = value.get("action")
    if action not in ACTIONS:
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_ACTION_INVALID")
    git_observation.canonical_branch(value.get("branch"))
    _sha(value.get("expectedBranchHead"), "AGENT_WRITE_LIFECYCLE_DISPATCH_INVALID")
    _sha(value.get("authorityHead"), "AGENT_WRITE_LIFECYCLE_DISPATCH_INVALID")

    previous_binding_hash = value.get("previousBindingHash")
    previous_lease_id = value.get("previousLeaseId")
    if action == "acquire":
        if previous_binding_hash is not None or previous_lease_id is not None:
            raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_DISPATCH_INVALID")
    else:
        _hash(
            previous_binding_hash,
            "AGENT_WRITE_LIFECYCLE_DISPATCH_PRIOR_BINDING_INVALID",
        )
        _text(
            previous_lease_id,
            "AGENT_WRITE_LIFECYCLE_DISPATCH_PRIOR_LEASE_INVALID",
        )

    command = remote.validate_command(value.get("command"))
    if value.get("commandHash") != remote.command_hash(command):
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_COMMAND_HASH_MISMATCH")

    source = value.get("source")
    if not isinstance(source, dict) or set(source) != SOURCE_FIELDS:
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_SOURCE_INVALID")
    _positive_int(source.get("issueNumber"), "AGENT_WRITE_LIFECYCLE_SOURCE_INVALID")
    _positive_int(
        source.get("requestCommentId"),
        "AGENT_WRITE_LIFECYCLE_SOURCE_INVALID",
    )
    _positive_int(
        source.get("hostedRunId"),
        "AGENT_WRITE_LIFECYCLE_SOURCE_INVALID",
    )
    _sha(source.get("semanticHostSha"), "AGENT_WRITE_LIFECYCLE_SOURCE_INVALID")

    if value.get("semanticAuthority") is not False or value.get("authorizesMutation") is not False:
        raise AgentWriteLifecycleError(
            "AGENT_WRITE_LIFECYCLE_DISPATCH_MUST_NOT_AUTHORIZE"
        )

    core = {
        key: copy.deepcopy(item)
        for key, item in value.items()
        if key != "dispatchHash"
    }
    if value.get("dispatchHash") != stable_hash(core):
        raise AgentWriteLifecycleError(
            "AGENT_WRITE_LIFECYCLE_DISPATCH_HASH_MISMATCH"
        )
    return value


def build_attempt(
    dispatch: dict[str, Any],
    *,
    run_id: int,
    host_sha: str,
) -> dict[str, Any]:
    validate_dispatch(dispatch)
    core = {
        "schemaVersion": ATTEMPT_SCHEMA,
        "dispatchHash": dispatch["dispatchHash"],
        "requestHash": dispatch["requestHash"],
        "runId": _positive_int(
            run_id, "AGENT_WRITE_LIFECYCLE_ATTEMPT_INVALID"
        ),
        "hostSha": _sha(
            host_sha, "AGENT_WRITE_LIFECYCLE_ATTEMPT_INVALID"
        ),
        "status": "STARTED",
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**core, "attemptHash": stable_hash(core)}


def build_binding(
    dispatch: dict[str, Any],
    *,
    authority_head_after: str,
    active_lease: dict[str, Any] | None,
    receipt_hash: str,
) -> dict[str, Any]:
    validate_dispatch(dispatch)
    action = dispatch["action"]
    state = "RELEASED" if action == "release" else "ACTIVE"

    if action == "acquire":
        if not isinstance(active_lease, dict):
            raise AgentWriteLifecycleError(
                "AGENT_WRITE_LIFECYCLE_ACTIVE_READBACK_MISMATCH"
            )
        lease_id = _text(
            active_lease.get("leaseId"),
            "AGENT_WRITE_LIFECYCLE_ACTIVE_READBACK_MISMATCH",
        )
        expires_at = _text(
            active_lease.get("expiresAt"),
            "AGENT_WRITE_LIFECYCLE_ACTIVE_READBACK_MISMATCH",
        )
        previous_binding_hash = None
    elif action == "renew":
        if (
            not isinstance(active_lease, dict)
            or active_lease.get("leaseId") != dispatch["previousLeaseId"]
        ):
            raise AgentWriteLifecycleError(
                "AGENT_WRITE_LIFECYCLE_ACTIVE_READBACK_MISMATCH"
            )
        lease_id = dispatch["previousLeaseId"]
        expires_at = _text(
            active_lease.get("expiresAt"),
            "AGENT_WRITE_LIFECYCLE_ACTIVE_READBACK_MISMATCH",
        )
        previous_binding_hash = dispatch["previousBindingHash"]
    else:
        if active_lease is not None:
            raise AgentWriteLifecycleError(
                "AGENT_WRITE_LIFECYCLE_RELEASE_READBACK_MISMATCH"
            )
        lease_id = dispatch["previousLeaseId"]
        expires_at = None
        previous_binding_hash = dispatch["previousBindingHash"]

    core = {
        "schemaVersion": BINDING_SCHEMA,
        "cycleInstanceId": dispatch["cycleInstanceId"],
        "begin": copy.deepcopy(dispatch["begin"]),
        "actor": copy.deepcopy(dispatch["actor"]),
        "branch": dispatch["branch"],
        "state": state,
        "leaseId": lease_id,
        "expiresAt": expires_at,
        "previousBindingHash": previous_binding_hash,
        "authorityHead": _sha(
            authority_head_after,
            "AGENT_WRITE_LIFECYCLE_AUTHORITY_HEAD_INVALID",
        ),
        "dispatchHash": dispatch["dispatchHash"],
        "receiptHash": _hash(
            receipt_hash,
            "AGENT_WRITE_LIFECYCLE_RECEIPT_HASH_INVALID",
        ),
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**core, "bindingHash": stable_hash(core)}


def validate_binding(value: Any) -> dict[str, Any]:
    fields = {
        "schemaVersion", "cycleInstanceId", "begin", "actor", "branch",
        "state", "leaseId", "expiresAt", "previousBindingHash",
        "authorityHead", "dispatchHash", "receiptHash", "semanticAuthority",
        "authorizesMutation", "bindingHash",
    }
    if (
        not isinstance(value, dict)
        or set(value) != fields
        or value.get("schemaVersion") != BINDING_SCHEMA
    ):
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_BINDING_INVALID")
    if (
        not isinstance(value.get("cycleInstanceId"), str)
        or not CYCLE_RE.fullmatch(value["cycleInstanceId"])
    ):
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_BINDING_INVALID")

    _begin(value.get("begin"))
    _actor(value.get("actor"))
    git_observation.canonical_branch(value.get("branch"))

    state = value.get("state")
    if state not in {"ACTIVE", "RELEASED"}:
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_BINDING_INVALID")

    _text(value.get("leaseId"), "AGENT_WRITE_LIFECYCLE_BINDING_INVALID")
    if state == "ACTIVE":
        _text(value.get("expiresAt"), "AGENT_WRITE_LIFECYCLE_BINDING_INVALID")
    elif value.get("expiresAt") is not None:
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_BINDING_INVALID")

    previous_binding_hash = value.get("previousBindingHash")
    if previous_binding_hash is not None:
        _hash(
            previous_binding_hash,
            "AGENT_WRITE_LIFECYCLE_BINDING_INVALID",
        )

    _sha(value.get("authorityHead"), "AGENT_WRITE_LIFECYCLE_BINDING_INVALID")
    _hash(value.get("dispatchHash"), "AGENT_WRITE_LIFECYCLE_BINDING_INVALID")
    _hash(value.get("receiptHash"), "AGENT_WRITE_LIFECYCLE_BINDING_INVALID")
    if value.get("semanticAuthority") is not False or value.get("authorizesMutation") is not False:
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_BINDING_INVALID")

    core = {
        key: copy.deepcopy(item)
        for key, item in value.items()
        if key != "bindingHash"
    }
    if value.get("bindingHash") != stable_hash(core):
        raise AgentWriteLifecycleError(
            "AGENT_WRITE_LIFECYCLE_BINDING_HASH_MISMATCH"
        )
    return value


def build_success_result(
    request: dict[str, Any],
    dispatch: dict[str, Any],
    *,
    receipt: dict[str, Any],
    binding: dict[str, Any],
) -> dict[str, Any]:
    validate_request(request)
    validate_dispatch(dispatch)
    validate_binding(binding)
    remote.validate_receipt(receipt)

    if binding["cycleInstanceId"] != dispatch["cycleInstanceId"]:
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_BINDING_MISMATCH")
    if binding["previousBindingHash"] != dispatch["previousBindingHash"]:
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_BINDING_MISMATCH")
    if (
        dispatch["action"] != "acquire"
        and binding["leaseId"] != dispatch["previousLeaseId"]
    ):
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_BINDING_MISMATCH")

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
        "schemaVersion", "requestId", "requestHash", "action", "begin",
        "cycleInstanceId", "actor", "branch", "dispatchHash", "binding",
        "remoteReceipt", "remoteReceiptHash", "status", "blockers",
        "semanticAuthority", "authorizesMutation", "resultHash",
    }
    if (
        not isinstance(value, dict)
        or set(value) != fields
        or value.get("schemaVersion") != RESULT_SCHEMA
    ):
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_RESULT_INVALID")
    if (
        value.get("status") != "PASS"
        or value.get("blockers") != []
        or value.get("action") not in ACTIONS
    ):
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_RESULT_INVALID")

    _text(value.get("requestId"), "AGENT_WRITE_LIFECYCLE_RESULT_INVALID")
    _hash(value.get("requestHash"), "AGENT_WRITE_LIFECYCLE_RESULT_INVALID")
    _begin(value.get("begin"))
    _actor(value.get("actor"))
    binding = validate_binding(value.get("binding"))
    if binding["cycleInstanceId"] != value.get("cycleInstanceId"):
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_RESULT_INVALID")
    if binding["begin"] != value["begin"] or binding["actor"] != value["actor"]:
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_RESULT_INVALID")
    if binding["branch"] != value["branch"]:
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_RESULT_INVALID")

    receipt = remote.validate_receipt(value.get("remoteReceipt"))
    if value.get("remoteReceiptHash") != receipt["receiptHash"]:
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_RESULT_INVALID")
    if value.get("semanticAuthority") is not False or value.get("authorizesMutation") is not False:
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_RESULT_INVALID")

    core = {
        key: copy.deepcopy(item)
        for key, item in value.items()
        if key != "resultHash"
    }
    if value.get("resultHash") != stable_hash(core):
        raise AgentWriteLifecycleError("AGENT_WRITE_LIFECYCLE_RESULT_HASH_MISMATCH")
    return value


def build_failure(
    request: dict[str, Any] | None,
    *,
    status: str,
    blockers: list[str],
    authority_head: str | None = None,
) -> dict[str, Any]:
    if status not in {"BLOCKED", "UNKNOWN"}:
        raise AgentWriteLifecycleError(
            "AGENT_WRITE_LIFECYCLE_FAILURE_STATUS_INVALID"
        )
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
