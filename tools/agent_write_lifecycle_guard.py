from __future__ import annotations

import copy
import json
from typing import Any

from tools import agent_write_lifecycle as lifecycle, coordination, hosted_cycle_records
from tools.canonical import stable_hash
from tools.coordination_remote import GhApiTransport, GitHubCoordinationAuthority

REPORT_SCHEMA = "AgentWriteLeaseCloseReport 0.1"
PROOF_SCHEMA = "AgentWriteLifecycleGuardProof 0.1"
CURRENT_REPOSITORY = hosted_cycle_records.CURRENT_REPOSITORY
AGENT_TOOL_REQUEST_MARKER = hosted_cycle_records.AGENT_TOOL_REQUEST_MARKER
AGENT_TOOL_REQUEST_MARKER_V02 = hosted_cycle_records.AGENT_TOOL_REQUEST_MARKER_V02
WRITE_LEASE_REQUEST_MARKER_V02 = hosted_cycle_records.WRITE_LEASE_REQUEST_MARKER_V02
STATES = {"NONE", "ACTIVE", "RELEASED", "EXPIRED", "UNKNOWN"}


class AgentWriteLifecycleGuardError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


_payload = hosted_cycle_records.json_after_marker


def _json_response(response: Any, code: str) -> Any:
    try:
        return json.loads(response.body)
    except (AttributeError, json.JSONDecodeError) as exc:
        raise AgentWriteLifecycleGuardError(code) from exc


def _comments(transport: Any, issue_number: int) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for page in range(1, 101):
        value = _json_response(
            transport.request(
                "GET",
                f"repos/{lifecycle.hosted_agent_cycle.REPOSITORY}/issues/{issue_number}/comments?per_page=100&page={page}",
            ),
            "AGENT_WRITE_LIFECYCLE_COMMENTS_INVALID",
        )
        if not isinstance(value, list):
            raise AgentWriteLifecycleGuardError("AGENT_WRITE_LIFECYCLE_COMMENTS_INVALID")
        result.extend(item for item in value if isinstance(item, dict))
        if len(value) < 100:
            return result
    raise AgentWriteLifecycleGuardError("AGENT_WRITE_LIFECYCLE_COMMENTS_UNBOUNDED")


def _before(comments: list[dict[str, Any]], comment_id: int | None) -> list[dict[str, Any]]:
    if comment_id is None:
        return list(comments)
    for index, item in enumerate(comments):
        if isinstance(item, dict) and item.get("id") == comment_id:
            return comments[:index]
    raise AgentWriteLifecycleGuardError("AGENT_WRITE_LIFECYCLE_CUTOFF_INVALID")


def _window(comments: list[dict[str, Any]], begin_id: int, close_id: int) -> list[dict[str, Any]]:
    try:
        return hosted_cycle_records.window(comments, begin_id, close_id)
    except hosted_cycle_records.HostedCycleRecordError as exc:
        raise AgentWriteLifecycleGuardError("AGENT_WRITE_LIFECYCLE_WINDOW_INVALID") from exc


def _bound_results(
    view: dict[str, Any], manifest: dict[str, Any] | None = None
) -> list[tuple[int, dict[str, Any]]]:
    del manifest
    return [
        (item["commentId"], item["normalized"])
        for item in hosted_cycle_records.records_of(
            view, "write-lease-result", binding=hosted_cycle_records.STRONG
        )
    ]


def _request_count(view: dict[str, Any], manifest: dict[str, Any] | None = None) -> int:
    del manifest
    return len(hosted_cycle_records.records_of(
        view, "write-lease-request", binding=hosted_cycle_records.STRONG
    ))


def _bound_agent_tool_branches(
    view: dict[str, Any], manifest: dict[str, Any] | None = None
) -> set[str]:
    del manifest
    branches: set[str] = set()
    for item in hosted_cycle_records.records_of(
        view, "agent-tool-request", binding=hosted_cycle_records.STRONG
    ):
        branch = item["normalized"]["target"].get("branch")
        if isinstance(branch, str) and branch:
            branches.add(branch)
    return branches


def _expected_owner(actor: dict[str, Any], branch: str) -> dict[str, Any]:
    return {"role": actor["role"], "session": actor["sessionId"], "branch": branch, "pr": None}


def _matching_exact_leases(
    active: list[dict[str, Any]], *, binding: dict[str, Any]
) -> list[dict[str, Any]]:
    expected_owner = _expected_owner(binding["actor"], binding["branch"])
    resource = f"branch:{binding['branch']}"
    return [
        lease for lease in active
        if lease.get("leaseId") == binding["leaseId"]
        and lease.get("resource") == resource
        and lease.get("owner") == expected_owner
    ]


