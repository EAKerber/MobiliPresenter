"""Read-only proof for own-Work durable deltas integrated under valid authority.

This module grants no authority and rewrites no historical close.  It supports
only the narrow case where the sole uncovered durable change is ``main``, every
first-parent merge in that interval belongs to the exact Work branch/PR, and all
those merges occurred while the exact hosted cycle held continuous write
authority.  The historical close is then rebuilt through the existing canonical
close verifier.
"""
from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from typing import Any

from tools import (
    agent_cycle_close,
    agent_write_lifecycle,
    git_mutation_plan,
    hosted_agent_cycle,
    hosted_cycle_external_delta_recovery,
    hosted_cycle_records,
)
from tools.canonical import stable_hash

PROOF_SCHEMA = "HostedCycleOwnWorkIntegrationProof 0.1"
BLOCKER = "UNATTRIBUTED_DURABLE_DELTA"


class HostedCycleOwnWorkDeltaRecoveryError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _parse_time(value: Any, code: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise HostedCycleOwnWorkDeltaRecoveryError(code)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HostedCycleOwnWorkDeltaRecoveryError(code) from exc
    if parsed.tzinfo is None:
        raise HostedCycleOwnWorkDeltaRecoveryError(code)
    return parsed.astimezone(timezone.utc)


def _get(transport: Any, endpoint: str, code: str) -> Any:
    try:
        response = transport.request("GET", endpoint)
        return json.loads(response.body)
    except Exception as exc:
        raise HostedCycleOwnWorkDeltaRecoveryError(code) from exc


def _work_item(context: Any, work_id: str) -> dict[str, Any]:
    if not isinstance(context, dict):
        raise HostedCycleOwnWorkDeltaRecoveryError("HOSTED_CYCLE_OWN_WORK_CONTEXT_INVALID")
    machine = context.get("projectMachine")
    sensors = machine.get("sensors") if isinstance(machine, dict) else None
    continuation = sensors.get("continuations") if isinstance(sensors, dict) else None
    data = continuation.get("data") if isinstance(continuation, dict) else None
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise HostedCycleOwnWorkDeltaRecoveryError("HOSTED_CYCLE_OWN_WORK_WORK_UNAVAILABLE")
    matches = [item for item in items if isinstance(item, dict) and item.get("id") == work_id]
    if len(matches) != 1:
        raise HostedCycleOwnWorkDeltaRecoveryError("HOSTED_CYCLE_OWN_WORK_WORK_UNAVAILABLE")
    return copy.deepcopy(matches[0])


def _control_change(closure: dict[str, Any]) -> dict[str, Any]:
    try:
        receipt = closure["receipt"]
        blockers = receipt["blockers"]
        changes = receipt["delta"]["durableChanges"]
        uncovered = receipt["aggregateReadback"]["uncoveredDurableChanges"]
    except (KeyError, TypeError) as exc:
        raise HostedCycleOwnWorkDeltaRecoveryError("HOSTED_CYCLE_OWN_WORK_CLOSURE_INVALID") from exc
    if blockers != [BLOCKER] or len(uncovered) != 1:
        raise HostedCycleOwnWorkDeltaRecoveryError("HOSTED_CYCLE_OWN_WORK_FAILURE_NOT_NARROW")
    target = uncovered[0]
    matches: list[dict[str, Any]] = []
    for index, change in enumerate(changes):
        if not isinstance(change, dict):
            continue
        change_id = f"{change.get('kind')}:{change.get('name') or 'project-state'}:{index}"
        if change_id == target:
            matches.append(change)
    if len(matches) != 1:
        raise HostedCycleOwnWorkDeltaRecoveryError("HOSTED_CYCLE_OWN_WORK_CHANGE_UNAVAILABLE")
    change = matches[0]
    if (
        change.get("kind") != "source-head"
        or change.get("name") != "control"
        or change.get("branch") != "main"
        or not isinstance(change.get("before"), str)
        or not isinstance(change.get("after"), str)
        or change["before"] == change["after"]
    ):
        raise HostedCycleOwnWorkDeltaRecoveryError("HOSTED_CYCLE_OWN_WORK_CHANGE_UNSUPPORTED")
    return copy.deepcopy(change)


def _planned_at(result: dict[str, Any]) -> datetime:
    try:
        value = result["remoteReceipt"]["evidence"]["plan"]["intent"]["plannedAt"]
    except (KeyError, TypeError) as exc:
        raise HostedCycleOwnWorkDeltaRecoveryError(
            "HOSTED_CYCLE_OWN_WORK_LIFECYCLE_TIME_UNAVAILABLE"
        ) from exc
    return _parse_time(value, "HOSTED_CYCLE_OWN_WORK_LIFECYCLE_TIME_UNAVAILABLE")


def _lifecycle_results(
    comments: list[dict[str, Any]],
    *,
    close_comment_id: int,
    cycle_instance_id: str,
    branch: str,
) -> list[dict[str, Any]]:
    found: list[tuple[int, dict[str, Any]]] = []
    for comment in comments:
        cid = hosted_cycle_records.comment_id(comment)
        if cid is None or cid >= close_comment_id:
            continue
        user = comment.get("user") if isinstance(comment, dict) else None
        if not isinstance(user, dict) or user.get("login") != "github-actions[bot]":
            continue
        payload = hosted_cycle_records.json_after_marker(
            comment.get("body"), agent_write_lifecycle.RESULT_MARKER
        )
        if not isinstance(payload, dict) or payload.get("schemaVersion") != agent_write_lifecycle.RESULT_SCHEMA:
            continue
        try:
            result = agent_write_lifecycle.validate_result(payload)
        except RuntimeError:
            continue
        if result.get("cycleInstanceId") == cycle_instance_id and result.get("branch") == branch:
            found.append((cid, result))
    return [item for _, item in sorted(found, key=lambda pair: pair[0])]


def lifecycle_window(
    comments: list[dict[str, Any]],
    *,
    close_comment_id: int,
    cycle_instance_id: str,
    branch: str,
) -> dict[str, Any]:
    results = _lifecycle_results(
        comments,
        close_comment_id=close_comment_id,
        cycle_instance_id=cycle_instance_id,
        branch=branch,
    )
    if len(results) < 2 or results[0].get("action") != "acquire":
        raise HostedCycleOwnWorkDeltaRecoveryError("HOSTED_CYCLE_OWN_WORK_LIFECYCLE_INCOMPLETE")
    if results[-1].get("action") != "release":
        raise HostedCycleOwnWorkDeltaRecoveryError("HOSTED_CYCLE_OWN_WORK_LIFECYCLE_NOT_RELEASED")
    if any(item.get("action") not in {"acquire", "renew", "release"} for item in results):
        raise HostedCycleOwnWorkDeltaRecoveryError("HOSTED_CYCLE_OWN_WORK_LIFECYCLE_INVALID")
    if any(item.get("action") == "release" for item in results[:-1]):
        raise HostedCycleOwnWorkDeltaRecoveryError("HOSTED_CYCLE_OWN_WORK_LIFECYCLE_INVALID")

    first = results[0]
    binding = first["binding"]
    if binding.get("state") != "ACTIVE" or binding.get("previousBindingHash") is not None:
        raise HostedCycleOwnWorkDeltaRecoveryError("HOSTED_CYCLE_OWN_WORK_LIFECYCLE_INVALID")
    lease_id = binding["leaseId"]
    active_from = _planned_at(first)
    current_expiry = _parse_time(
        binding.get("expiresAt"), "HOSTED_CYCLE_OWN_WORK_LIFECYCLE_TIME_UNAVAILABLE"
    )
    previous_hash = binding["bindingHash"]
    result_hashes = [first["resultHash"]]

    for result in results[1:-1]:
        binding = result["binding"]
        if (
            result.get("action") != "renew"
            or binding.get("state") != "ACTIVE"
            or binding.get("leaseId") != lease_id
            or binding.get("previousBindingHash") != previous_hash
        ):
            raise HostedCycleOwnWorkDeltaRecoveryError("HOSTED_CYCLE_OWN_WORK_LIFECYCLE_INVALID")
        renewed_at = _planned_at(result)
        if renewed_at >= current_expiry:
            raise HostedCycleOwnWorkDeltaRecoveryError("HOSTED_CYCLE_OWN_WORK_LIFECYCLE_GAP")
        next_expiry = _parse_time(
            binding.get("expiresAt"), "HOSTED_CYCLE_OWN_WORK_LIFECYCLE_TIME_UNAVAILABLE"
        )
        if next_expiry <= current_expiry:
            raise HostedCycleOwnWorkDeltaRecoveryError("HOSTED_CYCLE_OWN_WORK_LIFECYCLE_INVALID")
        current_expiry = next_expiry
        previous_hash = binding["bindingHash"]
        result_hashes.append(result["resultHash"])

    release = results[-1]
    binding = release["binding"]
    if (
        binding.get("state") != "RELEASED"
        or binding.get("leaseId") != lease_id
        or binding.get("previousBindingHash") != previous_hash
    ):
        raise HostedCycleOwnWorkDeltaRecoveryError("HOSTED_CYCLE_OWN_WORK_LIFECYCLE_INVALID")
    released_at = _planned_at(release)
    active_until = min(current_expiry, released_at)
    if active_from >= active_until:
        raise HostedCycleOwnWorkDeltaRecoveryError("HOSTED_CYCLE_OWN_WORK_LIFECYCLE_WINDOW_INVALID")
    result_hashes.append(release["resultHash"])
    return {
        "leaseId": lease_id,
        "activeFrom": active_from.isoformat().replace("+00:00", "Z"),
        "activeUntil": active_until.isoformat().replace("+00:00", "Z"),
        "releaseObservedAt": released_at.isoformat().replace("+00:00", "Z"),
        "resultHashes": result_hashes,
    }


def validate_own_work_chain(
    pulls: list[dict[str, Any]],
    *,
    before_sha: str,
    after_sha: str,
    work_branch: str,
    work_pr_number: int | None,
    active_from: str,
    active_until: str,
) -> list[dict[str, Any]]:
    if not isinstance(pulls, list) or not pulls:
        raise HostedCycleOwnWorkDeltaRecoveryError("HOSTED_CYCLE_OWN_WORK_CONTROL_CHAIN_INVALID")
    start = _parse_time(active_from, "HOSTED_CYCLE_OWN_WORK_LIFECYCLE_TIME_UNAVAILABLE")
    end = _parse_time(active_until, "HOSTED_CYCLE_OWN_WORK_LIFECYCLE_TIME_UNAVAILABLE")
    expected_base = before_sha
    seen_prs: set[int] = set()
    seen_commits: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for pull in pulls:
        if not isinstance(pull, dict) or set(pull) != {
            "commitSha", "prNumber", "headBranch", "headSha", "baseSha", "mergedAt"
        }:
            raise HostedCycleOwnWorkDeltaRecoveryError("HOSTED_CYCLE_OWN_WORK_CONTROL_CHAIN_INVALID")
        merged_at = _parse_time(
            pull.get("mergedAt"), "HOSTED_CYCLE_OWN_WORK_MERGE_TIME_UNAVAILABLE"
        )
        commit = pull.get("commitSha")
        number = pull.get("prNumber")
        base = pull.get("baseSha")
        if (
            not isinstance(commit, str) or len(commit) != 40
            or not isinstance(pull.get("headSha"), str) or len(pull["headSha"]) != 40
            or not isinstance(base, str) or len(base) != 40
            or pull.get("headBranch") != work_branch
            or not isinstance(number, int) or isinstance(number, bool) or number <= 0
            or number in seen_prs or commit in seen_commits
            or base != expected_base
            or (work_pr_number is not None and number != work_pr_number)
            or not (start <= merged_at < end)
        ):
            raise HostedCycleOwnWorkDeltaRecoveryError("HOSTED_CYCLE_OWN_WORK_CONTROL_CHAIN_INVALID")
        normalized.append(copy.deepcopy(pull))
        seen_prs.add(number)
        seen_commits.add(commit)
        expected_base = commit
    if expected_base != after_sha:
        raise HostedCycleOwnWorkDeltaRecoveryError("HOSTED_CYCLE_OWN_WORK_CONTROL_CHAIN_INCOMPLETE")
    return normalized


def merged_pull_request_chain(
    *,
    before_sha: str,
    after_sha: str,
    work_branch: str,
    work_pr_number: int | None,
    active_from: str,
    active_until: str,
    transport: Any,
) -> list[dict[str, Any]]:
    cursor = after_sha
    reverse: list[dict[str, Any]] = []
    seen: set[str] = set()
    for _ in range(100):
        if cursor == before_sha:
            break
        if cursor in seen:
            raise HostedCycleOwnWorkDeltaRecoveryError("HOSTED_CYCLE_OWN_WORK_CONTROL_CHAIN_INVALID")
        seen.add(cursor)
        commit = _get(
            transport,
            f"repos/{hosted_agent_cycle.REPOSITORY}/commits/{cursor}",
            "HOSTED_CYCLE_OWN_WORK_CONTROL_CHAIN_UNAVAILABLE",
        )
        parents = commit.get("parents") if isinstance(commit, dict) else None
        if not isinstance(parents, list) or len(parents) < 2:
            raise HostedCycleOwnWorkDeltaRecoveryError("HOSTED_CYCLE_OWN_WORK_CONTROL_CHAIN_NOT_MERGE_ONLY")
        base_sha = parents[0].get("sha") if isinstance(parents[0], dict) else None
        if not isinstance(base_sha, str) or len(base_sha) != 40:
            raise HostedCycleOwnWorkDeltaRecoveryError("HOSTED_CYCLE_OWN_WORK_CONTROL_CHAIN_INVALID")
        payload = _get(
            transport,
            f"repos/{hosted_agent_cycle.REPOSITORY}/commits/{cursor}/pulls",
            "HOSTED_CYCLE_OWN_WORK_CONTROL_CHAIN_UNAVAILABLE",
        )
        if not isinstance(payload, list):
            raise HostedCycleOwnWorkDeltaRecoveryError("HOSTED_CYCLE_OWN_WORK_CONTROL_CHAIN_INVALID")
        matches = []
        for pull in payload:
            head = pull.get("head") if isinstance(pull, dict) else None
            base = pull.get("base") if isinstance(pull, dict) else None
            number = pull.get("number") if isinstance(pull, dict) else None
            if (
                isinstance(pull, dict)
                and pull.get("merged_at") is not None
                and pull.get("merge_commit_sha") == cursor
                and isinstance(head, dict) and head.get("ref") == work_branch
                and isinstance(head.get("sha"), str) and len(head["sha"]) == 40
                and isinstance(base, dict) and base.get("ref") == "main"
                and isinstance(number, int) and not isinstance(number, bool)
                and (work_pr_number is None or number == work_pr_number)
            ):
                matches.append(pull)
        if len(matches) != 1:
            raise HostedCycleOwnWorkDeltaRecoveryError("HOSTED_CYCLE_OWN_WORK_CONTROL_CHAIN_AMBIGUOUS")
        pull = matches[0]
        reverse.append({
            "commitSha": cursor,
            "prNumber": pull["number"],
            "headBranch": pull["head"]["ref"],
            "headSha": pull["head"]["sha"],
            "baseSha": base_sha,
            "mergedAt": pull["merged_at"],
        })
        cursor = base_sha
    else:
        raise HostedCycleOwnWorkDeltaRecoveryError("HOSTED_CYCLE_OWN_WORK_CONTROL_CHAIN_TOO_DEEP")
    if cursor != before_sha or not reverse:
        raise HostedCycleOwnWorkDeltaRecoveryError("HOSTED_CYCLE_OWN_WORK_CONTROL_CHAIN_INCOMPLETE")
    return validate_own_work_chain(
        list(reversed(reverse)),
        before_sha=before_sha,
        after_sha=after_sha,
        work_branch=work_branch,
        work_pr_number=work_pr_number,
        active_from=active_from,
        active_until=active_until,
    )


def build_merge_evidence(pull: dict[str, Any]) -> dict[str, Any]:
    """Return raw canonical close evidence; verify it before returning.

    ``agent_cycle_close.build_receipt`` owns normalization.  Returning its
    normalized projection here would make the close attempt to verify an already
    normalized object a second time and fail closed on field shape.
    """
    plan = git_mutation_plan.merge_pr(
        pr_number=pull["prNumber"],
        head_sha=pull["headSha"],
        base="main",
        control_branch="main",
        merge_method="merge",
    )
    raw = {
        "kind": "git-mutation-plan-readback",
        "plan": plan,
        "observed": {
            "kind": "merged-pr",
            "status": "PASS",
            "prNumber": pull["prNumber"],
            "headSha": pull["headSha"],
            "base": "main",
            "merged": True,
            "mergeCommitSha": pull["commitSha"],
        },
    }
    try:
        agent_cycle_close.verify_evidence(raw)
    except RuntimeError as exc:
        raise HostedCycleOwnWorkDeltaRecoveryError(
            "HOSTED_CYCLE_OWN_WORK_MERGE_EVIDENCE_INVALID"
        ) from exc
    return raw


def reconcile_failed_closure(
    *,
    before_context: dict[str, Any],
    cycle_instance_id: str,
    failed_closure: dict[str, Any],
    comments: list[dict[str, Any]],
    close_comment_id: int,
    transport: Any,
) -> dict[str, Any]:
    work_ref = before_context.get("workRef")
    if not isinstance(work_ref, dict) or not isinstance(work_ref.get("workId"), str):
        raise HostedCycleOwnWorkDeltaRecoveryError("HOSTED_CYCLE_OWN_WORK_WORK_UNAVAILABLE")
    work_id = work_ref["workId"]
    before_work = _work_item(before_context, work_id)
    after = failed_closure.get("afterContext")
    if before_work != _work_item(after, work_id):
        raise HostedCycleOwnWorkDeltaRecoveryError("HOSTED_CYCLE_OWN_WORK_WORK_CHANGED")
    work_branch = before_work.get("branch")
    work_pr = before_work.get("prNumber")
    if not isinstance(work_branch, str) or not work_branch or work_branch == "main":
        raise HostedCycleOwnWorkDeltaRecoveryError("HOSTED_CYCLE_OWN_WORK_WORK_UNAVAILABLE")
    if work_pr is not None and (
        not isinstance(work_pr, int) or isinstance(work_pr, bool) or work_pr <= 0
    ):
        raise HostedCycleOwnWorkDeltaRecoveryError("HOSTED_CYCLE_OWN_WORK_WORK_UNAVAILABLE")

    original = hosted_cycle_external_delta_recovery.reconstruct_original_evidence(
        comments,
        failed_closure=failed_closure,
        close_comment_id=close_comment_id,
    )
    try:
        agent_cycle_close.validate_closure(failed_closure, before_context, evidence=original)
    except RuntimeError as exc:
        raise HostedCycleOwnWorkDeltaRecoveryError("HOSTED_CYCLE_OWN_WORK_CLOSURE_MISMATCH") from exc
    if failed_closure.get("status") != "UNKNOWN":
        raise HostedCycleOwnWorkDeltaRecoveryError("HOSTED_CYCLE_OWN_WORK_FAILURE_NOT_NARROW")

    change = _control_change(failed_closure)
    window = lifecycle_window(
        comments,
        close_comment_id=close_comment_id,
        cycle_instance_id=cycle_instance_id,
        branch=work_branch,
    )
    pulls = merged_pull_request_chain(
        before_sha=change["before"],
        after_sha=change["after"],
        work_branch=work_branch,
        work_pr_number=work_pr,
        active_from=window["activeFrom"],
        active_until=window["activeUntil"],
        transport=transport,
    )
    raw_merge_evidence = [build_merge_evidence(pull) for pull in pulls]
    verified_merge_evidence = [
        agent_cycle_close.verify_evidence(item) for item in raw_merge_evidence
    ]
    evidence = [*original, *raw_merge_evidence]
    receipt = agent_cycle_close.build_receipt(before_context, after, evidence=evidence)
    closure_body = {
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
    reconciled = {**closure_body, "closureHash": stable_hash(closure_body)}
    try:
        agent_cycle_close.validate_closure(reconciled, before_context, evidence=evidence)
    except RuntimeError as exc:
        raise HostedCycleOwnWorkDeltaRecoveryError(
            "HOSTED_CYCLE_OWN_WORK_RECONCILIATION_INVALID"
        ) from exc
    if reconciled["status"] != "PASS" or reconciled["receipt"]["aggregateReadback"]["uncoveredDurableChanges"]:
        raise HostedCycleOwnWorkDeltaRecoveryError("HOSTED_CYCLE_OWN_WORK_NOT_RECONCILED")

    proof_body = {
        "schemaVersion": PROOF_SCHEMA,
        "cycleId": before_context["cycleId"],
        "cycleInstanceId": cycle_instance_id,
        "workId": work_id,
        "workBranch": work_branch,
        "workPrNumber": work_pr,
        "leaseId": window["leaseId"],
        "activeFrom": window["activeFrom"],
        "activeUntil": window["activeUntil"],
        "releaseObservedAt": window["releaseObservedAt"],
        "lifecycleResultHashes": copy.deepcopy(window["resultHashes"]),
        "controlBefore": change["before"],
        "controlAfter": change["after"],
        "mergedPullRequests": copy.deepcopy(pulls),
        "mergeEvidenceHashes": sorted(item["evidenceHash"] for item in verified_merge_evidence),
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    proof = {**proof_body, "proofHash": stable_hash(proof_body)}
    return {
        "ownWorkIntegrationProof": proof,
        "mergeEvidence": verified_merge_evidence,
        "reconciledClosure": reconciled,
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
