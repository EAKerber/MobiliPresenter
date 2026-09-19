from __future__ import annotations

import argparse
import base64
import json
import re
import tempfile
from pathlib import Path
from typing import Any

from tools import agent_cycle_close as _canonical
from tools import git_mutation_plan
from tools import continuation_remote
from tools.coordination_remote import ApiError, CoordinationRemoteError, GhApiTransport
from tools.canonical import stable_hash

REPOSITORY = "EAKerber/MobiliPresenter"
CONTROL_BRANCH = "main"
CONTINUATION_BRANCH = "coordination/continuations"
COORDINATION_BRANCH = "coordination/leases"
COORDINATION_PATH = "ops/coordination/leases.json"
SHA_RE = re.compile(r"^[0-9a-f]{40,64}$")
CHANGE_REF_RE = re.compile(r"^source-head:([a-z][a-z0-9-]*):(0|[1-9][0-9]*)$")
MAX_FIRST_PARENT_DEPTH = 128


def __getattr__(name: str) -> Any:
    return getattr(_canonical, name)


def _json_response(response: Any, code: str) -> Any:
    try:
        return json.loads(response.body)
    except (AttributeError, json.JSONDecodeError) as exc:
        raise RuntimeError(code) from exc


def _get_json(transport: Any, endpoint: str, code: str) -> Any:
    try:
        response = transport.request("GET", endpoint)
    except (ApiError, CoordinationRemoteError) as exc:
        raise RuntimeError(code) from exc
    return _json_response(response, code)


def _change_id(change: Any, index: int) -> str | None:
    if not isinstance(change, dict):
        return None
    kind = change.get("kind")
    name = change.get("name")
    if not isinstance(kind, str) or not isinstance(name, str):
        return None
    return f"{kind}:{name}:{index}"



def _context_work_item(context: Any, work_id: str) -> dict[str, Any]:
    if not isinstance(context, dict):
        raise RuntimeError("AGENT_CYCLE_CLOSE_NONINTERFERENCE_CONTEXT_INVALID")
    machine = context.get("projectMachine")
    sensors = machine.get("sensors") if isinstance(machine, dict) else None
    continuation_sensor = sensors.get("continuations") if isinstance(sensors, dict) else None
    data = continuation_sensor.get("data") if isinstance(continuation_sensor, dict) else None
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise RuntimeError("AGENT_CYCLE_CLOSE_NONINTERFERENCE_WORK_UNAVAILABLE")
    matches = [item for item in items if isinstance(item, dict) and item.get("id") == work_id]
    if len(matches) != 1:
        raise RuntimeError("AGENT_CYCLE_CLOSE_NONINTERFERENCE_WORK_UNAVAILABLE")
    return matches[0]


def _current_branch_head(branch: str, *, transport: Any) -> str:
    value = _get_json(
        transport,
        f"repos/{REPOSITORY}/git/ref/heads/{branch}",
        "AGENT_CYCLE_CLOSE_NONINTERFERENCE_REF_UNAVAILABLE",
    )
    sha = (value.get("object") or {}).get("sha") if isinstance(value, dict) else None
    if not isinstance(sha, str) or SHA_RE.fullmatch(sha) is None:
        raise RuntimeError("AGENT_CYCLE_CLOSE_NONINTERFERENCE_REF_INVALID")
    return sha


