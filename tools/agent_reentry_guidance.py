"""Provider-backed observation adapter for canonical Hosted cycle re-entry.

This module adds no authority. It only materializes the observations required by
``hosted_cycle_reentry.inspect_reentry`` from the canonical Work authority and
transport-only Hosted Agent Cycle bus.
"""
from __future__ import annotations

import copy
import json
from typing import Any

from tools import continuation_remote, hosted_agent_cycle, hosted_cycle_handle, hosted_cycle_reentry
from tools.coordination_remote import ApiError

PER_PAGE = 100


class AgentReentryGuidanceError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}" if detail else code)


def _json(response: Any, operation: str) -> Any:
    try:
        return json.loads(response.body)
    except (AttributeError, json.JSONDecodeError) as exc:
        raise AgentReentryGuidanceError(
            "AGENT_REENTRY_PROVIDER_RESPONSE_INVALID", operation
        ) from exc


def _paged_list(transport: Any, endpoint: str, operation: str) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    page = 1
    separator = "&" if "?" in endpoint else "?"
    while True:
        try:
            response = transport.request(
                "GET", f"{endpoint}{separator}per_page={PER_PAGE}&page={page}"
            )
        except ApiError as exc:
            raise AgentReentryGuidanceError(
                "AGENT_REENTRY_PROVIDER_UNAVAILABLE", operation
            ) from exc
        payload = _json(response, operation)
        if not isinstance(payload, list) or any(not isinstance(item, dict) for item in payload):
            raise AgentReentryGuidanceError(
                "AGENT_REENTRY_PROVIDER_RESPONSE_INVALID", operation
            )
        values.extend(payload)
        if len(payload) < PER_PAGE:
            return values
        page += 1


def _bus_issue_number(transport: Any, repository: str) -> int:
    issues = _paged_list(
        transport,
        f"repos/{repository}/issues?state=open",
        "list hosted-cycle bus issues",
    )
    matches = [
        item
        for item in issues
        if item.get("title") == hosted_agent_cycle.BUS_TITLE
        and item.get("pull_request") is None
        and isinstance(item.get("number"), int)
        and not isinstance(item.get("number"), bool)
        and item["number"] > 0
    ]
    if not matches:
        raise AgentReentryGuidanceError("AGENT_REENTRY_BUS_NOT_FOUND")
    if len(matches) != 1:
        raise AgentReentryGuidanceError("AGENT_REENTRY_BUS_AMBIGUOUS")
    return matches[0]["number"]


def observe_live(
    work_id: str,
    *,
    repository: str = hosted_agent_cycle.REPOSITORY,
    transport: Any | None = None,
) -> dict[str, Any]:
    """Observe canonical Work + complete bus history and derive re-entry.

    Pagination is exhausted before absence or lineage claims are made. Provider
    failure is surfaced as UNKNOWN to the facade; it is never converted to PASS.
    """
    try:
        work_ref = {"workId": work_id}
        from tools import agent_cycle

        agent_cycle.validate_work_ref(work_ref)
    except RuntimeError as exc:
        raise AgentReentryGuidanceError("AGENT_REENTRY_WORK_REF_INVALID") from exc

    if transport is None:
        raise AgentReentryGuidanceError("BLOCKED_EXECUTION_SURFACE")
    try:
        observed = continuation_remote.GitHubContinuationAuthority(
            transport=transport,
            repository=repository,
        ).observe()
    except continuation_remote.ContinuationRemoteError as exc:
        raise AgentReentryGuidanceError(
            "AGENT_REENTRY_WORK_AUTHORITY_UNKNOWN", exc.code
        ) from exc

    work = observed.items.get(work_id)
    if work is None:
        raise AgentReentryGuidanceError("AGENT_REENTRY_WORK_NOT_FOUND", work_id)

    issue_number = _bus_issue_number(transport, repository)
    comments = _paged_list(
        transport,
        f"repos/{repository}/issues/{issue_number}/comments",
        "read hosted-cycle bus comments",
    )
    try:
        return hosted_cycle_reentry.inspect_reentry(
            comments,
            work=work,
            work_authority_head=observed.head_sha,
            issue_number=issue_number,
        )
    except RuntimeError as exc:
        raise AgentReentryGuidanceError(
            "AGENT_REENTRY_INSPECTION_INVALID", str(exc).split(":", 1)[0]
        ) from exc


