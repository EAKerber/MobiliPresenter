from __future__ import annotations

import copy
import json
from typing import Any

from tools import (
    agent_write_lifecycle,
    continuation,
    delivery_merge,
    hosted_agent_cycle,
    hosted_cycle_handle,
    hosted_delivery_merge,
)
from tools.canonical import stable_hash
from tools.continuation_remote import ContinuationRemoteError, GitHubContinuationAuthority
from tools.coordination_remote import ApiError

FINALIZATION_SCHEMA = "AgentFinalizationProjection 0.1"
FINALIZATION_ORDER = [
    "COMPLETE_WORK",
    "RELEASE_OWNERSHIP",
    "CLOSE_AGENT_CYCLE",
]


class AgentDeliveryError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}" if detail else code)


def _json_response(response: Any, code: str) -> Any:
    try:
        return json.loads(response.body)
    except (AttributeError, json.JSONDecodeError) as exc:
        raise AgentDeliveryError(code) from exc


def _request(transport: Any, method: str, endpoint: str, *, payload=None) -> Any:
    try:
        return _json_response(
            transport.request(method, endpoint, payload=payload),
            "AGENT_DELIVERY_PROVIDER_RESPONSE_INVALID",
        )
    except ApiError as exc:
        raise AgentDeliveryError("AGENT_DELIVERY_PROVIDER_UNAVAILABLE", exc.detail) from exc