def _ambient_uncovered_changes(closure: Any) -> list[dict[str, Any]] | None:
    if not isinstance(closure, dict) or closure.get("status") != "UNKNOWN":
        return None
    receipt = closure.get("receipt")
    if not isinstance(receipt, dict) or receipt.get("blockers") != ["UNATTRIBUTED_DURABLE_DELTA"]:
        return None
    delta = receipt.get("delta")
    aggregate = receipt.get("aggregateReadback")
    if not isinstance(delta, dict) or not isinstance(aggregate, dict):
        return None
    changes = delta.get("durableChanges")
    covered = aggregate.get("coveredDurableChanges")
    uncovered = aggregate.get("uncoveredDurableChanges")
    if (
        not isinstance(changes, list)
        or not isinstance(covered, list)
        or not isinstance(uncovered, list)
        or len(uncovered) not in {3, 4}
        or any(not isinstance(item, str) for item in [*covered, *uncovered])
        or len(set(covered)) != len(covered)
        or len(set(uncovered)) != len(uncovered)
        or set(covered) & set(uncovered)
    ):
        return None

    all_ids: list[str] = []
    indexed: dict[str, dict[str, Any]] = {}
    selected: list[dict[str, Any]] = []
    for index, change in enumerate(changes):
        change_id = _change_id(change, index)
        if change_id is None:
            return None
        all_ids.append(change_id)
        if change_id not in uncovered:
            continue
        name = change.get("name") if isinstance(change, dict) else None
        if (
            not isinstance(change, dict)
            or change.get("kind") != "source-head"
            or not isinstance(name, str)
            or not name
            or name in indexed
        ):
            return None
        indexed[name] = change
        selected.append(change)
    if set(covered) | set(uncovered) != set(all_ids):
        return None
    expected = {"continuation", "control", "inspection"}
    if "coordination" in indexed:
        expected.add("coordination")
    if set(indexed) != expected:
        return None

    continuation = indexed["continuation"]
    control = indexed["control"]
    inspection = indexed["inspection"]
    coordination = indexed.get("coordination")
    if (
        continuation.get("branch") != CONTINUATION_BRANCH
        or control.get("branch") != CONTROL_BRANCH
        or inspection.get("branch") != CONTROL_BRANCH
        or (coordination is not None and coordination.get("branch") != COORDINATION_BRANCH)
        or control.get("before") != inspection.get("before")
        or control.get("after") != inspection.get("after")
    ):
        return None
    for change in selected:
        if (
            not isinstance(change.get("before"), str)
            or not isinstance(change.get("after"), str)
            or change["before"] == change["after"]
            or SHA_RE.fullmatch(change["before"]) is None
            or SHA_RE.fullmatch(change["after"]) is None
        ):
            return None
    return selected

def _continuation_noninterference(
    before_sha: str,
    after_sha: str,
    *,
    work_id: str,
    transport: Any,
) -> dict[str, Any]:
    if _current_branch_head(CONTINUATION_BRANCH, transport=transport) != after_sha:
        raise RuntimeError("AGENT_CYCLE_CLOSE_NONINTERFERENCE_CONTINUATION_HEAD_MISMATCH")
    comparison = _get_json(
        transport,
        f"repos/{REPOSITORY}/compare/{before_sha}...{after_sha}",
        "AGENT_CYCLE_CLOSE_NONINTERFERENCE_CONTINUATION_COMPARE_UNAVAILABLE",
    )
    merge_base = comparison.get("merge_base_commit") if isinstance(comparison, dict) else None
    files = comparison.get("files") if isinstance(comparison, dict) else None
    commits = comparison.get("commits") if isinstance(comparison, dict) else None
    ahead_by = comparison.get("ahead_by") if isinstance(comparison, dict) else None
    if (
        not isinstance(comparison, dict)
        or comparison.get("status") != "ahead"
        or not isinstance(merge_base, dict)
        or merge_base.get("sha") != before_sha
        or not isinstance(ahead_by, int)
        or isinstance(ahead_by, bool)
        or ahead_by <= 0
        or not isinstance(commits, list)
        or len(commits) != ahead_by
        or not isinstance(files, list)
    ):
        raise RuntimeError("AGENT_CYCLE_CLOSE_NONINTERFERENCE_CONTINUATION_COMPARE_INVALID")
    paths: list[str] = []
    for item in files:
        filename = item.get("filename") if isinstance(item, dict) else None
        if not isinstance(filename, str) or not filename:
            raise RuntimeError("AGENT_CYCLE_CLOSE_NONINTERFERENCE_CONTINUATION_COMPARE_INVALID")
        paths.append(filename)
    paths = sorted(set(paths))
    work_path = f"ops/continuations/{work_id}.json"
    if work_path in paths:
        raise RuntimeError("AGENT_CYCLE_CLOSE_NONINTERFERENCE_WORK_TOUCHED")
    return {
        "branch": CONTINUATION_BRANCH,
        "before": before_sha,
        "after": after_sha,
        "workPath": work_path,
        "changedPaths": paths,
    }