def _begin_for_work(
    comments: list[dict[str, Any]],
    *,
    work_id: str,
    issue_number: int,
    preferred_comment_id: int | None = None,
) -> dict[str, Any] | None:
    matches: list[tuple[int, dict[str, Any]]] = []
    for comment in comments:
        cid = comment.get("id") if isinstance(comment, dict) else None
        if not isinstance(cid, int) or isinstance(cid, bool) or cid <= 0:
            continue
        if preferred_comment_id is not None and cid != preferred_comment_id:
            continue
        user = comment.get("user")
        association = comment.get("author_association")
        if association is None and isinstance(user, dict) and user.get("login") == "EAKerber":
            association = "OWNER"
        event = {
            "issue": {
                "number": issue_number,
                "title": hosted_agent_cycle.BUS_TITLE,
                "pull_request": None,
            },
            "comment": {
                "id": cid,
                "body": comment.get("body"),
                "author_association": association,
            },
            "repository": {"full_name": hosted_agent_cycle.REPOSITORY},
        }
        try:
            command, _ = hosted_agent_cycle.parse_event(event)
        except RuntimeError:
            continue
        if (
            command.get("action") == "begin"
            and command.get("workRef") == {"workId": work_id}
        ):
            matches.append((cid, command))
    if not matches:
        return None
    matches.sort(key=lambda item: item[0])
    return copy.deepcopy(matches[-1][1])


def observe_turnover_context(
    work_id: str,
    *,
    repository: str = hosted_agent_cycle.REPOSITORY,
    transport: Any | None = None,
) -> dict[str, Any]:
    """Observe the minimum host context needed for stateless intent turnover.

    This is a host adapter, not a new authority. It exposes the canonical
    re-entry projection plus the current/most-recent Work-bound begin intent and
    actor so a caller can recompute readiness without putting semantic state in
    the AgentCycleHandle.
    """
    if transport is None:
        raise AgentReentryGuidanceError("BLOCKED_EXECUTION_SURFACE")
    reentry = observe_live(work_id, repository=repository, transport=transport)
    try:
        observed = continuation_remote.GitHubContinuationAuthority(
            transport=transport,
            repository=repository,
        ).observe()
    except continuation_remote.ContinuationRemoteError as exc:
        raise AgentReentryGuidanceError(
            "AGENT_REENTRY_WORK_AUTHORITY_UNKNOWN", exc.code
        ) from exc
    work = observed.items.get(work_id)
    if not isinstance(work, dict):
        raise AgentReentryGuidanceError("AGENT_REENTRY_WORK_NOT_FOUND", work_id)

    issue_number = _bus_issue_number(transport, repository)
    comments = _paged_list(
        transport,
        f"repos/{repository}/issues/{issue_number}/comments",
        "read hosted-cycle bus comments",
    )
    preferred = None
    target = reentry.get("targetCycle")
    handle = None
    if isinstance(target, dict):
        handle = copy.deepcopy(target.get("handle"))
        if handle is not None:
            try:
                _, locator = hosted_cycle_handle.decode_handle(
                    handle, repository=repository
                )
            except RuntimeError as exc:
                raise AgentReentryGuidanceError(
                    "AGENT_REENTRY_HANDLE_INVALID"
                ) from exc
            preferred = locator["beginCommentId"]

    begin = _begin_for_work(
        comments,
        work_id=work_id,
        issue_number=issue_number,
        preferred_comment_id=preferred,
    )
    if begin is None and preferred is not None:
        raise AgentReentryGuidanceError("AGENT_REENTRY_BEGIN_REQUEST_NOT_FOUND")
    if begin is None:
        begin = _begin_for_work(
            comments,
            work_id=work_id,
            issue_number=issue_number,
        )

    actor = copy.deepcopy(begin.get("actor")) if isinstance(begin, dict) else None
    current_intent = (
        begin.get("declaredIntent") if isinstance(begin, dict) else None
    )
    return {
        "work": copy.deepcopy(work),
        "reentry": copy.deepcopy(reentry),
        "handle": handle,
        "actor": actor,
        "currentIntent": current_intent,
        "busIssueNumber": issue_number,
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
