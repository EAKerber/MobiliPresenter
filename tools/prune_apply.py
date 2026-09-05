#!/usr/bin/env python3
"""CAS-style destructive executor for one exact GitPrunePlan 0.4.

The planner remains the sole classifier. This executor may remove only entries
already classified as delete-candidate + autoDeleteEligible by one explicit,
materialized plan whose hash is supplied separately as expected-plan.

It fails closed on plan mismatch, incomplete observations, repository-wide ref
drift, control-head drift, open PRs, per-ref SHA mismatch, failed atomic
expected-SHA deletion, or failed readback. A delete that reports failure may be
accepted as ALREADY_ABSENT only when an immediate full-inventory readback
exactly matches the expected state with that single ref removed; any other
drift remains a hard failure.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

import prune_plan

ROOT = Path(__file__).resolve().parents[1]
ERROR_EXIT = 2
AUTH_ENV = "MOBILIPRESENTER_PRUNE_AUTHORIZED"
READBACK_ATTEMPTS = 8
READBACK_DELAY_SECONDS = 1.0


def run(args: list[str]) -> tuple[bool, str]:
    proc = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=False)
    return proc.returncode == 0, (proc.stdout if proc.returncode == 0 else proc.stderr or proc.stdout).strip()


def gh_json(endpoint: str) -> tuple[bool, Any]:
    ok, output = run(["gh", "api", endpoint])
    if not ok:
        return False, output
    try:
        return True, json.loads(output)
    except json.JSONDecodeError:
        return False, "GH_NON_JSON"


def load_plan(path: Path) -> dict[str, Any]:
    return prune_plan.load_plan(path)


def verify_plan_hash(plan: dict[str, Any]) -> None:
    prune_plan.validate_plan(plan, require_complete=False)


def require_expected_plan(plan: dict[str, Any], expected_plan: str | None) -> None:
    prune_plan.validate_plan(plan, require_complete=True)
    if not expected_plan:
        raise RuntimeError("EXPECTED_PLAN_REQUIRED")
    if expected_plan != plan.get("planHash"):
        raise RuntimeError("EXPECTED_PLAN_MISMATCH")


def observe_branch_inventory(repository: str) -> dict[str, str]:
    refs: dict[str, str] = {}
    for page in range(1, 21):
        ok, payload = gh_json(f"repos/{repository}/branches?per_page=100&page={page}")
        if not ok or not isinstance(payload, list):
            raise RuntimeError("BRANCH_INVENTORY_READ_FAILED")
        for item in payload:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            commit = item.get("commit")
            sha = commit.get("sha") if isinstance(commit, dict) else None
            if isinstance(name, str) and isinstance(sha, str):
                refs[name] = sha
        if len(payload) < 100:
            return refs
    raise RuntimeError("BRANCH_INVENTORY_PAGINATION_LIMIT")


def observe_open_prs_for_branch(repository: str, branch: str) -> list[dict[str, Any]]:
    owner = repository.split("/", 1)[0]
    head = quote(f"{owner}:{branch}", safe="")
    ok, payload = gh_json(f"repos/{repository}/pulls?state=open&head={head}&per_page=100")
    if not ok or not isinstance(payload, list):
        raise RuntimeError(f"OPEN_PR_READ_FAILED:{branch}")
    return [item for item in payload if isinstance(item, dict)]


def observe_open_prs_using_branch(repository: str, branch: str) -> list[dict[str, Any]]:
    by_number: dict[int, dict[str, Any]] = {}
    for item in observe_open_prs_for_branch(repository, branch):
        number = item.get("number")
        if isinstance(number, int):
            by_number[number] = item
    base = quote(branch, safe="")
    ok, payload = gh_json(f"repos/{repository}/pulls?state=open&base={base}&per_page=100")
    if not ok or not isinstance(payload, list):
        raise RuntimeError(f"OPEN_PR_BASE_READ_FAILED:{branch}")
    for item in payload:
        if isinstance(item, dict):
            number = item.get("number")
            if isinstance(number, int):
                by_number[number] = item
    return [by_number[key] for key in sorted(by_number)]


def delete_remote_ref_if_expected(repository: str, branch: str, expected_sha: str) -> None:
    if repository != "EAKerber/MobiliPresenter":
        raise RuntimeError("DELETE_REF_REPOSITORY_INVALID")
    ref = f"refs/heads/{branch}"
    lease = f"--force-with-lease={ref}:{expected_sha}"
    ok, output = run(["git", "push", "--porcelain", lease, "origin", f":{ref}"])
    if not ok:
        raise RuntimeError(f"DELETE_REF_LEASE_FAILED:{branch}:{output}")


def delete_or_confirm_absent(
    repository: str,
    branch: str,
    expected_sha: str,
    expected_after: dict[str, str],
) -> str:
    try:
        delete_remote_ref_if_expected(repository, branch, expected_sha)
        return "deleted"
    except RuntimeError as exc:
        observed = observe_branch_inventory(repository)
        if observed == expected_after:
            return "already-absent"
        actual_sha = observed.get(branch)
        if actual_sha is not None and actual_sha != expected_sha:
            raise RuntimeError(f"STALE_PLAN:BRANCH_HEAD_DRIFT:{branch}") from exc
        expected_before = dict(expected_after)
        expected_before[branch] = expected_sha
        if observed == expected_before:
            raise RuntimeError(f"DELETE_REF_LEASE_FAILED:{branch}") from exc
        raise RuntimeError(f"DELETE_REF_FAILED_WITH_DRIFT:{branch}") from exc


def select_candidates(plan: dict[str, Any]) -> list[dict[str, Any]]:
    prune_plan.validate_plan(plan, require_complete=True)
    return sorted(
        [entry for entry in plan["entries"] if entry["action"] == "delete-candidate"],
        key=lambda item: str(item.get("branch")),
    )


def expected_inventory_from_plan(plan: dict[str, Any]) -> dict[str, str]:
    prune_plan.validate_plan(plan, require_complete=True)
    return {entry["branch"]: entry["sha"] for entry in plan["entries"]}


def is_allowed_stale_inventory(
    observed: dict[str, str],
    expected: dict[str, str],
    deleted_this_run: dict[str, str],
) -> bool:
    for branch, sha in expected.items():
        if observed.get(branch) != sha:
            return False
    extras = set(observed) - set(expected)
    return bool(extras) and extras <= set(deleted_this_run) and all(
        observed[branch] == deleted_this_run[branch] for branch in extras
    )


def wait_for_consistent_inventory(
    repository: str,
    expected: dict[str, str],
    deleted_this_run: dict[str, str],
    *,
    context: str,
    attempts: int = READBACK_ATTEMPTS,
    delay_seconds: float = READBACK_DELAY_SECONDS,
) -> int:
    retries = 0
    for attempt in range(attempts):
        observed = observe_branch_inventory(repository)
        if observed == expected:
            return retries
        if not is_allowed_stale_inventory(observed, expected, deleted_this_run):
            raise RuntimeError(f"REF_INVENTORY_DRIFT:{context}")
        retries += 1
        if attempt + 1 < attempts:
            time.sleep(delay_seconds)
    raise RuntimeError(f"REF_READBACK_TIMEOUT:{context}")


def apply_plan(plan: dict[str, Any], expected_plan: str | None) -> dict[str, Any]:
    require_expected_plan(plan, expected_plan)
    candidates = select_candidates(plan)
    if os.environ.get(AUTH_ENV) != "1":
        raise RuntimeError("DESTRUCTIVE_AUTHORIZATION_MISSING")
    repository = plan.get("repository")
    control_branch = plan.get("controlBranch")
    control_sha = plan.get("controlSha")
    if repository != "EAKerber/MobiliPresenter" or not isinstance(control_branch, str) or not isinstance(control_sha, str):
        raise RuntimeError("PLAN_IDENTITY_INVALID")

    expected = expected_inventory_from_plan(plan)
    deleted: list[dict[str, str]] = []
    already_absent: list[dict[str, str]] = []
    deleted_this_run: dict[str, str] = {}
    readback_retries = 0

    readback_retries += wait_for_consistent_inventory(
        repository, expected, deleted_this_run, context="initial", attempts=1, delay_seconds=0
    )

    for entry in candidates:
        branch = str(entry["branch"])
        sha = str(entry["sha"])
        readback_retries += wait_for_consistent_inventory(
            repository, expected, deleted_this_run, context=f"before:{branch}"
        )
        if expected.get(control_branch) != control_sha:
            raise RuntimeError(f"STALE_PLAN:CONTROL_HEAD_DRIFT:{branch}")
        if expected.get(branch) != sha:
            raise RuntimeError(f"STALE_PLAN:BRANCH_HEAD_DRIFT:{branch}")
        if observe_open_prs_using_branch(repository, branch):
            raise RuntimeError(f"STALE_PLAN:OPEN_PR_RELATION_APPEARED:{branch}")

        expected_after = dict(expected)
        expected_after.pop(branch)
        outcome = delete_or_confirm_absent(repository, branch, sha, expected_after)
        expected = expected_after
        deleted_this_run[branch] = sha
        readback_retries += wait_for_consistent_inventory(
            repository, expected, deleted_this_run, context=f"after:{branch}"
        )
        record = {"branch": branch, "sha": sha}
        if outcome == "deleted":
            deleted.append(record)
        else:
            already_absent.append(record)

    readback_retries += wait_for_consistent_inventory(
        repository, expected, deleted_this_run, context="final"
    )
    return {
        "schemaVersion": "GitPruneApplyResult 0.3",
        "repository": repository,
        "planHash": plan.get("planHash"),
        "controlSha": control_sha,
        "deleted": deleted,
        "deletedCount": len(deleted),
        "alreadyAbsent": already_absent,
        "alreadyAbsentCount": len(already_absent),
        "concurrentDeletionObserved": bool(already_absent),
        "remainingBranchCount": len(expected),
        "readbackRetries": readback_retries,
        "readback": "PASS",
    }


def command(as_json: bool, plan_path: Path, expected_plan: str) -> int:
    try:
        plan = load_plan(plan_path)
        result = apply_plan(plan, expected_plan)
    except RuntimeError as exc:
        payload = {"ok": False, "error": str(exc)}
        print(json.dumps(payload, ensure_ascii=False) if as_json else f"BLOCKED\n{exc}")
        return ERROR_EXIT
    payload = {"ok": True, **result}
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print("GIT PRUNE APPLY 0.3")
        print(f"  deleted: {result['deletedCount']}")
        print(f"  already absent: {result['alreadyAbsentCount']}")
        print(f"  remaining branches: {result['remainingBranchCount']}")
        print(f"  readback retries: {result['readbackRetries']}")
        print(f"  planHash: {result['planHash']}")
        print("  readback: PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply one exact GitPrunePlan 0.4 with atomic expected-SHA deletion and CAS-style readback")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--plan", type=Path, required=True, help="Exact materialized GitPrunePlan 0.4")
    parser.add_argument("--expected-plan", required=True, help="Expected planHash observed before destructive execution")
    args = parser.parse_args()
    return command(args.as_json, args.plan, args.expected_plan)


if __name__ == "__main__":
    raise SystemExit(main())