def _coordination_binding_projection(state: Any, *, work_branch: str) -> dict[str, Any]:
    if not isinstance(state, dict):
        raise RuntimeError("AGENT_CYCLE_CLOSE_NONINTERFERENCE_COORDINATION_STATE_INVALID")
    projection: dict[str, list[Any]] = {}
    for key in ("intents", "leases"):
        records = state.get(key)
        if not isinstance(records, list):
            raise RuntimeError("AGENT_CYCLE_CLOSE_NONINTERFERENCE_COORDINATION_STATE_INVALID")
        matched = []
        for record in records:
            if not isinstance(record, dict):
                raise RuntimeError("AGENT_CYCLE_CLOSE_NONINTERFERENCE_COORDINATION_STATE_INVALID")
            if work_branch in json.dumps(record, sort_keys=True, separators=(",", ":")):
                matched.append(record)
        projection[key] = matched
    return projection


def _coordination_state_at(sha: str, *, transport: Any) -> dict[str, Any]:
    payload = _get_json(
        transport,
        f"repos/{REPOSITORY}/contents/{COORDINATION_PATH}?ref={sha}",
        "AGENT_CYCLE_CLOSE_NONINTERFERENCE_COORDINATION_CONTENT_UNAVAILABLE",
    )
    if (
        not isinstance(payload, dict)
        or payload.get("encoding") != "base64"
        or not isinstance(payload.get("content"), str)
    ):
        raise RuntimeError("AGENT_CYCLE_CLOSE_NONINTERFERENCE_COORDINATION_CONTENT_INVALID")
    try:
        raw = base64.b64decode(payload["content"]).decode("utf-8")
        value = json.loads(raw)
    except Exception as exc:
        raise RuntimeError("AGENT_CYCLE_CLOSE_NONINTERFERENCE_COORDINATION_CONTENT_INVALID") from exc
    if not isinstance(value, dict):
        raise RuntimeError("AGENT_CYCLE_CLOSE_NONINTERFERENCE_COORDINATION_CONTENT_INVALID")
    return value


def _coordination_noninterference(
    before_sha: str,
    after_sha: str,
    *,
    work_branch: str,
    transport: Any,
) -> dict[str, Any]:
    if _current_branch_head(COORDINATION_BRANCH, transport=transport) != after_sha:
        raise RuntimeError("AGENT_CYCLE_CLOSE_NONINTERFERENCE_COORDINATION_HEAD_MISMATCH")
    comparison = _get_json(
        transport,
        f"repos/{REPOSITORY}/compare/{before_sha}...{after_sha}",
        "AGENT_CYCLE_CLOSE_NONINTERFERENCE_COORDINATION_COMPARE_UNAVAILABLE",
    )
    merge_base = comparison.get("merge_base_commit") if isinstance(comparison, dict) else None
    commits = comparison.get("commits") if isinstance(comparison, dict) else None
    ahead_by = comparison.get("ahead_by") if isinstance(comparison, dict) else None
    if (
        not isinstance(comparison, dict)
        or comparison.get("status") != "ahead"
        or not isinstance(merge_base, dict)
        or merge_base.get("sha") != before_sha
        or not isinstance(ahead_by, int)
        or isinstance(ahead_by, bool)
        or ahead_by <= 0
        or not isinstance(commits, list)
        or len(commits) != ahead_by
    ):
        raise RuntimeError("AGENT_CYCLE_CLOSE_NONINTERFERENCE_COORDINATION_COMPARE_INVALID")
    shas = [before_sha]
    for commit in commits:
        sha = commit.get("sha") if isinstance(commit, dict) else None
        if not isinstance(sha, str) or SHA_RE.fullmatch(sha) is None:
            raise RuntimeError("AGENT_CYCLE_CLOSE_NONINTERFERENCE_COORDINATION_COMPARE_INVALID")
        shas.append(sha)
    states = []
    for sha in shas:
        projection = _coordination_binding_projection(
            _coordination_state_at(sha, transport=transport),
            work_branch=work_branch,
        )
        if projection != {"intents": [], "leases": []}:
            raise RuntimeError("AGENT_CYCLE_CLOSE_NONINTERFERENCE_BOUND_WORK_COORDINATION_TOUCHED")
        states.append({"sha": sha, "bindingHash": stable_hash(projection)})
    return {
        "branch": COORDINATION_BRANCH,
        "before": before_sha,
        "after": after_sha,
        "workBranch": work_branch,
        "states": states,
    }


