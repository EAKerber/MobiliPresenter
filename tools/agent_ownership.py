from __future__ import annotations

import copy
import json
from typing import Any

from tools import (
    agent_write_lifecycle as lifecycle,
    coordination,
    git_observation,
    hosted_agent_cycle,
    hosted_cycle_handle,
    hosted_handle_requests,
    hosted_issue_bus,
)
from tools.canonical import stable_hash
from tools.coordination_remote import GitHubCoordinationAuthority

RESULT_SCHEMA = "AgentOwnershipEnsureResult 0.1"
STATUSES = {"PASS", "PENDING", "BLOCKED", "UNKNOWN"}
DISPOSITIONS = {"REUSED", "ACQUIRE_REQUESTED", "RELEASE_REQUESTED", "NEW_CYCLE_REQUIRED", "NO_OWNERSHIP", "RELEASED", "UNKNOWN"}


class AgentOwnershipError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}" if detail else code)


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


def _find_write_lease_request(
    comments: list[dict[str, Any]],
    request: dict[str, Any],
) -> int | None:
    matches: list[int] = []
    for comment in comments:
        payload = _payload(
            comment.get("body") if isinstance(comment, dict) else None,
            hosted_handle_requests.WRITE_LEASE_MARKER_V02,
        )
        if payload != request:
            continue
        comment_id = comment.get("id")
        if not isinstance(comment_id, int) or isinstance(comment_id, bool) or comment_id <= 0:
            raise AgentOwnershipError("AGENT_OWNERSHIP_REQUEST_COMMENT_INVALID")
        matches.append(comment_id)
    if len(matches) > 1:
        raise AgentOwnershipError("AGENT_OWNERSHIP_REQUEST_DUPLICATE")
    return matches[0] if matches else None


def _latest_lifecycle_result(
    comments: list[dict[str, Any]],
    *,
    begin: dict[str, Any],
    actor: dict[str, Any],
    cycle_instance_id: str,
    branch: str,
) -> dict[str, Any] | None:
    latest: dict[str, Any] | None = None
    for comment in comments:
        user = comment.get("user") if isinstance(comment, dict) else None
        if not isinstance(user, dict) or user.get("login") != "github-actions[bot]":
            continue
        value = _payload(comment.get("body"), lifecycle.RESULT_MARKER)
        if not isinstance(value, dict) or value.get("schemaVersion") != lifecycle.RESULT_SCHEMA:
            continue
        if (
            value.get("begin") != begin
            or value.get("actor") != actor
            or value.get("cycleInstanceId") != cycle_instance_id
            or value.get("branch") != branch
        ):
            continue
        try:
            latest = copy.deepcopy(lifecycle.validate_result(value))
        except RuntimeError as exc:
            raise AgentOwnershipError("AGENT_OWNERSHIP_LIFECYCLE_RESULT_INVALID") from exc
    return latest


def _expected_owner(actor: dict[str, Any], branch: str) -> dict[str, Any]:
    return {
        "role": actor["role"],
        "session": actor["sessionId"],
        "branch": branch,
        "pr": None,
    }


def _matching_leases(
    leases: list[dict[str, Any]],
    *,
    lease_id: str,
    actor: dict[str, Any],
    branch: str,
) -> list[dict[str, Any]]:
    owner = _expected_owner(actor, branch)
    resource = f"branch:{branch}"
    return [
        copy.deepcopy(lease)
        for lease in leases
        if lease.get("leaseId") == lease_id
        and lease.get("resource") == resource
        and lease.get("owner") == owner
    ]


