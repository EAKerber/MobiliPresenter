"""Internal read-only trace gate for Hosted Agent Cycle close.

The Hosted Agent Cycle owns begin/close identity validation.  This helper owns
only carrier observation, exhaustive attribution of supported request/result
pairs, bounded transport stabilization, and evidence discovery.  It has no CLI,
no semantic authority, and never retries an operation or mutation.
"""
from __future__ import annotations

import copy
import json
import os
import time
from pathlib import Path
from typing import Any, Callable

from tools.agent_tools import trace as trace_contract
from tools.agent_tools import trace_collect

TRACE_STABILIZATION_ATTEMPTS = 3
TRACE_STABILIZATION_DELAY_SECONDS = 1.0
TRACE_COMPLETENESS_SCOPE = "same-cycle-attributable-events"
MUTATION_RECEIPT_MISSING = "AGENT_TRACE_MUTATION_RECEIPT_MISSING"
LIFECYCLE_RECEIPT_MISSING = "AGENT_TRACE_LIFECYCLE_RECEIPT_MISSING"


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


def _agent_write_lifecycle_evidence_comment_ids(
    comments: list[dict[str, Any]],
    manifest: dict[str, Any],
    *,
    close_comment_id: int,
) -> list[int]:
    """Discover canonical Coordination receipts emitted by this cycle's lease lifecycle."""

    # Local imports keep the Hosted Agent Cycle import graph acyclic:
    # hosted_agent_cycle -> hosted_agent_cycle_trace -> (this function) -> lifecycle.
    from tools import agent_write_lifecycle as lifecycle
    from tools import remote_canonical_execution

    source = manifest["source"]
    begin = {
        "runId": source["runId"],
        "sourceSha": source["sourceSha"],
        "contextHash": manifest["contextHash"],
    }
    actor = copy.deepcopy(manifest["actor"])
    cycle_id = trace_collect.cycle_instance_id(manifest)
    window = trace_collect._window(comments, source["commentId"], close_comment_id)

    expected: dict[str, dict[str, Any]] = {}
    for comment in window:
        if not trace_collect._result_comment_allowed(comment):
            continue
        payload = trace_collect._json_after_marker(
            comment.get("body"), lifecycle.RESULT_MARKER
        )
        if not isinstance(payload, dict) or payload.get("schemaVersion") != lifecycle.RESULT_SCHEMA:
            continue
        # A different cycle sharing the bus must never contaminate this close.
        if (
            trace_collect._canonical_begin(payload.get("begin")) != begin
            or trace_collect._canonical_actor(payload.get("actor")) != actor
            or payload.get("cycleInstanceId") != cycle_id
        ):
            continue
        try:
            lifecycle.validate_result(payload)
        except RuntimeError as exc:
            raise HostedAgentCycleTraceError("AGENT_TRACE_LIFECYCLE_RESULT_INVALID") from exc

        action = payload["action"]
        binding = payload["binding"]
        if (
            (action == "release" and binding.get("state") != "RELEASED")
            or (action in {"acquire", "renew"} and binding.get("state") != "ACTIVE")
        ):
            raise HostedAgentCycleTraceError("AGENT_TRACE_LIFECYCLE_RESULT_INVALID")

        receipt = payload["remoteReceipt"]
        command = receipt.get("command")
        declared = command.get("declaredIntent") if isinstance(command, dict) else None
        target = command.get("target") if isinstance(command, dict) else None
        if (
            not isinstance(declared, dict)
            or declared.get("intent") != "agent-write-lease-lifecycle"
            or declared.get("cycleInstanceId") != cycle_id
            or declared.get("action") != action
            or command.get("actor") != actor
            or not isinstance(target, dict)
            or target.get("domain") != "coordination"
            or target.get("action") != action
        ):
            raise HostedAgentCycleTraceError("AGENT_TRACE_LIFECYCLE_RECEIPT_INVALID")

        receipt_hash = payload["remoteReceiptHash"]
        if receipt_hash in expected:
            raise HostedAgentCycleTraceError(
                "AGENT_TRACE_LIFECYCLE_RECEIPT_DUPLICATE_EXPECTATION"
            )
        expected[receipt_hash] = receipt

    if not expected:
        return []

    found: dict[str, int] = {}
    for comment in window:
        if not trace_collect._result_comment_allowed(comment):
            continue
        payload = trace_collect._json_after_marker(
            comment.get("body"), trace_collect.REMOTE_RESULT_MARKER
        )
        if not isinstance(payload, dict):
            continue
        receipt_hash = payload.get("receiptHash")
        if receipt_hash not in expected:
            continue
        try:
            remote_canonical_execution.validate_receipt(payload)
        except RuntimeError as exc:
            raise HostedAgentCycleTraceError("AGENT_TRACE_LIFECYCLE_RECEIPT_INVALID") from exc
        if payload != expected[receipt_hash]:
            raise HostedAgentCycleTraceError("AGENT_TRACE_LIFECYCLE_RECEIPT_MISMATCH")
        if receipt_hash in found:
            raise HostedAgentCycleTraceError(
                "AGENT_TRACE_LIFECYCLE_RECEIPT_COMMENT_DUPLICATE"
            )
        comment_id = trace_collect._comment_id(comment)
        if comment_id is None:
            raise HostedAgentCycleTraceError(
                "AGENT_TRACE_LIFECYCLE_RECEIPT_COMMENT_INVALID"
            )
        found[receipt_hash] = comment_id

    if set(found) != set(expected):
        raise HostedAgentCycleTraceError(LIFECYCLE_RECEIPT_MISSING)
    return sorted(found.values())


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
        discovered.update(
            _agent_write_lifecycle_evidence_comment_ids(
                comments,
                manifest,
                close_comment_id=close_comment_id,
            )
        )
    except RuntimeError as exc:
        if isinstance(exc, HostedAgentCycleTraceError):
            raise
        raise HostedAgentCycleTraceError(str(exc).split(":", 1)[0]) from exc
    amended = copy.deepcopy(command)
    amended["evidenceCommentIds"] = sorted(
        set(command["evidenceCommentIds"]) | discovered
    )
    return amended


