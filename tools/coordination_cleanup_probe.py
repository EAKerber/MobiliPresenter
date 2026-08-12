#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import coordination  # noqa: E402
from tools.coordination_cleanup import plan_closed_pr_cleanup  # noqa: E402
from tools.coordination_remote import CoordinationRemoteError, GhApiTransport, GitHubCoordinationAuthority  # noqa: E402


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"ENV_REQUIRED:{name}")
    return value


def _mutate_retry(authority, planner_factory, message: str, attempts: int = 5):
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


def main() -> int:
    run_id = _required("GITHUB_RUN_ID")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "1")
    closed_pr = 930001
    closed_branch = "engine/closed-pr-probe"
    closed_owner_a = {
        "role": "engine",
        "session": f"gha-closed-a:{run_id}:{attempt}",
        "branch": closed_branch,
        "pr": closed_pr,
    }
    closed_owner_b = {
        "role": "engine",
        "session": f"gha-closed-b:{run_id}:{attempt}",
        "branch": closed_branch,
        "pr": closed_pr,
    }
    foreign_owner = {
        "role": "ui",
        "session": f"gha-foreign:{run_id}:{attempt}",
        "branch": "ui/foreign-pr-probe",
        "pr": 930002,
    }
    resource_a = f"file:ops/coordination/probes/closed-a-{run_id}-{attempt}.shared"
    resource_b = f"file:ops/coordination/probes/closed-b-{run_id}-{attempt}.shared"
    foreign_resource = f"file:ops/coordination/probes/foreign-{run_id}-{attempt}.shared"
    authority = GitHubCoordinationAuthority(GhApiTransport())

    acquired_a = acquired_b = acquired_foreign = cleanup = foreign_release = None
    try:
        def acquire_factory(owner, resource, transition_id):
            def factory():
                def planner(state, authority_now):
                    return coordination.plan_acquire(
                        state,
                        [resource],
                        owner,
                        "live closed PR cleanup probe",
                        authority_now,
                        transition_id,
                        ttl_seconds=120,
                    )
                return planner
            return factory

        acquired_a = _mutate_retry(
            authority,
            acquire_factory(closed_owner_a, resource_a, f"closed-a:{run_id}:{attempt}"),
            f"coordination: closed PR probe acquire A {run_id}/{attempt}",
        )
        acquired_b = _mutate_retry(
            authority,
            acquire_factory(closed_owner_b, resource_b, f"closed-b:{run_id}:{attempt}"),
            f"coordination: closed PR probe acquire B {run_id}/{attempt}",
        )
        acquired_foreign = _mutate_retry(
            authority,
            acquire_factory(foreign_owner, foreign_resource, f"foreign:{run_id}:{attempt}"),
            f"coordination: closed PR probe acquire foreign {run_id}/{attempt}",
        )

        before = authority.observe()
        sessions_before = {
            lease["owner"]["session"]
            for lease in coordination.active_leases(before.state, before.authority_now)
        }
        expected_before = {
            closed_owner_a["session"],
            closed_owner_b["session"],
            foreign_owner["session"],
        }
        if not expected_before.issubset(sessions_before):
            raise RuntimeError("CLOSED_PR_PROBE_SETUP_INCOMPLETE")

        def cleanup_factory():
            def planner(state, authority_now):
                return plan_closed_pr_cleanup(
                    state,
                    pr_number=closed_pr,
                    branch=closed_branch,
                    now=authority_now,
                    transition_id=f"closed-pr-cleanup:{run_id}:{attempt}",
                )
            return planner

        cleanup = _mutate_retry(
            authority,
            cleanup_factory,
            f"coordination: cleanup closed PR {closed_pr} {run_id}/{attempt}",
        )
        after = authority.observe()
        active_after = coordination.active_leases(after.state, after.authority_now)
        sessions_after = {lease["owner"]["session"] for lease in active_after}
        if closed_owner_a["session"] in sessions_after or closed_owner_b["session"] in sessions_after:
            raise RuntimeError("CLOSED_PR_CLEANUP_DID_NOT_REMOVE_TARGET")
        if foreign_owner["session"] not in sessions_after:
            raise RuntimeError("CLOSED_PR_CLEANUP_REMOVED_FOREIGN_SESSION")

        def release_foreign_factory():
            def planner(state, authority_now):
                return coordination.plan_release(
                    state,
                    foreign_owner,
                    authority_now,
                    f"foreign-release:{run_id}:{attempt}",
                    mine=True,
                )
            return planner

        foreign_release = _mutate_retry(
            authority,
            release_foreign_factory,
            f"coordination: release foreign cleanup probe {run_id}/{attempt}",
        )
    finally:
        for owner in (closed_owner_a, closed_owner_b, foreign_owner):
            try:
                observed = authority.observe()
                active = [
                    lease for lease in coordination.active_leases(observed.state, observed.authority_now)
                    if lease["owner"]["session"] == owner["session"]
                ]
                if not active:
                    continue
                def cleanup_owner_factory(owner=owner):
                    def planner(state, authority_now):
                        return coordination.plan_release(
                            state,
                            owner,
                            authority_now,
                            f"closed-pr-probe-finally:{owner['session']}",
                            mine=True,
                        )
                    return planner
                _mutate_retry(
                    authority,
                    cleanup_owner_factory,
                    f"coordination: closed PR probe finally {owner['session']}",
                )
            except (CoordinationRemoteError, coordination.CoordinationError):
                pass

    final = authority.observe()
    probe_sessions = {closed_owner_a["session"], closed_owner_b["session"], foreign_owner["session"]}
    if any(
        lease["owner"]["session"] in probe_sessions
        for lease in coordination.active_leases(final.state, final.authority_now)
    ):
        raise RuntimeError("CLOSED_PR_PROBE_LEASE_LEFT_ACTIVE")
    if any(item is None for item in (acquired_a, acquired_b, acquired_foreign, cleanup, foreign_release)):
        raise RuntimeError("CLOSED_PR_PROBE_INCOMPLETE")

    evidence = {
        "schemaVersion": "CoordinationClosedPrCleanupProbe 0.1",
        "runId": run_id,
        "runAttempt": attempt,
        "closedIdentity": {"pr": closed_pr, "branch": closed_branch},
        "closedSessions": [closed_owner_a["session"], closed_owner_b["session"]],
        "foreignOwner": foreign_owner,
        "acquireHeads": [acquired_a.after_sha, acquired_b.after_sha, acquired_foreign.after_sha],
        "cleanupHead": cleanup.after_sha,
        "cleanupEvent": cleanup.event,
        "foreignReleaseHead": foreign_release.after_sha,
        "closedSessionsRemoved": True,
        "foreignSessionPreserved": True,
        "leaseLeftActive": False,
    }
    output = Path(os.environ.get("COORDINATION_CLEANUP_PROBE_OUTPUT", "/tmp/coordination-cleanup-probe.json"))
    output.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