def _unbound_target_leases(
    active: list[dict[str, Any]],
    *,
    manifest: dict[str, Any],
    branches: set[str],
    bound_lease_id: str | None,
) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for branch in sorted(branches):
        expected_owner = _expected_owner(manifest["actor"], branch)
        resource = f"branch:{branch}"
        for lease in active:
            if (
                lease.get("leaseId") != bound_lease_id
                and lease.get("resource") == resource
                and lease.get("owner") == expected_owner
            ):
                found.append(lease)
    return found


def prove_active_binding(
    plan: dict[str, Any],
    *,
    cycle_instance_id: str,
    issue_number: int,
    before_comment_id: int | None,
    transport: Any | None = None,
) -> dict[str, Any]:
    carrier = transport or GhApiTransport()
    comments = _before(_comments(carrier, issue_number), before_comment_id)

    candidates: list[tuple[int, dict[str, Any]]] = []
    for comment in comments:
        if not hosted_cycle_records.result_comment_allowed(comment):
            continue
        value = _payload(comment.get("body"), lifecycle.RESULT_MARKER)
        if not isinstance(value, dict) or value.get("schemaVersion") != lifecycle.RESULT_SCHEMA:
            continue
        # Establish exact cycle claim before validating the full payload so a
        # malformed result from another cycle cannot poison this admission.
        if (
            value.get("cycleInstanceId") != cycle_instance_id
            or value.get("begin") != plan["begin"]
            or value.get("actor") != plan["actor"]
        ):
            continue
        try:
            lifecycle.validate_result(value)
        except RuntimeError as exc:
            raise AgentWriteLifecycleGuardError("AGENT_WRITE_LIFECYCLE_RESULT_INVALID") from exc
        if value["branch"] != plan["target"].get("branch"):
            continue
        comment_id = hosted_cycle_records.comment_id(comment)
        if comment_id is None:
            raise AgentWriteLifecycleGuardError("AGENT_WRITE_LIFECYCLE_RESULT_COMMENT_INVALID")
        candidates.append((comment_id, value))

    if not candidates:
        raise AgentWriteLifecycleGuardError("AGENT_WRITE_LIFECYCLE_BINDING_REQUIRED")

    comment_id, result = candidates[-1]
    binding = result["binding"]
    if binding["state"] != "ACTIVE":
        raise AgentWriteLifecycleGuardError("AGENT_WRITE_LIFECYCLE_NOT_ACTIVE")

    authority = GitHubCoordinationAuthority(transport=carrier)
    observation = authority.observe()
    if lifecycle.binding_is_expired(binding, observation.authority_now):
        raise AgentWriteLifecycleGuardError("AGENT_WRITE_LIFECYCLE_BINDING_EXPIRED")

    active = coordination.active_leases(observation.state, observation.authority_now)
    matching = _matching_exact_leases(active, binding=binding)
    if len(matching) != 1:
        raise AgentWriteLifecycleGuardError("AGENT_WRITE_LIFECYCLE_BINDING_AUTHORITY_MISMATCH")

    core = {
        "schemaVersion": PROOF_SCHEMA,
        "cycleInstanceId": cycle_instance_id,
        "requestHash": plan["requestHash"],
        "planHash": plan["planHash"],
        "actor": copy.deepcopy(plan["actor"]),
        "branch": binding["branch"],
        "bindingHash": binding["bindingHash"],
        "lifecycleResultHash": result["resultHash"],
        "lifecycleResultCommentId": comment_id,
        "leaseId": binding["leaseId"],
        "authorityHead": observation.head_sha,
        "authorityNow": observation.authority_now.isoformat().replace("+00:00", "Z"),
        "status": "PASS",
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**core, "proofHash": stable_hash(core)}


def validate_active_binding_proof(value: Any) -> dict[str, Any]:
    fields = {
        "schemaVersion", "cycleInstanceId", "requestHash", "planHash", "actor",
        "branch", "bindingHash", "lifecycleResultHash",
        "lifecycleResultCommentId", "leaseId", "authorityHead", "authorityNow",
        "status", "readOnly", "semanticAuthority", "authorizesMutation", "proofHash",
    }
    if not isinstance(value, dict) or set(value) != fields or value.get("schemaVersion") != PROOF_SCHEMA:
        raise AgentWriteLifecycleGuardError("AGENT_WRITE_LIFECYCLE_PROOF_INVALID")
    if value.get("status") != "PASS" or value.get("readOnly") is not True:
        raise AgentWriteLifecycleGuardError("AGENT_WRITE_LIFECYCLE_PROOF_INVALID")
    if value.get("semanticAuthority") is not False or value.get("authorizesMutation") is not False:
        raise AgentWriteLifecycleGuardError("AGENT_WRITE_LIFECYCLE_PROOF_INVALID")
    for field in ("requestHash", "planHash", "bindingHash", "lifecycleResultHash", "proofHash"):
        raw = value.get(field)
        if not isinstance(raw, str) or len(raw) != 64 or any(ch not in "0123456789abcdef" for ch in raw):
            raise AgentWriteLifecycleGuardError("AGENT_WRITE_LIFECYCLE_PROOF_INVALID")
    if (
        not isinstance(value.get("lifecycleResultCommentId"), int)
        or isinstance(value["lifecycleResultCommentId"], bool)
        or value["lifecycleResultCommentId"] <= 0
    ):
        raise AgentWriteLifecycleGuardError("AGENT_WRITE_LIFECYCLE_PROOF_INVALID")

    core = {key: copy.deepcopy(item) for key, item in value.items() if key != "proofHash"}
    if value.get("proofHash") != stable_hash(core):
        raise AgentWriteLifecycleGuardError("AGENT_WRITE_LIFECYCLE_PROOF_HASH_MISMATCH")
    return value