def _decode_handle(handle: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        return hosted_cycle_handle.decode_handle(
            handle, repository=hosted_agent_cycle.REPOSITORY
        )
    except RuntimeError as exc:
        raise AgentDeliveryError("AGENT_DELIVERY_HANDLE_INVALID") from exc


def _observe_work(work_id: str, transport: Any) -> tuple[str, dict[str, Any]]:
    try:
        observed = GitHubContinuationAuthority(
            transport=transport,
            repository=hosted_agent_cycle.REPOSITORY,
        ).observe()
    except (RuntimeError, ContinuationRemoteError) as exc:
        raise AgentDeliveryError("AGENT_DELIVERY_WORK_OBSERVATION_UNAVAILABLE") from exc
    work = observed.items.get(work_id)
    if work is None:
        raise AgentDeliveryError("AGENT_DELIVERY_WORK_MISSING")
    try:
        continuation.require_current(work, work_id)
    except RuntimeError as exc:
        raise AgentDeliveryError("AGENT_DELIVERY_WORK_INVALID") from exc
    if work["status"] not in delivery_merge.ACTIVE_WORK_STATUSES:
        raise AgentDeliveryError("AGENT_DELIVERY_WORK_NOT_ACTIVE")
    if not isinstance(work.get("branch"), str) or not work["branch"]:
        raise AgentDeliveryError("AGENT_DELIVERY_WORK_BRANCH_MISSING")
    if type(work.get("prNumber")) is not int or work["prNumber"] <= 0:
        raise AgentDeliveryError("AGENT_DELIVERY_WORK_PR_MISSING")
    return observed.head_sha, copy.deepcopy(work)


def _observe_pr(pr_number: int, transport: Any) -> dict[str, Any]:
    raw = _request(
        transport,
        "GET",
        f"repos/{hosted_agent_cycle.REPOSITORY}/pulls/{pr_number}",
    )
    if not isinstance(raw, dict):
        raise AgentDeliveryError("AGENT_DELIVERY_PR_OBSERVATION_INVALID")
    head = raw.get("head") if isinstance(raw.get("head"), dict) else {}
    base = raw.get("base") if isinstance(raw.get("base"), dict) else {}
    head_repo = head.get("repo") if isinstance(head.get("repo"), dict) else {}
    value = {
        "number": raw.get("number"),
        "state": raw.get("state"),
        "draft": raw.get("draft"),
        "merged": raw.get("merged"),
        "headSha": head.get("sha"),
        "headRef": head.get("ref"),
        "headRepository": head_repo.get("full_name"),
        "baseRef": base.get("ref"),
    }
    if (
        value["number"] != pr_number
        or value["state"] != "open"
        or value["draft"] is not False
        or value["merged"] is not False
        or value["headRepository"] != hosted_agent_cycle.REPOSITORY
        or not isinstance(value["headSha"], str)
        or not isinstance(value["headRef"], str)
        or not isinstance(value["baseRef"], str)
    ):
        raise AgentDeliveryError("AGENT_DELIVERY_PR_NOT_OPEN_READY")
    return value


def _observe_main(transport: Any) -> str:
    raw = _request(
        transport,
        "GET",
        f"repos/{hosted_agent_cycle.REPOSITORY}/git/ref/heads/{delivery_merge.CONTROL_BRANCH}",
    )
    value = (raw.get("object") or {}).get("sha") if isinstance(raw, dict) else None
    if not isinstance(value, str) or len(value) != 40:
        raise AgentDeliveryError("AGENT_DELIVERY_MAIN_OBSERVATION_INVALID")
    return value


def build_delivery_request(
    *,
    handle: Any,
    work_id: str,
    request_id: str,
    transport: Any | None = None,
) -> dict[str, Any]:
    """Compose the existing HostedDeliveryMergeRequest 0.1 from live observations."""

    handle_value, _ = _decode_handle(handle)
    if transport is None:
        raise AgentDeliveryError("BLOCKED_EXECUTION_SURFACE")
    carrier = transport
    authority_head, work = _observe_work(work_id, carrier)
    pr = _observe_pr(work["prNumber"], carrier)
    if pr["headRef"] != work["branch"]:
        raise AgentDeliveryError("AGENT_DELIVERY_WORK_BRANCH_MISMATCH")
    if pr["baseRef"] != delivery_merge.CONTROL_BRANCH:
        raise AgentDeliveryError("AGENT_DELIVERY_PR_BASE_FORBIDDEN")
    target_sha = _observe_main(carrier)
    request = {
        "schemaVersion": delivery_merge.REQUEST_SCHEMA,
        "requestId": request_id,
        "actor": copy.deepcopy(handle_value["actor"]),
        "workId": work_id,
        "prNumber": work["prNumber"],
        "expectedWorkAuthorityHead": authority_head,
        "expectedHeadSha": pr["headSha"],
        "expectedBase": pr["baseRef"],
        "expectedTargetSha": target_sha,
        "mergeMethod": "squash",
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    try:
        return delivery_merge.validate_request(request)
    except RuntimeError as exc:
        raise AgentDeliveryError("AGENT_DELIVERY_REQUEST_INVALID", str(exc)) from exc


def submit_delivery_request(
    request: dict[str, Any],
    *,
    handle: Any,
    transport: Any | None = None,
) -> int:
    try:
        delivery_merge.validate_request(request)
    except RuntimeError as exc:
        raise AgentDeliveryError("AGENT_DELIVERY_REQUEST_INVALID", str(exc)) from exc
    _, locator = _decode_handle(handle)
    if transport is None:
        raise AgentDeliveryError("BLOCKED_EXECUTION_SURFACE")
    body = (
        hosted_delivery_merge.REQUEST_MARKER
        + "\n"
        + json.dumps(request, separators=(",", ":"), ensure_ascii=False)
    )
    payload = _request(
        transport,
        "POST",
        f"repos/{hosted_agent_cycle.REPOSITORY}/issues/{locator['issueNumber']}/comments",
        payload={"body": body},
    )
    comment_id = payload.get("id") if isinstance(payload, dict) else None
    if type(comment_id) is not int or comment_id <= 0:
        raise AgentDeliveryError("AGENT_DELIVERY_SUBMIT_INVALID")
    return comment_id


def compose_delivery(
    *,
    handle: Any,
    work_id: str,
    request_id: str,
    submit: bool = False,
    transport: Any | None = None,
) -> dict[str, Any]:
    request = build_delivery_request(
        handle=handle,
        work_id=work_id,
        request_id=request_id,
        transport=transport,
    )
    comment_id = (
        submit_delivery_request(request, handle=handle, transport=transport)
        if submit
        else None
    )
    return {"request": request, "requestCommentId": comment_id}


def _require_delivery_pass(value: Any) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or value.get("schemaVersion") != delivery_merge.RESULT_SCHEMA
        or value.get("repository") != delivery_merge.REPOSITORY
        or value.get("status") != "PASS"
        or value.get("targetContainsMergedSha") is not True
        or value.get("semanticAuthority") is not False
        or value.get("authorizesMutation") is not False
    ):
        raise AgentDeliveryError("AGENT_FINALIZATION_DELIVERY_PASS_REQUIRED")
    result_hash = value.get("resultHash")
    body = {key: copy.deepcopy(item) for key, item in value.items() if key != "resultHash"}
    if not isinstance(result_hash, str) or result_hash != stable_hash(body):
        raise AgentDeliveryError("AGENT_FINALIZATION_DELIVERY_RESULT_INVALID")
    return value


def _released_ownership(value: Any, *, handle: Any, branch: str) -> bool:
    if value is None:
        return False
    try:
        result = agent_write_lifecycle.validate_result(value)
    except RuntimeError as exc:
        raise AgentDeliveryError("AGENT_FINALIZATION_OWNERSHIP_RESULT_INVALID") from exc
    handle_value, _ = _decode_handle(handle)
    binding = result["binding"]
    if (
        result["action"] != "release"
        or binding["state"] != "RELEASED"
        or result["branch"] != branch
        or result["cycleInstanceId"] != handle_value["cycleInstanceId"]
        or result["actor"] != handle_value["actor"]
    ):
        raise AgentDeliveryError("AGENT_FINALIZATION_OWNERSHIP_RELEASE_MISMATCH")
    return True


def project_finalization(
    *,
    handle: Any,
    delivery_result: dict[str, Any],
    work: dict[str, Any],
    ownership_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Project, but never execute, the explicit post-delivery finalization order."""

    delivery = _require_delivery_pass(delivery_result)
    work_id = (delivery.get("work") or {}).get("id")
    try:
        continuation.require_current(work, work_id)
    except RuntimeError as exc:
        raise AgentDeliveryError("AGENT_FINALIZATION_WORK_INVALID") from exc
    if work.get("prNumber") != delivery.get("prNumber"):
        raise AgentDeliveryError("AGENT_FINALIZATION_WORK_DELIVERY_MISMATCH")
    branch = (delivery.get("work") or {}).get("branch")
    if not isinstance(branch, str) or work.get("branch") != branch:
        raise AgentDeliveryError("AGENT_FINALIZATION_WORK_DELIVERY_MISMATCH")

    work_done = work["status"] == "DONE"
    ownership_released = _released_ownership(
        ownership_result, handle=handle, branch=branch
    )
    if ownership_released and not work_done:
        raise AgentDeliveryError("AGENT_FINALIZATION_ORDER_VIOLATION")

    completed = ["DELIVERY_PASS"]
    if work_done:
        completed.append("COMPLETE_WORK")
    if ownership_released:
        completed.append("RELEASE_OWNERSHIP")

    if not work_done:
        next_action = "COMPLETE_WORK"
    elif not ownership_released:
        next_action = "RELEASE_OWNERSHIP"
    else:
        next_action = "CLOSE_AGENT_CYCLE"

    steps = [
        {
            "action": "COMPLETE_WORK",
            "disposition": "DONE" if work_done else "REQUIRED",
            "authority": "coordination/continuations",
        },
        {
            "action": "RELEASE_OWNERSHIP",
            "disposition": (
                "DONE"
                if ownership_released
                else "REQUIRED"
                if work_done
                else "BLOCKED_BY_PREVIOUS"
            ),
            "authority": "coordination/leases",
        },
        {
            "action": "CLOSE_AGENT_CYCLE",
            "disposition": "REQUIRED" if ownership_released else "BLOCKED_BY_PREVIOUS",
            "authority": "agent-cycle",
        },
    ]
    core = {
        "schemaVersion": FINALIZATION_SCHEMA,
        "deliveryDisposition": "PASS",
        "workId": work["id"],
        "branch": branch,
        "finalizationOrder": copy.deepcopy(FINALIZATION_ORDER),
        "steps": steps,
        "completedResponsibilities": completed,
        "nextSafeAction": next_action,
        "automaticTransitions": [],
        "executesActions": False,
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    return {**core, "projectionHash": stable_hash(core)}
