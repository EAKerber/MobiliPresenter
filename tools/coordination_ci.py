#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import coordination  # noqa: E402
from tools.coordination_remote import (  # noqa: E402
    CoordinationRemoteError,
    GhApiTransport,
    GitHubCoordinationAuthority,
)

ERROR_EXIT = 2


def owner_matches_pr(owner: dict[str, Any], head_branch: str, pr_number: int | None) -> bool:
    canonical = coordination.validate_owner(owner)
    if canonical["branch"] != head_branch:
        return False
    lease_pr = canonical["pr"]
    if lease_pr is None:
        return True
    return pr_number == lease_pr


def evaluate_changes(
    state: dict[str, Any],
    authority_now,
    files: list[str],
    *,
    head_branch: str,
    pr_number: int | None,
) -> dict[str, Any]:
    coordination.validate_state(state)
    if not isinstance(head_branch, str) or not head_branch:
        raise coordination.CoordinationError("CI_OWNER_INVALID", "head branch is required")
    canonical_files = sorted(set(coordination.normalize_resource(f"file:{path}") for path in files))
    active = coordination.active_leases(state, authority_now)
    violations: list[dict[str, Any]] = []

    for lease in active:
        if lease["resource"].startswith("branch:"):
            branch_resource = f"branch:{head_branch}"
            if coordination.resources_conflict(branch_resource, lease["resource"]) and not owner_matches_pr(
                lease["owner"], head_branch, pr_number
            ):
                violations.append(
                    {
                        "changed": branch_resource,
                        "held": lease["resource"],
                        "owner": lease["owner"],
                        "expiresAt": lease["expiresAt"],
                    }
                )

    for changed in canonical_files:
        for lease in active:
            if lease["resource"].startswith("branch:"):
                continue
            if not coordination.resources_conflict(changed, lease["resource"]):
                continue
            if owner_matches_pr(lease["owner"], head_branch, pr_number):
                continue
            violations.append(
                {
                    "changed": changed,
                    "held": lease["resource"],
                    "owner": lease["owner"],
                    "expiresAt": lease["expiresAt"],
                }
            )

    violations.sort(key=lambda item: (item["changed"], item["held"], item["owner"].get("session") or ""))
    return {
        "ok": not violations,
        "headBranch": head_branch,
        "prNumber": pr_number,
        "files": canonical_files,
        "activeLeaseCount": len(active),
        "violations": violations,
    }


def changed_files_from_git(base_sha: str, head_sha: str = "HEAD") -> list[str]:
    if not base_sha:
        raise coordination.CoordinationError("CI_DIFF_INVALID", "base sha is required")
    proc = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=ACMR", f"{base_sha}...{head_sha}"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise coordination.CoordinationError("CI_DIFF_UNAVAILABLE", (proc.stderr or proc.stdout).strip())
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="coordination-ci", description="Experimental lease ownership gate")
    parser.add_argument("--head-branch", required=True)
    parser.add_argument("--pr", type=int, dest="pr_number")
    parser.add_argument("--base-sha")
    parser.add_argument("--head-sha", default="HEAD")
    parser.add_argument("--files", nargs="*")
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main(argv: list[str] | None = None, *, authority_factory=GitHubCoordinationAuthority) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.files is not None:
            files = args.files
        else:
            if not args.base_sha:
                raise coordination.CoordinationError("CI_DIFF_INVALID", "provide --files or --base-sha")
            files = changed_files_from_git(args.base_sha, args.head_sha)

        if authority_factory is GitHubCoordinationAuthority:
            authority = GitHubCoordinationAuthority(GhApiTransport())
        else:
            authority = authority_factory()
        observed = authority.observe()
        payload = evaluate_changes(
            observed.state,
            observed.authority_now,
            files,
            head_branch=args.head_branch,
            pr_number=args.pr_number,
        )
        payload["authorityHead"] = observed.head_sha
        payload["authorityNow"] = observed.authority_now.isoformat()
        if not payload["ok"]:
            payload["error"] = "LOCK_OWNERSHIP_VIOLATION"
            print(json.dumps(payload, indent=2 if args.as_json else None, ensure_ascii=False))
            return ERROR_EXIT
        print(json.dumps(payload, indent=2 if args.as_json else None, ensure_ascii=False))
        return 0
    except (coordination.CoordinationError, CoordinationRemoteError) as exc:
        payload = {
            "ok": False,
            "error": getattr(exc, "code", "COORDINATION_CI_ERROR"),
            "detail": getattr(exc, "detail", str(exc)),
        }
        print(json.dumps(payload, indent=2 if args.as_json else None, ensure_ascii=False))
        return ERROR_EXIT


if __name__ == "__main__":
    raise SystemExit(main())
