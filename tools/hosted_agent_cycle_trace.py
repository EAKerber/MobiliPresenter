"""Internal read-only trace gate for Hosted Agent Cycle close.

The Hosted Agent Cycle owns begin/close identity validation.  This helper owns
only carrier observation, exhaustive attribution of supported request/result
pairs, bounded transport stabilization, and evidence discovery.  It has no CLI,
no semantic authority, and never retries an operation or mutation.
"""
from __future__ import annotations

import copy
import time
from typing import Any, Callable

from tools.agent_tools import trace as trace_contract
from tools.agent_tools import trace_collect

TRACE_STABILIZATION_ATTEMPTS = 3
TRACE_STABILIZATION_DELAY_SECONDS = 1.0
TRACE_COMPLETENESS_SCOPE = "same-cycle-attributable-events"
MUTATION_RECEIPT_MISSING = "AGENT_TRACE_MUTATION_RECEIPT_MISSING"


class HostedAgentCycleTraceError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _bound_trace(
    command: dict[str, Any],
    meta: dict[str, Any],
    manifest: dict[str, Any],
    comments: list[dict[str, Any]],
) -> dict[str, Any]:
    if meta.get("issueNumber") != manifest["source"]["issueNumber"]:
        raise HostedAgentCycleTraceError("HOSTED_AGENT_TRACE_ISSUE_MISMATCH")
    close_comment_id = meta.get("commentId")
    if not isinstance(close_comment_id, int) or isinstance(close_comment_id, bool) or close_comment_id <= 0:
        raise HostedAgentCycleTraceError("HOSTED_AGENT_TRACE_CLOSE_COMMENT_INVALID")
    try:
        value = trace_collect.build_trace(
            comments,
            manifest,
            close_comment_id=close_comment_id,
        )
    except RuntimeError as exc:
        raise HostedAgentCycleTraceError(str(exc).split(":", 1)[0]) from exc
    trace_contract.validate_trace(value)
    return value


def _amend_command(
    command: dict[str, Any],
    trace_value: dict[str, Any],
    comments: list[dict[str, Any]],
    manifest: dict[str, Any],
    *,
    close_comment_id: int,
) -> dict[str, Any]:
    discovered = set(trace_collect.remote_evidence_comment_ids(trace_value))
    try:
        discovered.update(
            trace_collect.agent_tool_mutation_evidence_comment_ids(
                comments,
                manifest,
                close_comment_id=close_comment_id,
            )
        )
    except RuntimeError as exc:
        raise HostedAgentCycleTraceError(str(exc).split(":", 1)[0]) from exc
    amended = copy.deepcopy(command)
    amended["evidenceCommentIds"] = sorted(
        set(command["evidenceCommentIds"]) | discovered
    )
    return amended


def prepare_close(
    command: dict[str, Any],
    meta: dict[str, Any],
    manifest: dict[str, Any],
    context: dict[str, Any],
    comments: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Prepare one observation. Identity/begin binding is validated by caller."""
    del context
    value = _bound_trace(command, meta, manifest, comments)
    if value["traceStatus"] != "PASS":
        raise HostedAgentCycleTraceError("EXECUTION_TRACE_INCOMPLETE")
    return (
        _amend_command(
            command,
            value,
            comments,
            manifest,
            close_comment_id=meta["commentId"],
        ),
        value,
    )


def prepare_close_stabilized(
    command: dict[str, Any],
    meta: dict[str, Any],
    manifest: dict[str, Any],
    context: dict[str, Any],
    *,
    repository: str,
    fetch_comments: Callable[[str, int], list[dict[str, Any]]] | None = None,
    sleep: Callable[[float], None] | None = None,
    attempts: int = TRACE_STABILIZATION_ATTEMPTS,
    delay_seconds: float = TRACE_STABILIZATION_DELAY_SECONDS,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Reobserve transport only; never replay or retry the underlying work."""
    del context
    if not isinstance(attempts, int) or isinstance(attempts, bool) or attempts <= 0:
        raise HostedAgentCycleTraceError("HOSTED_AGENT_TRACE_STABILIZATION_INVALID")
    if not isinstance(delay_seconds, (int, float)) or isinstance(delay_seconds, bool) or delay_seconds < 0:
        raise HostedAgentCycleTraceError("HOSTED_AGENT_TRACE_STABILIZATION_INVALID")
    fetcher = trace_collect.fetch_issue_comments if fetch_comments is None else fetch_comments
    sleeper = time.sleep if sleep is None else sleep
    issue_number = manifest["source"]["issueNumber"]
    last_trace: dict[str, Any] | None = None
    last_observation_error: HostedAgentCycleTraceError | None = None
    for observation in range(attempts):
        comments = fetcher(repository, issue_number)
        value = _bound_trace(command, meta, manifest, comments)
        last_trace = value
        last_observation_error = None
        if value["traceStatus"] == "PASS":
            try:
                amended = _amend_command(
                    command,
                    value,
                    comments,
                    manifest,
                    close_comment_id=meta["commentId"],
                )
                return amended, value
            except HostedAgentCycleTraceError as exc:
                if exc.code != MUTATION_RECEIPT_MISSING:
                    raise
                # A terminal mutation result may be visible before the separately
                # materialized canonical receipt comment. Reobserve the carrier;
                # never replay the mutation to fill an observation gap.
                last_observation_error = exc
        if observation + 1 < attempts:
            sleeper(float(delay_seconds))
    assert last_trace is not None
    if last_observation_error is not None:
        raise last_observation_error
    raise HostedAgentCycleTraceError("EXECUTION_TRACE_INCOMPLETE")