def _materialize_shadow_resources(
    output_path: str,
    comments: list[dict[str, Any]],
    manifest: dict[str, Any],
    *,
    close_comment_id: int,
    repository: str,
) -> None:
    """Best-effort shadow projection; failure must never change close judgment."""
    from tools import agent_cycle_resource_collect

    path = Path(output_path)
    error_path = path.with_suffix(path.suffix + ".error.json")
    try:
        value = agent_cycle_resource_collect.build_resource_set(
            comments,
            manifest,
            close_comment_id=close_comment_id,
            repository=repository,
        )
        path.write_text(
            json.dumps(value, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        if error_path.exists():
            error_path.unlink()
    except Exception as exc:
        code = str(exc).split(":", 1)[0] or exc.__class__.__name__
        diagnostic = {
            "schemaVersion": "AgentCycleTouchedResourceShadowDiagnostic 0.1",
            "status": "UNKNOWN",
            "error": code,
            "readOnly": True,
            "semanticAuthority": False,
            "authorizesMutation": False,
        }
        error_path.write_text(
            json.dumps(diagnostic, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )


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
    resource_output_path: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Reobserve transport only; never replay or retry the underlying work."""
    del context
    resource_output_path = resource_output_path or os.environ.get("HOSTED_AGENT_RESOURCE_OUTPUT_PATH")
    if not isinstance(attempts, int) or isinstance(attempts, bool) or attempts <= 0:
        raise HostedAgentCycleTraceError("HOSTED_AGENT_TRACE_STABILIZATION_INVALID")
    if not isinstance(delay_seconds, (int, float)) or isinstance(delay_seconds, bool) or delay_seconds < 0:
        raise HostedAgentCycleTraceError("HOSTED_AGENT_TRACE_STABILIZATION_INVALID")
    fetcher = trace_collect.fetch_issue_comments if fetch_comments is None else fetch_comments
    sleeper = time.sleep if sleep is None else sleep
    issue_number = manifest["source"]["issueNumber"]
    last_trace: dict[str, Any] | None = None
    last_observation_error: HostedAgentCycleTraceError | None = None
    retryable_observation_errors = {
        MUTATION_RECEIPT_MISSING,
        LIFECYCLE_RECEIPT_MISSING,
    }
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
                if resource_output_path is not None:
                    _materialize_shadow_resources(
                        resource_output_path,
                        comments,
                        manifest,
                        close_comment_id=meta["commentId"],
                        repository=repository,
                    )
                return amended, value
            except HostedAgentCycleTraceError as exc:
                if exc.code not in retryable_observation_errors:
                    raise
                # A terminal mutation/lifecycle result may be visible before its
                # separately materialized canonical receipt comment. Reobserve
                # the carrier only; never replay work to fill an observation gap.
                last_observation_error = exc
        if observation + 1 < attempts:
            sleeper(float(delay_seconds))
    assert last_trace is not None
    if last_observation_error is not None:
        raise last_observation_error
    raise HostedAgentCycleTraceError("EXECUTION_TRACE_INCOMPLETE")