def _unrelated_main_pr_chain(
    before_sha: str,
    after_sha: str,
    *,
    work_branch: str,
    work_pr_number: int | None,
    transport: Any,
) -> list[dict[str, Any]]:
    if _current_branch_head(CONTROL_BRANCH, transport=transport) != after_sha:
        raise RuntimeError("AGENT_CYCLE_CLOSE_NONINTERFERENCE_MAIN_HEAD_MISMATCH")
    cursor = after_sha
    newest_first: list[dict[str, Any]] = []
    for _ in range(MAX_FIRST_PARENT_DEPTH):
        commit = _get_json(
            transport,
            f"repos/{REPOSITORY}/git/commits/{cursor}",
            "AGENT_CYCLE_CLOSE_NONINTERFERENCE_COMMIT_UNAVAILABLE",
        )
        parents = commit.get("parents") if isinstance(commit, dict) else None
        if (
            not isinstance(parents, list)
            or not parents
            or not isinstance(parents[0], dict)
        ):
            raise RuntimeError("AGENT_CYCLE_CLOSE_NONINTERFERENCE_NONLINEAR_HISTORY")
        parent = parents[0].get("sha")
        if not isinstance(parent, str) or SHA_RE.fullmatch(parent) is None:
            raise RuntimeError("AGENT_CYCLE_CLOSE_NONINTERFERENCE_PARENT_INVALID")

        pulls = _get_json(
            transport,
            f"repos/{REPOSITORY}/commits/{cursor}/pulls",
            "AGENT_CYCLE_CLOSE_NONINTERFERENCE_PR_UNAVAILABLE",
        )
        if not isinstance(pulls, list):
            raise RuntimeError("AGENT_CYCLE_CLOSE_NONINTERFERENCE_PR_INVALID")
        candidates: list[dict[str, Any]] = []
        for item in pulls:
            if not isinstance(item, dict):
                continue
            base = item.get("base")
            head = item.get("head")
            if not isinstance(base, dict) or not isinstance(head, dict):
                continue
            if (
                item.get("state") == "closed"
                and isinstance(item.get("merged_at"), str)
                and item.get("merge_commit_sha") == cursor
                and base.get("ref") == CONTROL_BRANCH
                and base.get("sha") == parent
                and isinstance(head.get("ref"), str)
                and head["ref"]
                and isinstance(item.get("number"), int)
                and not isinstance(item.get("number"), bool)
                and item["number"] > 0
            ):
                candidates.append(item)
        if len(candidates) != 1:
            raise RuntimeError("AGENT_CYCLE_CLOSE_NONINTERFERENCE_PR_AMBIGUOUS")
        pull = candidates[0]
        if pull["head"]["ref"] == work_branch or (
            work_pr_number is not None and pull["number"] == work_pr_number
        ):
            raise RuntimeError("AGENT_CYCLE_CLOSE_NONINTERFERENCE_BOUND_WORK_MERGE")
        newest_first.append({
            "commitSha": cursor,
            "prNumber": pull["number"],
            "headBranch": pull["head"]["ref"],
            "baseSha": parent,
        })
        if parent == before_sha:
            return list(reversed(newest_first))
        cursor = parent
    raise RuntimeError("AGENT_CYCLE_CLOSE_NONINTERFERENCE_ANCESTRY_MISMATCH")


