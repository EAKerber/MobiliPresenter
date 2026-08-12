#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import time
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


def _release_mine(authority, owner, transition_id: str, message: str):
    def factory():
        def planner(state, authority_now):
            return coordination.plan_release(state, owner, authority_now, transition_id, mine=True)
        return planner
    return _mutate_retry(authority, factory, message)


def main() -> int:
    run_id = _required("GITHUB_RUN_ID")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "1")
    orphan_session = f"gha-orphan:{run_id}:{attempt}"
    recovery_session = f"gha-recovery:{run_id}:{attempt}"
    orphan_owner = {
        "role": "engine",
        "session": orphan_session,
        "branch": "engine/orphan-probe",
        "pr": 910001,
    }
    recovery_owner = {
        "role": "ui",
        "session": recovery_session,
        "branch": "ui/recovery-probe",
        "pr": 910002,
    }
    orphan_resource = f"file:ops/coordination/probes/orphan-{run_id}-{attempt}.shared"
    independent_resource = f"file:ops/coordination/probes/independent-{run_id}-{attempt}.shared"
    authority = GitHubCoordinationAuthority(GhApiTransport())

    orphan_acquire = None
    independent_acquire = None
    independent_release = None
    recovery_acquire = None
    recovery_release = None
    before_expiry = None
    after_expiry = None

    try:
        def orphan_factory():
            def planner(state, authority_now):
                return coordination.plan_acquire(
                    state,
                    [orphan_resource],
                    orphan_owner,
                    "live orphan expiry probe",
                    authority_now,
                    f"orphan-acquire:{run_id}:{attempt}",
                    ttl_seconds=2,
                )
            return planner

        orphan_acquire = _mutate_retry(
            authority,
            orphan_factory,
            f"coordination: orphan acquire {run_id}/{attempt}",
        )

        def independent_factory():
            def planner(state, authority_now):
                return coordination.plan_acquire(
                    state,
                    [independent_resource],
                    recovery_owner,
                    "prove independent resource remains available",
                    authority_now,
                    f"independent-acquire:{run_id}:{attempt}",
                    ttl_seconds=30,
                )
            return planner

        independent_acquire = _mutate_retry(
            authority,
            independent_factory,
            f"coordination: independent acquire {run_id}/{attempt}",
        )
        simultaneous = authority.observe()
        active_sessions = {
            lease["owner"]["session"]
            for lease in coordination.active_leases(simultaneous.state, simultaneous.authority_now)
        }
        if orphan_session not in active_sessions or recovery_session not in active_sessions:
            raise RuntimeError("INDEPENDENT_RESOURCE_CONCURRENCY_NOT_PROVEN")

        independent_release = _release_mine(
            authority,
            recovery_owner,
            f"independent-release:{run_id}:{attempt}",
            f"coordination: independent release {run_id}/{attempt}",
        )

        before_expiry = authority.observe()
        if not any(
            lease["owner"]["session"] == orphan_session
            for lease in coordination.active_leases(before_expiry.state, before_expiry.authority_now)
        ):
            raise RuntimeError("ORPHAN_LEASE_EXPIRED_TOO_EARLY_FOR_PROBE")

        time.sleep(4)
        after_expiry = authority.observe()
        if any(
            lease["owner"]["session"] == orphan_session
            for lease in coordination.active_leases(after_expiry.state, after_expiry.authority_now)
        ):
            raise RuntimeError("ORPHAN_LEASE_DID_NOT_EXPIRE")

        def recovery_factory():
            def planner(state, authority_now):
                return coordination.plan_acquire(
                    state,
                    [orphan_resource],
                    recovery_owner,
                    "recover resource after orphan TTL expiry",
                    authority_now,
                    f"recovery-acquire:{run_id}:{attempt}",
                    ttl_seconds=30,
                )
            return planner

        recovery_acquire = _mutate_retry(
            authority,
            recovery_factory,
            f"coordination: recovery acquire {run_id}/{attempt}",
        )
        recovered = authority.observe()
        recovered_leases = [
            lease
            for lease in coordination.active_leases(recovered.state, recovered.authority_now)
            if lease["resource"] == orphan_resource
        ]
        if len(recovered_leases) != 1 or recovered_leases[0]["owner"]["session"] != recovery_session:
            raise RuntimeError("ORPHAN_RECOVERY_OWNER_MISMATCH")

        recovery_release = _release_mine(
            authority,
            recovery_owner,
            f"recovery-release:{run_id}:{attempt}",
            f"coordination: recovery release {run_id}/{attempt}",
        )
    finally:
        final = authority.observe()
        active = coordination.active_leases(final.state, final.authority_now)
        sessions = {lease["owner"]["session"] for lease in active}
        if recovery_session in sessions:
            try:
                _release_mine(
                    authority,
                    recovery_owner,
                    f"recovery-cleanup:{run_id}:{attempt}",
                    f"coordination: recovery cleanup {run_id}/{attempt}",
                )
            except (CoordinationRemoteError, coordination.CoordinationError):
                pass
        refreshed = authority.observe()
        active = coordination.active_leases(refreshed.state, refreshed.authority_now)
        if orphan_session in {lease["owner"]["session"] for lease in active}:
            try:
                _release_mine(
                    authority,
                    orphan_owner,
                    f"orphan-cleanup:{run_id}:{attempt}",
                    f"coordination: orphan cleanup {run_id}/{attempt}",
                )
            except (CoordinationRemoteError, coordination.CoordinationError):
                pass

    final = authority.observe()
    remaining = [
        lease
        for lease in coordination.active_leases(final.state, final.authority_now)
        if lease["owner"]["session"] in {orphan_session, recovery_session}
    ]
    if remaining:
        raise RuntimeError("RECOVERY_PROBE_LEASE_LEFT_ACTIVE")
    if orphan_acquire is None or independent_acquire is None or independent_release is None:
        raise RuntimeError("RECOVERY_PROBE_INCOMPLETE")
    if recovery_acquire is None or recovery_release is None or before_expiry is None or after_expiry is None:
        raise RuntimeError("ORPHAN_RECOVERY_NOT_COMPLETED")

    evidence = {
        "schemaVersion": "CoordinationRecoveryProbe 0.1",
        "runId": run_id,
        "runAttempt": attempt,
        "orphanOwner": orphan_owner,
        "recoveryOwner": recovery_owner,
        "orphanResource": orphan_resource,
        "independentResource": independent_resource,
        "orphanAcquireHead": orphan_acquire.after_sha,
        "independentAcquireHead": independent_acquire.after_sha,
        "independentReleaseHead": independent_release.after_sha,
        "authorityNowBeforeExpiry": before_expiry.authority_now.isoformat(),
        "authorityNowAfterExpiry": after_expiry.authority_now.isoformat(),
        "recoveryAcquireHead": recovery_acquire.after_sha,
        "recoveryReleaseHead": recovery_release.after_sha,
        "independentResourceAvailableWhileOrphanHeld": True,
        "orphanExpiredWithoutRelease": True,
        "reacquiredAfterExpiry": True,
        "leaseLeftActive": False,
    }
    output = Path(os.environ.get("COORDINATION_RECOVERY_PROBE_OUTPUT", "/tmp/coordination-recovery-probe.json"))
    output.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
