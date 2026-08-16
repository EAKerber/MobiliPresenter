#!/usr/bin/env python3
"""CAS-style destructive executor for one exact GitPrunePlan 0.3.

The planner remains the sole classifier. This executor may delete only entries
already classified as delete-candidate + autoDeleteEligible by one explicit,
materialized plan whose hash is supplied separately as expected-plan.

It fails closed on plan mismatch, incomplete observations, repository-wide ref
drift, control-head drift, open PRs, per-ref SHA mismatch, or failed readback.
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
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"PLAN_FILE_MISSING:{path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"PLAN_JSON_INVALID:{path}") from exc
    if not isinstance(value, dict):
        raise RuntimeError("PLAN_ROOT_INVALID")
    return value


def verify_plan_hash(plan: dict[str, Any]) -> None:
    observed = plan.get("planHash")
    if not isinstance(observed, str):
        raise RuntimeError("PLAN_HASH_MISSING")
    body = {key: value for key, value in plan.items() if key != "planHash"}
    expected = prune_plan.stable_hash(body)
    if observed != expected:
        raise RuntimeError("PLAN_HASH_MISMATCH")


def require_expected_plan(plan: dict[str, Any], expected_plan: str | None) -> None:
    verify_plan_hash(plan)
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


def delete_remote_ref(repository: str, branch: str) -> None:
    endpoint = f"repos/{repository}/git/refs/heads/{quote(branch, safe='/')}"
    ok, output = run(["gh", "api", "--method", "DELETE", endpoint])
    if not ok:
        raise RuntimeError(f"DELETE_REF_FAILED:{branch}:{output}")


def select_candidates(plan: dict[str, Any]) -> list[dict[str, Any]]:
    verify_plan_hash(plan)
    if plan.get("schemaVersion") != "GitPrunePlan 0.3":
        raise RuntimeError("PLAN_SCHEMA_UNSUPPORTED")
    observations = plan.get("observations")
    if not isinstance(observations, dict) or observations.get("complete") is not True:
        raise RuntimeError("PLAN_OBSERVATION_INCOMPLETE")
    if not all(
        observations.get(key) is True
        for key in ("branchInventoryComplete", "prHistoryComplete", "ancestryComplete")
    ):
        raise RuntimeError("PLAN_OBSERVATION_INCOMPLETE")
    execution = plan.get("execution")
    if not isinstance(execution, dict) or not all(
        execution.get(key) is True
        for key in ("executorAvailable", "requiresPlanFile", "requiresExpectedPlan", "requiresExplicitAuthorization")
    ):
        raise RuntimeError("PLAN_EXECUTION_CONTRACT_INVALID")
    entries = plan.get("entries")
    if not isinstance(entries, list):
        raise RuntimeError("PLAN_ENTRIES_INVALID")
    result = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if entry.get("action") == "delete-candidate" and entry.get("autoDeleteEligible") is True:
            if entry.get("protections"):
                raise RuntimeError(f"PROTECTED_CANDIDATE:{entry.get('branch')}")
            result.append(entry)
    return sorted(result, key=lambda item: str(item.get("branch")))


def expected_inventory_from_plan(plan: dict[str, Any]) -> dict[str, str]:
    entries = plan.get("entries")
    if not isinstance(entries, list):
        raise RuntimeError("PLAN_ENTRIES_INVALID")
    result: dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        branch, sha = entry.get("branch"), entry.get("sha")
        if not isinstance(branch, str) or not isinstance(sha, str):
            raise RuntimeError("PLAN_REF_INVALID")
        result[branch] = sha
    return result


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
        if observe_open_prs_for_branch(repository, branch):
            raise RuntimeError(f"STALE_PLAN:OPEN_PR_APPEARED:{branch}")

        delete_remote_ref(repository, branch)
        expected.pop(branch)
        deleted_this_run[branch] = sha
        readback_retries += wait_for_consistent_inventory(
            repository, expected, deleted_this_run, context=f"after:{branch}"
        )
        deleted.append({"branch": branch, "sha": sha})

    readback_retries += wait_for_consistent_inventory(
        repository, expected, deleted_this_run, context="final"
    )
    return {
        "schemaVersion": "GitPruneApplyResult 0.2",
        "repository": repository,
        "planHash": plan.get("planHash"),
        "controlSha": control_sha,
        "deleted": deleted,
        "deletedCount": len(deleted),
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
        print("GIT PRUNE APPLY 0.2")
        print(f"  deleted: {result['deletedCount']}")
        print(f"  remaining branches: {result['remainingBranchCount']}")
        print(f"  readback retries: {result['readbackRetries']}")
        print(f"  planHash: {result['planHash']}")
        print("  readback: PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply one exact GitPrunePlan 0.3 with CAS-style readback")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--plan", type=Path, required=True, help="Exact materialized GitPrunePlan 0.3")
    parser.add_argument("--expected-plan", required=True, help="Expected planHash observed before destructive execution")
    args = parser.parse_args()
    return command(args.as_json, args.plan, args.expected_plan)


if __name__ == "__main__":
    raise SystemExit(main())
