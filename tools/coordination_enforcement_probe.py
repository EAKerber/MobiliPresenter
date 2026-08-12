#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import coordination  # noqa: E402
from tools.coordination_remote import CoordinationRemoteError, GhApiTransport, GitHubCoordinationAuthority  # noqa: E402


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"ENV_REQUIRED:{name}")
    return value


def _mutate_retry(authority, planner_factory, message: str, attempts: int = 3):
    last = None
    for _ in range(attempts):
        try:
            return authority.mutate(planner_factory(), message=message)
        except CoordinationRemoteError as exc:
            last = exc
            if exc.code != "COORDINATION_REF_DRIFT":
                raise
    assert last is not None
    raise last


def _run_gate(file_path: str, branch: str, pr: int):
    proc = subprocess.run(
        [
            sys.executable,
            "tools/coordination_ci.py",
            "--files",
            file_path,
            "--head-branch",
            branch,
            "--pr",
            str(pr),
            "--json",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=os.environ.copy(),
    )
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"CI_GATE_NON_JSON:{proc.stdout}:{proc.stderr}") from exc
    return proc.returncode, payload


def main() -> int:
    run_id = _required("GITHUB_RUN_ID")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "1")
    session = f"gha-ci-enforcement:{run_id}:{attempt}"
    foreign_branch = "engine/enforcement-probe"
    foreign_pr = 900001
    bypass_branch = "ui/enforcement-bypass"
    bypass_pr = 900002
    file_path = f"ops/coordination/probes/ci-bypass-{run_id}-{attempt}.shared"
    resource = f"file:{file_path}"
    unrelated = f"ops/coordination/probes/ci-unrelated-{run_id}-{attempt}.shared"
    owner = {
        "role": "engine",
        "session": session,
        "branch": foreign_branch,
        "pr": foreign_pr,
    }
    authority = GitHubCoordinationAuthority(GhApiTransport())
    acquired = None
    released = None
    blocked_payload = None
    matching_payload = None
    unrelated_payload = None

    try:
        def acquire_factory():
            def planner(state, authority_now):
                return coordination.plan_acquire(
                    state,
                    [resource],
                    owner,
                    "live CI ownership violation probe",
                    authority_now,
                    f"ci-probe-acquire:{run_id}:{attempt}",
                    ttl_seconds=300,
                )
            return planner

        acquired = _mutate_retry(
            authority,
            acquire_factory,
            f"coordination: CI enforcement acquire {run_id}/{attempt}",
        )

        blocked_code, blocked_payload = _run_gate(file_path, bypass_branch, bypass_pr)
        if blocked_code != 2 or blocked_payload.get("error") != "LOCK_OWNERSHIP_VIOLATION":
            raise RuntimeError(f"CI_BYPASS_NOT_BLOCKED:{blocked_code}:{blocked_payload}")

        matching_code, matching_payload = _run_gate(file_path, foreign_branch, foreign_pr)
        if matching_code != 0 or not matching_payload.get("ok"):
            raise RuntimeError(f"CI_OWNER_NOT_ALLOWED:{matching_code}:{matching_payload}")

        unrelated_code, unrelated_payload = _run_gate(unrelated, bypass_branch, bypass_pr)
        if unrelated_code != 0 or not unrelated_payload.get("ok"):
            raise RuntimeError(f"CI_UNRELATED_RESOURCE_BLOCKED:{unrelated_code}:{unrelated_payload}")
    finally:
        if acquired is not None:
            def release_factory():
                def planner(state, authority_now):
                    return coordination.plan_release(
                        state,
                        owner,
                        authority_now,
                        f"ci-probe-release:{run_id}:{attempt}",
                        mine=True,
                    )
                return planner

            released = _mutate_retry(
                authority,
                release_factory,
                f"coordination: CI enforcement release {run_id}/{attempt}",
            )

    final = authority.observe()
    remaining = [
        lease
        for lease in coordination.active_leases(final.state, final.authority_now)
        if lease["owner"]["session"] == session
    ]
    if remaining:
        raise RuntimeError("CI_PROBE_LEASE_LEFT_ACTIVE")

    evidence = {
        "schemaVersion": "CoordinationCiProbe 0.1",
        "runId": run_id,
        "runAttempt": attempt,
        "resource": resource,
        "owner": owner,
        "bypassIdentity": {"branch": bypass_branch, "pr": bypass_pr},
        "acquireHead": acquired.after_sha if acquired else None,
        "releaseHead": released.after_sha if released else None,
        "blockedResult": blocked_payload,
        "matchingOwnerResult": matching_payload,
        "unrelatedResult": unrelated_payload,
        "leaseLeftActive": False,
    }
    output = Path(os.environ.get("COORDINATION_CI_PROBE_OUTPUT", "/tmp/coordination-ci-probe.json"))
    output.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
