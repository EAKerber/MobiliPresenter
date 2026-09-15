from __future__ import annotations

import copy
import json
from typing import Any

from tools import hosted_agent_cycle, hosted_cycle_handle, hosted_handle_requests
from tools.coordination_remote import GhApiTransport

TOOL_ID = "git.files.mutate"


class AgentAuthoringError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}" if detail else code)


def build_authoring_request(
    *,
    handle: Any,
    branch: str,
    changes: list[dict[str, Any]],
    message: str,
    request_id: str,
) -> dict[str, Any]:
    """Compose the existing Hosted Agent Tool V0.2 authoring request.

    Git observation, CAS, ownership proofing, dispatch, mutation and readback remain
    responsibilities of the existing Agent Tool host.  This helper deliberately
    does not introduce a parallel authoring state or mutation contract.
    """

    value = {
        "schemaVersion": hosted_handle_requests.TOOL_SCHEMA,
        "requestId": request_id,
        "handle": copy.deepcopy(handle),
        "toolId": TOOL_ID,
        "target": {"branch": branch},
        "input": {
            "changes": copy.deepcopy(changes),
            "message": message,
        },
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    try:
        return hosted_handle_requests.validate_tool(
            value, repository=hosted_agent_cycle.REPOSITORY
        )
    except RuntimeError as exc:
        raise AgentAuthoringError("AGENT_AUTHORING_REQUEST_INVALID", str(exc)) from exc


def submit_authoring_request(
    request: dict[str, Any],
    *,
    transport: Any | None = None,
) -> int:
    """Submit one existing Hosted Agent Tool V0.2 request to the canonical bus."""

    try:
        hosted_handle_requests.validate_tool(
            request, repository=hosted_agent_cycle.REPOSITORY
        )
        _, locator = hosted_cycle_handle.decode_handle(
            request["handle"], repository=hosted_agent_cycle.REPOSITORY
        )
    except RuntimeError as exc:
        raise AgentAuthoringError("AGENT_AUTHORING_REQUEST_INVALID", str(exc)) from exc

    carrier = transport or GhApiTransport()
    body = (
        hosted_handle_requests.TOOL_MARKER_V02
        + "\n"
        + json.dumps(request, separators=(",", ":"), ensure_ascii=False)
    )
    response = carrier.request(
        "POST",
        f"repos/{hosted_agent_cycle.REPOSITORY}/issues/{locator['issueNumber']}/comments",
        payload={"body": body},
    )
    try:
        payload = json.loads(response.body)
    except (AttributeError, json.JSONDecodeError) as exc:
        raise AgentAuthoringError("AGENT_AUTHORING_SUBMIT_INVALID") from exc
    comment_id = payload.get("id") if isinstance(payload, dict) else None
    if not isinstance(comment_id, int) or isinstance(comment_id, bool) or comment_id <= 0:
        raise AgentAuthoringError("AGENT_AUTHORING_SUBMIT_INVALID")
    return comment_id


def author_changes(
    *,
    handle: Any,
    branch: str,
    changes: list[dict[str, Any]],
    message: str,
    request_id: str,
    submit: bool = False,
    transport: Any | None = None,
) -> dict[str, Any]:
    """Build, and optionally submit, the existing authoring request."""

    request = build_authoring_request(
        handle=handle,
        branch=branch,
        changes=changes,
        message=message,
        request_id=request_id,
    )
    comment_id = (
        submit_authoring_request(request, transport=transport) if submit else None
    )
    return {"request": request, "requestCommentId": comment_id}