def _outer_request(
    *,
    request_id: str,
    handle: Any,
    action: str,
    branch: str,
    authority_head: str,
    branch_head: str | None,
    binding_hash: str | None,
) -> dict[str, Any]:
    value = {
        "schemaVersion": hosted_handle_requests.WRITE_LEASE_SCHEMA,
        "requestId": request_id,
        "handle": copy.deepcopy(handle),
        "action": action,
        "branch": branch,
        "expectedAuthorityHead": authority_head,
        "expectedBranchHead": branch_head,
        "expectedBindingHash": binding_hash,
        "ttlSeconds": coordination.DEFAULT_TTL_SECONDS if action == "acquire" else None,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return hosted_handle_requests.validate_write_lease(
        value, repository=hosted_agent_cycle.REPOSITORY
    )


def _result(
    *,
    status: str,
    disposition: str,
    branch: str,
    authority_head: str,
    branch_head: str,
    request: dict[str, Any] | None = None,
    binding: dict[str, Any] | None = None,
    request_comment_id: int | None = None,
    blockers: list[str] | None = None,
) -> dict[str, Any]:
    if status not in STATUSES or disposition not in DISPOSITIONS:
        raise AgentOwnershipError("AGENT_OWNERSHIP_RESULT_INVALID")
    core = {
        "schemaVersion": RESULT_SCHEMA,
        "status": status,
        "disposition": disposition,
        "branch": branch,
        "branchHead": branch_head,
        "authorityHead": authority_head,
        "request": copy.deepcopy(request),
        "requestCommentId": request_comment_id,
        "bindingHash": binding.get("bindingHash") if isinstance(binding, dict) else None,
        "leaseId": binding.get("leaseId") if isinstance(binding, dict) else None,
        "expiresAt": binding.get("expiresAt") if isinstance(binding, dict) else None,
        "blockers": sorted(set(blockers or [])),
        "readOnly": request is None,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**core, "resultHash": stable_hash(core)}


def ensure_ownership(
    *,
    handle: Any,
    branch: str,
    request_id: str,
    submit: bool = False,
    transport: Any | None = None,
) -> dict[str, Any]:
    try:
        handle_value, locator = hosted_cycle_handle.decode_handle(
            handle, repository=hosted_agent_cycle.REPOSITORY
        )
    except RuntimeError as exc:
        raise AgentOwnershipError("AGENT_OWNERSHIP_HANDLE_INVALID") from exc

    branch = git_observation.canonical_branch(branch)
    if branch == "main":
        raise AgentOwnershipError("AGENT_OWNERSHIP_BRANCH_FORBIDDEN")
    if not isinstance(request_id, str) or not request_id.strip():
        raise AgentOwnershipError("AGENT_OWNERSHIP_REQUEST_ID_INVALID")
    if transport is None:
        raise AgentOwnershipError("BLOCKED_EXECUTION_SURFACE")
    carrier = transport

    begin = {
        "runId": locator["runId"],
        "sourceSha": locator["sourceSha"],
        "contextHash": locator["contextHash"],
    }
    actor = copy.deepcopy(handle_value["actor"])
    cycle_instance_id = handle_value["cycleInstanceId"]
    issue_number = locator["issueNumber"]

    observed_branch = git_observation.observe_branch(branch, transport=carrier)
    branch_head = observed_branch["branchHead"]
    authority = GitHubCoordinationAuthority(transport=carrier)
    observation = authority.observe()
    try:
        comments = hosted_issue_bus.list_comments(
            carrier,
            repository=hosted_agent_cycle.REPOSITORY,
            issue_number=issue_number,
        )
    except hosted_issue_bus.HostedIssueBusError as exc:
        code = (
            "AGENT_OWNERSHIP_COMMENTS_UNBOUNDED"
            if exc.code == "HOSTED_ISSUE_BUS_COMMENTS_UNBOUNDED"
            else "AGENT_OWNERSHIP_COMMENTS_INVALID"
        )
        raise AgentOwnershipError(code) from exc
    latest = _latest_lifecycle_result(
        comments,
        begin=begin,
        actor=actor,
        cycle_instance_id=cycle_instance_id,
        branch=branch,
    )

    request: dict[str, Any] | None = None
    binding: dict[str, Any] | None = None
    disposition: str
    status: str
    blockers: list[str] = []

    if latest is None:
        request = _outer_request(
            request_id=request_id,
            handle=handle,
            action="acquire",
            branch=branch,
            authority_head=observation.head_sha,
            branch_head=branch_head,
            binding_hash=None,
        )
        status = "PENDING"
        disposition = "ACQUIRE_REQUESTED"
    else:
        binding = latest["binding"]
        if binding["state"] == "RELEASED":
            status = "BLOCKED"
            disposition = "NEW_CYCLE_REQUIRED"
            blockers = ["AGENT_OWNERSHIP_REACQUIRE_REQUIRES_NEW_CYCLE"]
        elif lifecycle.binding_is_expired(binding, observation.authority_now):
            materialized = _matching_leases(
                observation.state["leases"],
                lease_id=binding["leaseId"],
                actor=actor,
                branch=branch,
            )
            if len(materialized) != 1:
                status = "UNKNOWN"
                disposition = "UNKNOWN"
                blockers = ["AGENT_OWNERSHIP_BINDING_AUTHORITY_MISMATCH"]
            else:
                request = _outer_request(
                    request_id=request_id,
                    handle=handle,
                    action="release",
                    branch=branch,
                    authority_head=observation.head_sha,
                    branch_head=None,
                    binding_hash=binding["bindingHash"],
                )
                status = "PENDING"
                disposition = "RELEASE_REQUESTED"
        else:
            active = coordination.active_leases(
                observation.state, observation.authority_now
            )
            matching = _matching_leases(
                active,
                lease_id=binding["leaseId"],
                actor=actor,
                branch=branch,
            )
            if len(matching) == 1:
                status = "PASS"
                disposition = "REUSED"
            else:
                status = "UNKNOWN"
                disposition = "UNKNOWN"
                blockers = ["AGENT_OWNERSHIP_BINDING_AUTHORITY_MISMATCH"]

    comment_id: int | None = (
        _find_write_lease_request(comments, request)
        if request is not None
        else None
    )
    if request is not None and comment_id is None and submit:
        body = (
            hosted_handle_requests.WRITE_LEASE_MARKER_V02
            + "\n"
            + json.dumps(request, separators=(",", ":"), ensure_ascii=False)
        )
        try:
            comment_id = hosted_issue_bus.post_comment(
                carrier,
                repository=hosted_agent_cycle.REPOSITORY,
                issue_number=issue_number,
                body=body,
            )
        except hosted_issue_bus.HostedIssueBusError as exc:
            raise AgentOwnershipError("AGENT_OWNERSHIP_SUBMIT_INVALID") from exc

    return _result(
        status=status,
        disposition=disposition,
        branch=branch,
        authority_head=observation.head_sha,
        branch_head=branch_head,
        request=request,
        binding=binding,
        request_comment_id=comment_id,
        blockers=blockers,
    )


def _lifecycle_snapshot(
    *,
    handle: Any,
    branch: str,
    transport: Any,
) -> dict[str, Any]:
    try:
        handle_value, locator = hosted_cycle_handle.decode_handle(
            handle, repository=hosted_agent_cycle.REPOSITORY
        )
    except RuntimeError as exc:
        raise AgentOwnershipError("AGENT_OWNERSHIP_HANDLE_INVALID") from exc
    branch = git_observation.canonical_branch(branch)
    if branch == "main":
        raise AgentOwnershipError("AGENT_OWNERSHIP_BRANCH_FORBIDDEN")
    actor = copy.deepcopy(handle_value["actor"])
    begin = {
        "runId": locator["runId"],
        "sourceSha": locator["sourceSha"],
        "contextHash": locator["contextHash"],
    }
    authority = GitHubCoordinationAuthority(transport=transport)
    observation = authority.observe()
    issue_number = locator["issueNumber"]
    try:
        comments = hosted_issue_bus.list_comments(
            transport,
            repository=hosted_agent_cycle.REPOSITORY,
            issue_number=issue_number,
        )
    except hosted_issue_bus.HostedIssueBusError as exc:
        code = (
            "AGENT_OWNERSHIP_COMMENTS_UNBOUNDED"
            if exc.code == "HOSTED_ISSUE_BUS_COMMENTS_UNBOUNDED"
            else "AGENT_OWNERSHIP_COMMENTS_INVALID"
        )
        raise AgentOwnershipError(code) from exc
    latest = _latest_lifecycle_result(
        comments,
        begin=begin,
        actor=actor,
        cycle_instance_id=handle_value["cycleInstanceId"],
        branch=branch,
    )
    state = "NONE"
    binding = None
    if latest is not None:
        binding = latest["binding"]
        if binding["state"] == "RELEASED":
            state = "RELEASED"
        elif lifecycle.binding_is_expired(binding, observation.authority_now):
            materialized = _matching_leases(
                observation.state["leases"],
                lease_id=binding["leaseId"],
                actor=actor,
                branch=branch,
            )
            state = "EXPIRED" if len(materialized) == 1 else "UNKNOWN"
        else:
            active = coordination.active_leases(
                observation.state, observation.authority_now
            )
            matching = _matching_leases(
                active,
                lease_id=binding["leaseId"],
                actor=actor,
                branch=branch,
            )
            state = "ACTIVE" if len(matching) == 1 else "UNKNOWN"
    return {
        "handle": copy.deepcopy(handle),
        "actor": actor,
        "locator": copy.deepcopy(locator),
        "branch": branch,
        "observation": observation,
        "latest": copy.deepcopy(latest),
        "binding": copy.deepcopy(binding),
        "state": state,
        "comments": copy.deepcopy(comments),
    }


def observe_write_lifecycle_state(
    *,
    handle: Any,
    branch: str,
    transport: Any | None = None,
) -> dict[str, Any]:
    if transport is None:
        raise AgentOwnershipError("BLOCKED_EXECUTION_SURFACE")
    snapshot = _lifecycle_snapshot(
        handle=handle,
        branch=branch,
        transport=transport,
    )
    return {
        "state": snapshot["state"],
        "branch": snapshot["branch"],
        "authorityHead": snapshot["observation"].head_sha,
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }


def release_ownership(
    *,
    handle: Any,
    branch: str,
    request_id: str,
    submit: bool = False,
    transport: Any | None = None,
) -> dict[str, Any]:
    """Release the current cycle's exact binding without selecting a new cycle."""
    if not isinstance(request_id, str) or not request_id.strip():
        raise AgentOwnershipError("AGENT_OWNERSHIP_REQUEST_ID_INVALID")
    if transport is None:
        raise AgentOwnershipError("BLOCKED_EXECUTION_SURFACE")
    snapshot = _lifecycle_snapshot(
        handle=handle,
        branch=branch,
        transport=transport,
    )
    observed_branch = git_observation.observe_branch(
        snapshot["branch"], transport=transport
    )
    branch_head = observed_branch["branchHead"]
    state = snapshot["state"]
    binding = snapshot["binding"]

    if state == "NONE":
        return _result(
            status="PASS",
            disposition="NO_OWNERSHIP",
            branch=snapshot["branch"],
            authority_head=snapshot["observation"].head_sha,
            branch_head=branch_head,
        )
    if state == "RELEASED":
        return _result(
            status="PASS",
            disposition="RELEASED",
            branch=snapshot["branch"],
            authority_head=snapshot["observation"].head_sha,
            branch_head=branch_head,
            binding=binding,
        )
    if state == "UNKNOWN" or not isinstance(binding, dict):
        return _result(
            status="UNKNOWN",
            disposition="UNKNOWN",
            branch=snapshot["branch"],
            authority_head=snapshot["observation"].head_sha,
            branch_head=branch_head,
            binding=binding,
            blockers=["AGENT_OWNERSHIP_BINDING_AUTHORITY_MISMATCH"],
        )

    request = _outer_request(
        request_id=request_id,
        handle=handle,
        action="release",
        branch=snapshot["branch"],
        authority_head=snapshot["observation"].head_sha,
        branch_head=None,
        binding_hash=binding["bindingHash"],
    )
    comment_id = _find_write_lease_request(snapshot["comments"], request)
    if comment_id is None and submit:
        body = (
            hosted_handle_requests.WRITE_LEASE_MARKER_V02
            + "\n"
            + json.dumps(request, separators=(",", ":"), ensure_ascii=False)
        )
        try:
            comment_id = hosted_issue_bus.post_comment(
                transport,
                repository=hosted_agent_cycle.REPOSITORY,
                issue_number=snapshot["locator"]["issueNumber"],
                body=body,
            )
        except hosted_issue_bus.HostedIssueBusError as exc:
            raise AgentOwnershipError("AGENT_OWNERSHIP_SUBMIT_INVALID") from exc
    return _result(
        status="PENDING",
        disposition="RELEASE_REQUESTED",
        branch=snapshot["branch"],
        authority_head=snapshot["observation"].head_sha,
        branch_head=branch_head,
        request=request,
        binding=binding,
        request_comment_id=comment_id,
    )