def inspect_cycle(
    comments: list[dict[str, Any]],
    manifest: dict[str, Any],
    *,
    close_comment_id: int,
    transport: Any | None = None,
) -> dict[str, Any]:
    carrier = transport or GhApiTransport()
    try:
        view = hosted_cycle_records.collect(
            comments, manifest, close_comment_id=close_comment_id
        )
    except hosted_cycle_records.HostedCycleRecordError as exc:
        if exc.code.startswith("HOSTED_CYCLE_RECORD_WINDOW_"):
            raise AgentWriteLifecycleGuardError("AGENT_WRITE_LIFECYCLE_WINDOW_INVALID") from exc
        raise AgentWriteLifecycleGuardError(exc.code) from exc
    results = _bound_results(view, manifest)
    request_count = _request_count(view, manifest)
    target_branches = _bound_agent_tool_branches(view, manifest)

    authority = GitHubCoordinationAuthority(transport=carrier)
    observation = authority.observe()
    active = coordination.active_leases(observation.state, observation.authority_now)

    state = "NONE"
    blockers: list[str] = []
    latest_binding: dict[str, Any] | None = None
    matching: list[dict[str, Any]] = []

    if results:
        latest_binding = results[-1][1]["binding"]
        matching = _matching_exact_leases(active, binding=latest_binding)
        if latest_binding["state"] == "RELEASED":
            if matching:
                state = "UNKNOWN"
                blockers.append("AGENT_WRITE_LIFECYCLE_RELEASE_READBACK_MISMATCH")
            else:
                state = "RELEASED"
        elif lifecycle.binding_is_expired(latest_binding, observation.authority_now):
            if matching:
                state = "UNKNOWN"
                blockers.append("AGENT_WRITE_LIFECYCLE_EXPIRED_BUT_LEASE_ACTIVE")
            else:
                state = "EXPIRED"
        elif len(matching) == 1:
            state = "ACTIVE"
            blockers.append("AGENT_WRITE_LIFECYCLE_ACTIVE_AT_CLOSE")
        else:
            state = "UNKNOWN"
            blockers.append("AGENT_WRITE_LIFECYCLE_BINDING_AUTHORITY_MISMATCH")
    elif request_count:
        state = "UNKNOWN"
        blockers.append("AGENT_WRITE_LIFECYCLE_REQUEST_WITHOUT_TERMINAL")

    bound_lease_id = latest_binding["leaseId"] if latest_binding is not None else None
    unbound = _unbound_target_leases(
        active,
        manifest=manifest,
        branches=target_branches,
        bound_lease_id=bound_lease_id,
    )
    if unbound and state in {"NONE", "RELEASED"}:
        state = "UNKNOWN"
        blockers.append("AGENT_WRITE_LIFECYCLE_UNBOUND_ACTIVE_LEASE")

    core = {
        "schemaVersion": REPORT_SCHEMA,
        "cycleInstanceId": view["cycleInstanceId"],
        "actor": copy.deepcopy(manifest["actor"]),
        "state": state,
        "latestBindingHash": latest_binding["bindingHash"] if latest_binding is not None else None,
        "authorityHead": observation.head_sha,
        "authorityNow": observation.authority_now.isoformat().replace("+00:00", "Z"),
        "matchingLeaseIds": sorted(lease["leaseId"] for lease in matching),
        "blockers": sorted(set(blockers)),
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**core, "reportHash": stable_hash(core)}


def validate_report(value: Any) -> dict[str, Any]:
    fields = {
        "schemaVersion", "cycleInstanceId", "actor", "state",
        "latestBindingHash", "authorityHead", "authorityNow",
        "matchingLeaseIds", "blockers", "readOnly", "semanticAuthority",
        "authorizesMutation", "reportHash",
    }
    if (
        not isinstance(value, dict)
        or set(value) != fields
        or value.get("schemaVersion") != REPORT_SCHEMA
        or value.get("state") not in STATES
    ):
        raise AgentWriteLifecycleGuardError("AGENT_WRITE_LIFECYCLE_REPORT_INVALID")
    core = {key: copy.deepcopy(item) for key, item in value.items() if key != "reportHash"}
    if value.get("reportHash") != stable_hash(core):
        raise AgentWriteLifecycleGuardError("AGENT_WRITE_LIFECYCLE_REPORT_HASH_MISMATCH")
    return value