def noninterference_evidence(
    closure: dict[str, Any],
    *,
    context_path: str,
    transport: Any | None = None,
) -> dict[str, Any] | None:
    changes = _ambient_uncovered_changes(closure)
    if changes is None:
        return None
    carrier = transport or GhApiTransport()
    try:
        before = json.loads(Path(context_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("AGENT_CYCLE_CLOSE_NONINTERFERENCE_CONTEXT_UNAVAILABLE") from exc
    after = closure.get("afterContext")
    before_ref = before.get("workRef") if isinstance(before, dict) else None
    after_ref = after.get("workRef") if isinstance(after, dict) else None
    work_id = before_ref.get("workId") if isinstance(before_ref, dict) else None
    if not isinstance(work_id, str) or not work_id or after_ref != before_ref:
        raise RuntimeError("AGENT_CYCLE_CLOSE_NONINTERFERENCE_WORK_REF_REQUIRED")
    before_work = _context_work_item(before, work_id)
    after_work = _context_work_item(after, work_id)
    if before_work != after_work:
        raise RuntimeError("AGENT_CYCLE_CLOSE_NONINTERFERENCE_WORK_CHANGED")
    work_branch = before_work.get("branch")
    work_pr = before_work.get("prNumber")
    if (
        not isinstance(work_branch, str)
        or not work_branch
        or work_branch == CONTROL_BRANCH
        or (work_pr is not None and (
            not isinstance(work_pr, int) or isinstance(work_pr, bool) or work_pr <= 0
        ))
    ):
        raise RuntimeError("AGENT_CYCLE_CLOSE_NONINTERFERENCE_WORK_BINDING_INVALID")

    by_name = {change["name"]: change for change in changes}
    continuation = by_name["continuation"]
    control = by_name["control"]
    coordination = by_name.get("coordination")
    continuation_readback = _continuation_noninterference(
        continuation["before"],
        continuation["after"],
        work_id=work_id,
        transport=carrier,
    )
    coordination_readback = None
    if coordination is not None:
        coordination_readback = _coordination_noninterference(
            coordination["before"],
            coordination["after"],
            work_branch=work_branch,
            transport=carrier,
        )
    main_pulls = _unrelated_main_pr_chain(
        control["before"],
        control["after"],
        work_branch=work_branch,
        work_pr_number=work_pr,
        transport=carrier,
    )
    body = {
        "kind": "agent-cycle-noninterference-readback",
        "schemaVersion": _canonical.NONINTERFERENCE_SCHEMA,
        "cycleId": closure.get("cycleId"),
        "workId": work_id,
        "workBranch": work_branch,
        "workPrNumber": work_pr,
        "workStateHash": stable_hash(before_work),
        "coveredChanges": changes,
        "continuationReadback": continuation_readback,
        "coordinationReadback": coordination_readback,
        "controlReadback": {
            "branch": CONTROL_BRANCH,
            "before": control["before"],
            "after": control["after"],
            "mergedPullRequests": main_pulls,
        },
        "readOnly": True,
        "semanticAuthority": False,
        "authorizesMutation": False,
    }
    evidence = {**body, "evidenceHash": stable_hash(body)}
    _canonical.verify_evidence(evidence)
    return evidence


def recoverable_main_delta(closure: Any) -> tuple[str, str] | None:
    if not isinstance(closure, dict) or closure.get("status") != "UNKNOWN":
        return None
    receipt = closure.get("receipt")
    if not isinstance(receipt, dict) or receipt.get("blockers") != ["UNATTRIBUTED_DURABLE_DELTA"]:
        return None
    delta = receipt.get("delta")
    if not isinstance(delta, dict):
        return None
    changes = delta.get("durableChanges")
    if not isinstance(changes, list) or len(changes) < 2:
        return None

    aggregate = receipt.get("aggregateReadback")
    if not isinstance(aggregate, dict):
        return None
    covered = aggregate.get("coveredDurableChanges")
    uncovered = aggregate.get("uncoveredDurableChanges")
    if not isinstance(covered, list) or not isinstance(uncovered, list) or len(uncovered) != 2:
        return None
    if any(not isinstance(item, str) for item in [*covered, *uncovered]):
        return None
    if len(set(covered)) != len(covered) or len(set(uncovered)) != len(uncovered):
        return None
    if set(covered) & set(uncovered):
        return None

    all_ids: list[str] = []
    for index, change in enumerate(changes):
        change_id = _change_id(change, index)
        if change_id is None:
            return None
        all_ids.append(change_id)
    if set(covered) | set(uncovered) != set(all_ids):
        return None

    indexed: dict[str, tuple[int, dict[str, Any]]] = {}
    for ref in uncovered:
        match = CHANGE_REF_RE.fullmatch(ref)
        if match is None:
            return None
        name = match.group(1)
        index = int(match.group(2))
        if index >= len(changes):
            return None
        change = changes[index]
        if (
            not isinstance(change, dict)
            or change.get("kind") != "source-head"
            or change.get("name") != name
            or change.get("branch") != CONTROL_BRANCH
            or name not in {"control", "inspection"}
            or name in indexed
            or _change_id(change, index) != ref
        ):
            return None
        indexed[name] = (index, change)
    if set(indexed) != {"control", "inspection"}:
        return None

    _, control = indexed["control"]
    _, inspection = indexed["inspection"]
    before = control.get("before")
    after = control.get("after")
    if (
        not isinstance(before, str)
        or not isinstance(after, str)
        or before == after
        or SHA_RE.fullmatch(before) is None
        or SHA_RE.fullmatch(after) is None
        or inspection.get("before") != before
        or inspection.get("after") != after
    ):
        return None
    return before, after


def _first_child_after(
    before_sha: str,
    after_sha: str,
    *,
    transport: Any,
) -> str:
    cursor = after_sha
    for _ in range(MAX_FIRST_PARENT_DEPTH):
        commit = _get_json(
            transport,
            f"repos/{REPOSITORY}/git/commits/{cursor}",
            "AGENT_CYCLE_CLOSE_MERGE_RECOVERY_COMMIT_UNAVAILABLE",
        )
        parents = commit.get("parents") if isinstance(commit, dict) else None
        if not isinstance(parents, list):
            raise RuntimeError("AGENT_CYCLE_CLOSE_MERGE_RECOVERY_COMMIT_INVALID")
        if len(parents) == 0:
            raise RuntimeError("AGENT_CYCLE_CLOSE_MERGE_RECOVERY_ANCESTRY_MISMATCH")
        if len(parents) != 1 or not isinstance(parents[0], dict):
            raise RuntimeError("AGENT_CYCLE_CLOSE_MERGE_RECOVERY_NONLINEAR_HISTORY")
        parent = parents[0].get("sha")
        if not isinstance(parent, str) or SHA_RE.fullmatch(parent) is None:
            raise RuntimeError("AGENT_CYCLE_CLOSE_MERGE_RECOVERY_PARENT_INVALID")
        if parent == before_sha:
            return cursor
        cursor = parent
    raise RuntimeError("AGENT_CYCLE_CLOSE_MERGE_RECOVERY_ANCESTRY_MISMATCH")


def _work_expectation(context_path: str, *, transport: Any) -> tuple[int, str]:
    try:
        context = json.loads(Path(context_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("AGENT_CYCLE_CLOSE_MERGE_RECOVERY_CONTEXT_UNAVAILABLE") from exc
    work_ref = context.get("workRef") if isinstance(context, dict) else None
    work_id = work_ref.get("workId") if isinstance(work_ref, dict) else None
    if not isinstance(work_id, str) or not work_id:
        raise RuntimeError("AGENT_CYCLE_CLOSE_MERGE_RECOVERY_WORK_REF_REQUIRED")
    try:
        observed = continuation_remote.GitHubContinuationAuthority(
            transport=transport,
            repository=REPOSITORY,
        ).observe()
    except Exception as exc:
        raise RuntimeError("AGENT_CYCLE_CLOSE_MERGE_RECOVERY_WORK_UNAVAILABLE") from exc
    work = observed.items.get(work_id)
    if not isinstance(work, dict) or work.get("status") != "DONE":
        raise RuntimeError("AGENT_CYCLE_CLOSE_MERGE_RECOVERY_WORK_NOT_DONE")
    pr_number = work.get("prNumber")
    last_known_good = work.get("lastKnownGood")
    merge_sha = last_known_good.get("sha") if isinstance(last_known_good, dict) else None
    if (
        not isinstance(pr_number, int)
        or isinstance(pr_number, bool)
        or pr_number <= 0
        or not isinstance(merge_sha, str)
        or SHA_RE.fullmatch(merge_sha) is None
    ):
        raise RuntimeError("AGENT_CYCLE_CLOSE_MERGE_RECOVERY_WORK_BINDING_INVALID")
    return pr_number, merge_sha


def merge_readback_evidence(
    before_sha: str,
    after_sha: str,
    *,
    transport: Any | None = None,
    expected_pr_number: int | None = None,
    expected_merge_sha: str | None = None,
) -> dict[str, Any]:
    if SHA_RE.fullmatch(before_sha) is None or SHA_RE.fullmatch(after_sha) is None:
        raise RuntimeError("AGENT_CYCLE_CLOSE_MERGE_RECOVERY_SHA_INVALID")
    carrier = transport or GhApiTransport()

    ref = _get_json(
        carrier,
        f"repos/{REPOSITORY}/git/ref/heads/{CONTROL_BRANCH}",
        "AGENT_CYCLE_CLOSE_MERGE_RECOVERY_MAIN_UNAVAILABLE",
    )
    observed_main = (ref.get("object") or {}).get("sha") if isinstance(ref, dict) else None
    if observed_main != after_sha:
        raise RuntimeError("AGENT_CYCLE_CLOSE_MERGE_RECOVERY_MAIN_MISMATCH")

    merge_sha = _first_child_after(before_sha, after_sha, transport=carrier)
    if expected_merge_sha is not None and merge_sha != expected_merge_sha:
        raise RuntimeError("AGENT_CYCLE_CLOSE_MERGE_RECOVERY_WORK_SHA_MISMATCH")

    pulls = _get_json(
        carrier,
        f"repos/{REPOSITORY}/commits/{merge_sha}/pulls",
        "AGENT_CYCLE_CLOSE_MERGE_RECOVERY_PR_UNAVAILABLE",
    )
    if not isinstance(pulls, list):
        raise RuntimeError("AGENT_CYCLE_CLOSE_MERGE_RECOVERY_PR_INVALID")
    candidates: list[dict[str, Any]] = []
    for item in pulls:
        if not isinstance(item, dict):
            continue
        base = item.get("base")
        head = item.get("head")
        if not isinstance(base, dict) or not isinstance(head, dict):
            continue
        if (
            item.get("state") == "closed"
            and isinstance(item.get("merged_at"), str)
            and item.get("merge_commit_sha") == merge_sha
            and base.get("ref") == CONTROL_BRANCH
            and base.get("sha") == before_sha
            and isinstance(head.get("sha"), str)
            and SHA_RE.fullmatch(head["sha"]) is not None
            and isinstance(item.get("number"), int)
            and not isinstance(item.get("number"), bool)
            and item["number"] > 0
        ):
            candidates.append(item)
    if len(candidates) != 1:
        raise RuntimeError("AGENT_CYCLE_CLOSE_MERGE_RECOVERY_PR_AMBIGUOUS")

    pull = candidates[0]
    if expected_pr_number is not None and pull["number"] != expected_pr_number:
        raise RuntimeError("AGENT_CYCLE_CLOSE_MERGE_RECOVERY_WORK_PR_MISMATCH")
    head_sha = pull["head"]["sha"]
    plan = git_mutation_plan.merge_pr(
        pr_number=pull["number"],
        head_sha=head_sha,
        base=CONTROL_BRANCH,
        control_branch=CONTROL_BRANCH,
        merge_method="squash",
    )
    observed = {
        "kind": "merged-pr",
        "status": "PASS",
        "prNumber": pull["number"],
        "headSha": head_sha,
        "base": CONTROL_BRANCH,
        "merged": True,
        "mergeCommitSha": merge_sha,
    }
    evidence = {
        "kind": "git-mutation-plan-readback",
        "plan": plan,
        "observed": observed,
    }
    _canonical.verify_evidence(evidence)
    return evidence


def recovery_evidence(
    closure: dict[str, Any],
    *,
    context_path: str,
    transport: Any | None = None,
    raise_on_error: bool = False,
) -> dict[str, Any] | None:
    carrier = transport or GhApiTransport()
    delta = recoverable_main_delta(closure)
    if delta is not None:
        try:
            expected_pr, expected_merge = _work_expectation(context_path, transport=carrier)
            return merge_readback_evidence(
                *delta,
                transport=carrier,
                expected_pr_number=expected_pr,
                expected_merge_sha=expected_merge,
            )
        except RuntimeError:
            pass
    try:
        return noninterference_evidence(
            closure,
            context_path=context_path,
            transport=carrier,
        )
    except RuntimeError:
        if raise_on_error:
            raise
        return None


def recover_closure(
    closure: dict[str, Any],
    *,
    context_path: str,
    machine_scope: str | None,
    observations_path: str | None,
    runtime_providers: str | None,
    evidence_paths: list[str],
    transport: Any | None = None,
    recovery_evidence_path: str | None = None,
    raise_on_recovery_error: bool = False,
) -> dict[str, Any]:
    evidence = recovery_evidence(
        closure,
        context_path=context_path,
        transport=transport,
        raise_on_error=raise_on_recovery_error,
    )
    if evidence is None:
        return closure

    if recovery_evidence_path is not None:
        path = Path(recovery_evidence_path)
        path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        recovery_path = str(path)
        recovered = _canonical.close_from_files(
            context_path=context_path,
            machine_scope=machine_scope,
            observations_path=observations_path,
            runtime_providers=runtime_providers,
            evidence_paths=[*evidence_paths, recovery_path],
        )
        return recovered if recovered.get("status") == "PASS" else closure

    with tempfile.TemporaryDirectory(prefix="agent-close-merge-recovery-") as root:
        path = Path(root) / "merge-readback-evidence.json"
        path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        recovered = _canonical.close_from_files(
            context_path=context_path,
            machine_scope=machine_scope,
            observations_path=observations_path,
            runtime_providers=runtime_providers,
            evidence_paths=[*evidence_paths, str(path)],
        )
    return recovered if recovered.get("status") == "PASS" else closure


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent close")
    parser.add_argument("--context", required=True)
    parser.add_argument("--machine-scope", choices=("local", "base", "live"))
    parser.add_argument("--observations")
    parser.add_argument("--runtime-providers")
    parser.add_argument("--evidence", action="append", default=[])
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    try:
        payload = _canonical.close_from_files(
            context_path=args.context,
            machine_scope=args.machine_scope,
            observations_path=args.observations,
            runtime_providers=args.runtime_providers,
            evidence_paths=args.evidence,
        )
        if payload.get("status") == "UNKNOWN":
            payload = recover_closure(
                payload,
                context_path=args.context,
                machine_scope=args.machine_scope,
                observations_path=args.observations,
                runtime_providers=args.runtime_providers,
                evidence_paths=args.evidence,
            )
        if args.as_json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            receipt = payload["receipt"]
            print(
                "AGENT CYCLE CLOSE\n"
                f"  cycle: {payload['cycleId']}\n"
                f"  status: {payload['status']}\n"
                f"  durable-changes: {len(receipt['delta']['durableChanges'])}\n"
                f"  uncovered: {len(receipt['aggregateReadback']['uncoveredDurableChanges'])}\n"
                f"  receipt: {receipt['receiptHash']}"
            )
        if payload["status"] == "BLOCKED":
            return 2
        if payload["status"] == "UNKNOWN":
            return 1
        return 0
    except RuntimeError as exc:
        if args.as_json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"BLOCKED\n{exc}")
        return 2
