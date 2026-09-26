"""Fail-closed reconciliation for a Hosted close blocked by external durable deltas.

This module creates no authority and never rewrites the historical close. It
reconstructs the exact raw close evidence, adds an explicit non-interference
readback, and asks the canonical Agent Cycle close policy to re-evaluate the
historical before/after contexts. Recovery is admissible only when that
re-evaluation is PASS.
"""
from __future__ import annotations

import copy
from typing import Any

from tools import agent_cycle_close, hosted_agent_cycle, hosted_cycle_records
from tools.agent_tools import trace_collect
from tools.canonical import stable_hash

BLOCKER = "UNATTRIBUTED_DURABLE_DELTA"


class HostedCycleExternalDeltaRecoveryError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _work_item(context: Any, work_id: str) -> dict[str, Any]:
    if not isinstance(context, dict):
        raise HostedCycleExternalDeltaRecoveryError(
            "HOSTED_CYCLE_EXTERNAL_DELTA_CONTEXT_INVALID"
        )
    machine = context.get("projectMachine")
    sensors = machine.get("sensors") if isinstance(machine, dict) else None
    continuation = sensors.get("continuations") if isinstance(sensors, dict) else None
    data = continuation.get("data") if isinstance(continuation, dict) else None
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise HostedCycleExternalDeltaRecoveryError(
            "HOSTED_CYCLE_EXTERNAL_DELTA_WORK_UNAVAILABLE"
        )
    matches = [
        item
        for item in items
        if isinstance(item, dict) and item.get("id") == work_id
    ]
    if len(matches) != 1:
        raise HostedCycleExternalDeltaRecoveryError(
            "HOSTED_CYCLE_EXTERNAL_DELTA_WORK_UNAVAILABLE"
        )
    return copy.deepcopy(matches[0])


def _control_change(closure: dict[str, Any]) -> dict[str, Any]:
    try:
        receipt = closure["receipt"]
        blockers = receipt["blockers"]
        delta = receipt["delta"]["durableChanges"]
        uncovered = receipt["aggregateReadback"]["uncoveredDurableChanges"]
    except (KeyError, TypeError) as exc:
        raise HostedCycleExternalDeltaRecoveryError(
            "HOSTED_CYCLE_EXTERNAL_DELTA_CLOSURE_INVALID"
        ) from exc
    if blockers != [BLOCKER] or len(uncovered) != 1:
        raise HostedCycleExternalDeltaRecoveryError(
            "HOSTED_CYCLE_EXTERNAL_DELTA_FAILURE_NOT_NARROW"
        )
    target = uncovered[0]
    matches: list[dict[str, Any]] = []
    for index, change in enumerate(delta):
        if not isinstance(change, dict):
            continue
        change_id = f"{change.get('kind')}:{change.get('name') or 'project-state'}:{index}"
        if change_id == target:
            matches.append(change)
    if len(matches) != 1:
        raise HostedCycleExternalDeltaRecoveryError(
            "HOSTED_CYCLE_EXTERNAL_DELTA_CHANGE_UNAVAILABLE"
        )
    change = matches[0]
    if (
        change.get("kind") != "source-head"
        or change.get("name") != "control"
        or change.get("branch") != "main"
        or not isinstance(change.get("before"), str)
        or not isinstance(change.get("after"), str)
        or change["before"] == change["after"]
    ):
        raise HostedCycleExternalDeltaRecoveryError(
            "HOSTED_CYCLE_EXTERNAL_DELTA_CHANGE_UNSUPPORTED"
        )
    return copy.deepcopy(change)


def _validate_control_chain(
    pulls: list[dict[str, Any]],
    *,
    before: str,
    after: str,
    work_branch: str,
    work_pr_number: int | None,
) -> list[dict[str, Any]]:
    if not isinstance(pulls, list) or not pulls:
        raise HostedCycleExternalDeltaRecoveryError(
            "HOSTED_CYCLE_EXTERNAL_DELTA_CONTROL_READBACK_INVALID"
        )
    normalized: list[dict[str, Any]] = []
    expected_base = before
    seen_prs: set[int] = set()
    seen_commits: set[str] = set()
    for pull in pulls:
        if not isinstance(pull, dict) or set(pull) != {
            "commitSha", "prNumber", "headBranch", "baseSha"
        }:
            raise HostedCycleExternalDeltaRecoveryError(
                "HOSTED_CYCLE_EXTERNAL_DELTA_CONTROL_READBACK_INVALID"
            )
        commit = pull.get("commitSha")
        base = pull.get("baseSha")
        head = pull.get("headBranch")
        number = pull.get("prNumber")
        if (
            not isinstance(commit, str)
            or len(commit) != 40
            or not isinstance(base, str)
            or len(base) != 40
            or not isinstance(head, str)
            or not head
            or head == work_branch
            or not isinstance(number, int)
            or isinstance(number, bool)
            or number <= 0
            or number in seen_prs
            or commit in seen_commits
            or (work_pr_number is not None and number == work_pr_number)
            or base != expected_base
        ):
            raise HostedCycleExternalDeltaRecoveryError(
                "HOSTED_CYCLE_EXTERNAL_DELTA_CONTROL_READBACK_INVALID"
            )
        normalized.append(copy.deepcopy(pull))
        seen_prs.add(number)
        seen_commits.add(commit)
        expected_base = commit
    if expected_base != after:
        raise HostedCycleExternalDeltaRecoveryError(
            "HOSTED_CYCLE_EXTERNAL_DELTA_CONTROL_CHAIN_INCOMPLETE"
        )
    return normalized


