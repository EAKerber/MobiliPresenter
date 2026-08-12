#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
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


def _lease_for_session(observation, session: str):
    return next(
        (
            lease
            for lease in coordination.active_leases(observation.state, observation.authority_now)
            if lease["owner"]["session"] == session
        ),
        None,
    )


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def main() -> int:
    run_id = _required("GITHUB_RUN_ID")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "1")
    holder_session = f"gha-holder:{run_id}:{attempt}"
    peer_session = f"gha-peer:{run_id}:{attempt}"
    orphan_session = f"gha-orphan:{run_id}:{attempt}"
    recovery_session = f"gha-recovery:{run_id}:{attempt}"

    holder_owner = {
        "role": "engine",
        "session": holder_session,
        "branch": "engine/independent-probe",
        "pr": 910001,
    }
    peer_owner = {
        "role": "ui",
        "session": peer_session,
        "branch": "ui/independent-probe",
        "pr": 910002,
    }
    orphan_owner = {
        "role": "engine",
        "session": orphan_session,
        "branch": "engine/orphan-probe",
        "pr": 910003,
    }
    recovery_owner = {
        "role": "ui",
        "session": recovery_session,
        "branch": "ui/recovery-probe",
        "pr": 910004,
    }

    held_resource = f"file:ops/coordination/probes/held-{run_id}-{attempt}.shared"
    independent_resource = f"file:ops/coordination/probes/independent-{run_id}-{attempt}.shared"
    orphan_resource = f"file:ops/coordination/probes/orphan-{run_id}-{attempt}.shared"
    authority = GitHubCoordinationAuthority(GhApiTransport())

    holder_acquire = None
    peer_acquire = None
    peer_release = None
    holder_release = None
    orphan_acquire = None
    recovery_acquire = None
    recovery_release = None
    before_expiry = None
    after_expiry = None
    waited_seconds = None

    all_owners = [holder_owner, peer_owner, orphan_owner, recovery_owner]
    try:
        # Probe A: a foreign lease on one resource must not block an independent resource.
        def holder_factory():
            def planner(state, authority_now):
                return coordination.plan_acquire(
                    state,
                    [held_resource],
                    holder_owner,
                    "hold one resource while peer acquires another",
                    authority_now,
                    f"holder-acquire:{run_id}:{attempt}",
                    ttl_seconds=120,
                )
            return planner

        holder_acquire = _mutate_retry(
            authority,
            holder_factory,
            f"coordination: holder acquire {run_id}/{attempt}",
        )

        def peer_factory():
            def planner(state, authority_now):
                return coordination.plan_acquire(
                    state,
                    [independent_resource],
                    peer_owner,
                    "prove independent resource remains available",
                    authority_now,
                    f"peer-acquire:{run_id}:{attempt}",
                    ttl_seconds=120,
                )
            return planner

        peer_acquire = _mutate_retry(
            authority,
            peer_factory,
            f"coordination: peer acquire {run_id}/{attempt}",
        )
        simultaneous = authority.observe()
        active_sessions = {
            lease["owner"]["session"]
            for lease in coordination.active_leases(simultaneous.state, simultaneous.authority_now)
        }
        if holder_session not in active_sessions or peer_session not in active_sessions:
            raise RuntimeError("INDEPENDENT_RESOURCE_CONCURRENCY_NOT_PROVEN")

        peer_release = _release_mine(
            authority,
            peer_owner,
            f"peer-release:{run_id}:{attempt}",
            f"coordination: peer release {run_id}/{attempt}",
        )
        holder_release = _release_mine(
            authority,
            holder_owner,
            f"holder-release:{run_id}:{attempt}",
            f"coordination: holder release {run_id}/{attempt}",
        )

        # Probe B: a separate short lease is deliberately left unreleased and must
        # cease blocking solely because GitHub's remote clock passes expiresAt.
        def orphan_factory():
            def planner(state, authority_now):
                return coordination.plan_acquire(
                    state,
                    [orphan_resource],
                    orphan_owner,
                    "live orphan expiry probe",
                    authority_now,
                    f"orphan-acquire:{run_id}:{attempt}",
                    ttl_seconds=20,
                )
            return planner

        orphan_acquire = _mutate_retry(
            authority,
            orphan_factory,
            f"coordination: orphan acquire {run_id}/{attempt}",
        )
        before_expiry = authority.observe()
        orphan_lease = _lease_for_session(before_expiry, orphan_session)
        if orphan_lease is None:
            raise RuntimeError("ORPHAN_LEASE_NOT_ACTIVE_AFTER_ACQUIRE")

        expires_at = _parse_utc(orphan_lease["expiresAt"])
        remaining = (expires_at - before_expiry.authority_now).total_seconds()
        if remaining <= 0:
            raise RuntimeError("ORPHAN_LEASE_EXPIRED_TOO_EARLY_FOR_PROBE")
        waited_seconds = min(remaining + 2.0, 25.0)
        if waited_seconds < remaining + 1.0:
            raise RuntimeError("ORPHAN_EXPIRY_WAIT_OUT_OF_BOUNDS")
        time.sleep(waited_seconds)

        after_expiry = authority.observe()
        if _lease_for_session(after_expiry, orphan_session) is not None:
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
                    ttl_seconds=60,
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
        # Compensating cleanup only for leases that are still active. The expected
        # orphan path is not released before expiry; this block is only failure safety.
        for owner in all_owners:
            try:
                observed = authority.observe()
                if _lease_for_session(observed, owner["session"]) is not None:
                    _release_mine(
                        authority,
                        owner,
                        f"probe-cleanup:{owner['session']}:{run_id}:{attempt}",
                        f"coordination: recovery probe cleanup {owner['session']}",
                    )
            except (CoordinationRemoteError, coordination.CoordinationError):
                pass

    final = authority.observe()
    probe_sessions = {owner["session"] for owner in all_owners}
    remaining_probe_leases = [
        lease
        for lease in coordination.active_leases(final.state, final.authority_now)
        if lease["owner"]["session"] in probe_sessions
    ]
    if remaining_probe_leases:
        raise RuntimeError("RECOVERY_PROBE_LEASE_LEFT_ACTIVE")
    required = [
        holder_acquire,
        peer_acquire,
        peer_release,
        holder_release,
        orphan_acquire,
        recovery_acquire,
        recovery_release,
        before_expiry,
        after_expiry,
    ]
    if any(item is None for item in required):
        raise RuntimeError("RECOVERY_PROBE_INCOMPLETE")

    evidence = {
        "schemaVersion": "CoordinationRecoveryProbe 0.2",
        "runId": run_id,
        "runAttempt": attempt,
        "heldResource": held_resource,
        "independentResource": independent_resource,
        "orphanResource": orphan_resource,
        "holderOwner": holder_owner,
        "peerOwner": peer_owner,
        "orphanOwner": orphan_owner,
        "recoveryOwner": recovery_owner,
        "holderAcquireHead": holder_acquire.after_sha,
        "peerAcquireHead": peer_acquire.after_sha,
        "peerReleaseHead": peer_release.after_sha,
        "holderReleaseHead": holder_release.after_sha,
        "orphanAcquireHead": orphan_acquire.after_sha,
        "authorityNowBeforeExpiry": before_expiry.authority_now.isoformat(),
        "authorityNowAfterExpiry": after_expiry.authority_now.isoformat(),
        "waitedSeconds": waited_seconds,
        "recoveryAcquireHead": recovery_acquire.after_sha,
        "recoveryReleaseHead": recovery_release.after_sha,
        "independentResourceAvailableWhileForeignLeaseHeld": True,
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
