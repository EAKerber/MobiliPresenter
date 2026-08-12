#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import coordination  # noqa: E402
from tools.coordination_remote import (  # noqa: E402
    CoordinationRemoteError,
    GhApiTransport,
    GitHubCoordinationAuthority,
)


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"ENV_REQUIRED:{name}")
    return value


def _mutate_with_drift_retry(
    authority: GitHubCoordinationAuthority,
    planner_factory: Callable[[], Callable[[dict[str, Any], Any], tuple[dict[str, Any], dict[str, Any]]]],
    *,
    message: str,
    attempts: int = 3,
):
    last_error: CoordinationRemoteError | None = None
    for _ in range(attempts):
        try:
            return authority.mutate(planner_factory(), message=message)
        except CoordinationRemoteError as exc:
            last_error = exc
            if exc.code != "COORDINATION_REF_DRIFT":
                raise
    assert last_error is not None
    raise last_error


def main() -> int:
    run_id = _required_env("GITHUB_RUN_ID")
    run_attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "1")
    branch = _required_env("GITHUB_HEAD_REF")
    pr_text = _required_env("PR_NUMBER")
    try:
        pr_number = int(pr_text)
    except ValueError as exc:
        raise RuntimeError("PR_NUMBER_INVALID") from exc

    session = f"gha:{run_id}:{run_attempt}"
    owner = {"role": "gitops", "session": session, "branch": branch, "pr": pr_number}
    resource = f"file:ops/coordination/probes/gha-{run_id}-{run_attempt}.shared"
    authority = GitHubCoordinationAuthority(GhApiTransport())

    initial = authority.observe()
    acquired = None
    released = None
    try:
        def acquire_factory():
            def planner(state, authority_now):
                return coordination.plan_acquire(
                    state,
                    [resource],
                    owner,
                    "GitHub Actions live adapter probe",
                    authority_now,
                    f"gha-acquire:{run_id}:{run_attempt}",
                    ttl_seconds=300,
                )
            return planner

        acquired = _mutate_with_drift_retry(
            authority,
            acquire_factory,
            message=f"coordination: GHA adapter acquire {run_id}/{run_attempt}",
        )

        acquired_observation = authority.observe()
        allowed, held = coordination.can_write(acquired_observation.state, resource, owner, acquired_observation.authority_now)
        if not allowed or held is None:
            raise RuntimeError("LIVE_PROBE_WRITE_GUARD_FAILED")
        if held["owner"]["session"] != session:
            raise RuntimeError("LIVE_PROBE_OWNER_MISMATCH")
    finally:
        if acquired is not None:
            def release_factory():
                def planner(state, authority_now):
                    return coordination.plan_release(
                        state,
                        owner,
                        authority_now,
                        f"gha-release:{run_id}:{run_attempt}",
                        mine=True,
                    )
                return planner

            released = _mutate_with_drift_retry(
                authority,
                release_factory,
                message=f"coordination: GHA adapter release {run_id}/{run_attempt}",
            )

    final = authority.observe()
    mine = [
        lease
        for lease in coordination.active_leases(final.state, final.authority_now)
        if lease["owner"]["session"] == session
    ]
    if mine:
        raise RuntimeError("LIVE_PROBE_LEASE_LEFT_ACTIVE")

    evidence = {
        "schemaVersion": "CoordinationLiveProbe 0.1",
        "runId": run_id,
        "runAttempt": run_attempt,
        "owner": owner,
        "resource": resource,
        "initialHead": initial.head_sha,
        "acquireHead": acquired.after_sha if acquired else None,
        "releaseHead": released.after_sha if released else None,
        "finalHead": final.head_sha,
        "authorityNowInitial": initial.authority_now.isoformat(),
        "authorityNowFinal": final.authority_now.isoformat(),
        "leaseLeftActive": False,
    }
    output = Path(os.environ.get("COORDINATION_PROBE_OUTPUT", "/tmp/coordination-live-probe.json"))
    output.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