def build_noninterference_evidence(
    *,
    before_context: dict[str, Any],
    failed_closure: dict[str, Any],
    continuation_after_sha: str,
    continuation_changed_paths: list[str],
    merged_pull_requests: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build one canonical AgentCycleNonInterferenceReadback 0.2.

    The control interval is the historical failed-close interval. The
    continuation interval may extend to a later readback; excluding the exact
    Work path across that wider interval proves the Work remained unchanged.
    """
    work_ref = before_context.get("workRef")
    if not isinstance(work_ref, dict) or not isinstance(work_ref.get("workId"), str):
        raise HostedCycleExternalDeltaRecoveryError(
            "HOSTED_CYCLE_EXTERNAL_DELTA_WORK_UNAVAILABLE"
        )
    work_id = work_ref["workId"]
    after_context = failed_closure.get("afterContext")
    before_work = _work_item(before_context, work_id)
    after_work = _work_item(after_context, work_id)
    if before_work != after_work:
        raise HostedCycleExternalDeltaRecoveryError(
            "HOSTED_CYCLE_EXTERNAL_DELTA_WORK_CHANGED"
        )
    work_branch = before_work.get("branch")
    work_pr = before_work.get("prNumber")
    if not isinstance(work_branch, str) or not work_branch or work_branch == "main":
        raise HostedCycleExternalDeltaRecoveryError(
            "HOSTED_CYCLE_EXTERNAL_DELTA_WORK_UNAVAILABLE"
        )
    if work_pr is not None and (
        not isinstance(work_pr, int) or isinstance(work_pr, bool) or work_pr <= 0
    ):
        raise HostedCycleExternalDeltaRecoveryError(
            "HOSTED_CYCLE_EXTERNAL_DELTA_WORK_UNAVAILABLE"
        )

    change = _control_change(failed_closure)
    source_heads = before_context.get("baseline", {}).get("sourceHeads")
    continuation = source_heads.get("continuation") if isinstance(source_heads, dict) else None
    continuation_before = continuation.get("sha") if isinstance(continuation, dict) else None
    if (
        not isinstance(continuation_before, str)
        or len(continuation_before) != 40
        or not isinstance(continuation_after_sha, str)
        or len(continuation_after_sha) != 40
        or continuation_after_sha == continuation_before
    ):
        raise HostedCycleExternalDeltaRecoveryError(
            "HOSTED_CYCLE_EXTERNAL_DELTA_CONTINUATION_READBACK_INVALID"
        )
    paths = continuation_changed_paths
    work_path = f"ops/continuations/{work_id}.json"
    if (
        not isinstance(paths, list)
        or any(not isinstance(path, str) or not path for path in paths)
        or paths != sorted(set(paths))
        or work_path in paths
    ):
        raise HostedCycleExternalDeltaRecoveryError(
            "HOSTED_CYCLE_EXTERNAL_DELTA_WORK_CHANGED"
        )

    pulls = _validate_control_chain(
        merged_pull_requests,
        before=change["before"],
        after=change["after"],
        work_branch=work_branch,
        work_pr_number=work_pr,
    )
    continuation_change = {
        "kind": "source-head",
        "name": "continuation",
        "branch": "coordination/continuations",
        "before": continuation_before,
        "after": continuation_after_sha,
    }
    control_change = copy.deepcopy(change)
    inspection_change = {
        "kind": "source-head",
        "name": "inspection",
        "branch": "main",
        "before": change["before"],
        "after": change["after"],
    }
    body = {
        "kind": "agent-cycle-noninterference-readback",
        "schemaVersion": agent_cycle_close.NONINTERFERENCE_SCHEMA,
        "cycleId": before_context.get("cycleId"),
        "workId": work_id,
        "workBranch": work_branch,
        "workPrNumber": work_pr,
        "workStateHash": stable_hash(before_work),
        "coveredChanges": [continuation_change, control_change, inspection_change],
        "continuationReadback": {
            "branch": "coordination/continuations",
            "before": continuation_before,
            "after": continuation_after_sha,
            "workPath": work_path,
            "changedPaths": copy.deepcopy(paths),
        },
        "controlReadback": {
            "branch": "main",
            "before": change["before"],
            "after": change["after"],
            "mergedPullRequests": pulls,
        },
        "coordinationReadback": None,
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    evidence = {**body, "evidenceHash": stable_hash(body)}
    try:
        agent_cycle_close.verify_evidence(evidence)
    except RuntimeError as exc:
        raise HostedCycleExternalDeltaRecoveryError(
            "HOSTED_CYCLE_EXTERNAL_DELTA_EVIDENCE_INVALID"
        ) from exc
    return evidence


def reconstruct_original_evidence(
    comments: list[dict[str, Any]],
    *,
    failed_closure: dict[str, Any],
    close_comment_id: int,
) -> list[dict[str, Any]]:
    """Recover the exact raw inputs whose normalized hashes are in the receipt."""
    try:
        expected = {
            item["evidenceHash"]
            for item in failed_closure["receipt"]["evidence"]
        }
    except (KeyError, TypeError) as exc:
        raise HostedCycleExternalDeltaRecoveryError(
            "HOSTED_CYCLE_EXTERNAL_DELTA_CLOSURE_INVALID"
        ) from exc
    if len(expected) != len(failed_closure["receipt"]["evidence"]):
        raise HostedCycleExternalDeltaRecoveryError(
            "HOSTED_CYCLE_EXTERNAL_DELTA_EVIDENCE_AMBIGUOUS"
        )
    found: dict[str, dict[str, Any]] = {}
    for comment in comments:
        cid = hosted_cycle_records.comment_id(comment)
        if cid is None or cid >= close_comment_id:
            continue
        user = comment.get("user") if isinstance(comment, dict) else None
        if not isinstance(user, dict) or user.get("login") != "github-actions[bot]":
            continue
        payload = trace_collect._json_after_marker(
            comment.get("body"), trace_collect.REMOTE_RESULT_MARKER
        )
        if not isinstance(payload, dict) or payload.get("status") != "PASS":
            continue
        try:
            raw = hosted_agent_cycle.normalize_remote_evidence(payload)
            verified = agent_cycle_close.verify_evidence(raw)
        except RuntimeError:
            continue
        digest = verified["evidenceHash"]
        if digest not in expected:
            continue
        previous = found.get(digest)
        if previous is not None and previous != raw:
            raise HostedCycleExternalDeltaRecoveryError(
                "HOSTED_CYCLE_EXTERNAL_DELTA_EVIDENCE_AMBIGUOUS"
            )
        found[digest] = raw
    if set(found) != expected:
        raise HostedCycleExternalDeltaRecoveryError(
            "HOSTED_CYCLE_EXTERNAL_DELTA_EVIDENCE_INCOMPLETE"
        )
    return [found[digest] for digest in sorted(found)]


def reconcile_failed_closure(
    *,
    before_context: dict[str, Any],
    failed_closure: dict[str, Any],
    comments: list[dict[str, Any]],
    close_comment_id: int,
    continuation_after_sha: str,
    continuation_changed_paths: list[str],
    merged_pull_requests: list[dict[str, Any]],
) -> dict[str, Any]:
    """Re-evaluate one exact historical close with explicit external proof."""
    original = reconstruct_original_evidence(
        comments,
        failed_closure=failed_closure,
        close_comment_id=close_comment_id,
    )
    try:
        agent_cycle_close.validate_closure(
            failed_closure, before_context, evidence=original
        )
    except RuntimeError as exc:
        raise HostedCycleExternalDeltaRecoveryError(
            "HOSTED_CYCLE_EXTERNAL_DELTA_CLOSURE_MISMATCH"
        ) from exc
    if failed_closure.get("status") != "UNKNOWN":
        raise HostedCycleExternalDeltaRecoveryError(
            "HOSTED_CYCLE_EXTERNAL_DELTA_FAILURE_NOT_NARROW"
        )
    proof = build_noninterference_evidence(
        before_context=before_context,
        failed_closure=failed_closure,
        continuation_after_sha=continuation_after_sha,
        continuation_changed_paths=continuation_changed_paths,
        merged_pull_requests=merged_pull_requests,
    )
    evidence = [*original, proof]
    after = failed_closure["afterContext"]
    receipt = agent_cycle_close.build_receipt(
        before_context, after, evidence=evidence
    )
    body = {
        "schemaVersion": agent_cycle_close.CLOSURE_SCHEMA,
        "cycleId": before_context["cycleId"],
        "beforeContextHash": before_context["contextHash"],
        "afterContext": copy.deepcopy(after),
        "receipt": receipt,
        "status": receipt["status"],
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    reconciled = {**body, "closureHash": stable_hash(body)}
    try:
        agent_cycle_close.validate_closure(
            reconciled, before_context, evidence=evidence
        )
    except RuntimeError as exc:
        raise HostedCycleExternalDeltaRecoveryError(
            "HOSTED_CYCLE_EXTERNAL_DELTA_RECONCILIATION_INVALID"
        ) from exc
    if (
        reconciled["status"] != "PASS"
        or reconciled["receipt"]["aggregateReadback"]["uncoveredDurableChanges"]
    ):
        raise HostedCycleExternalDeltaRecoveryError(
            "HOSTED_CYCLE_EXTERNAL_DELTA_NOT_RECONCILED"
        )
    return {
        "nonInterferenceEvidence": proof,
        "reconciledClosure": reconciled,
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
