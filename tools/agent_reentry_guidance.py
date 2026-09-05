"""Provider-backed observation adapter for canonical Hosted cycle re-entry.

This module adds no authority. It only materializes the observations required by
``hosted_cycle_reentry.inspect_reentry`` from the canonical Work authority and
transport-only Hosted Agent Cycle bus.
"""
from __future__ import annotations

import json
from typing import Any

from tools import continuation_remote, hosted_agent_cycle, hosted_cycle_reentry
from tools.coordination_remote import ApiError, GhApiTransport

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

    transport = transport or GhApiTransport()
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
