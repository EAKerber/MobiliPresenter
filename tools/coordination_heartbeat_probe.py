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
    session = f"gha-heartbeat:{run_id}:{attempt}"
    owner = {
        "role": "engine",
        "session": session,
        "branch": "engine/heartbeat-probe",
        "pr": 920001,
    }
    resource = f"file:ops/coordination/probes/heartbeat-{run_id}-{attempt}.shared"
    authority = GitHubCoordinationAuthority(GhApiTransport())

    acquired = None
    renewed = None
    released = None
    first_observation = None
    renewed_observation = None
    post_original_expiry = None
    wait_before_renew = 6.0
    waited_after_renew = None

    try:
        def acquire_factory():
            def planner(state, authority_now):
                return coordination.plan_acquire(
                    state,
                    [resource],
                    owner,
                    "live heartbeat renewal probe",
                    authority_now,
                    f"heartbeat-acquire:{run_id}:{attempt}",
                    ttl_seconds=20,
                )
            return planner

        acquired = _mutate_retry(
            authority,
            acquire_factory,
            f"coordination: heartbeat acquire {run_id}/{attempt}",
        )
        first_observation = authority.observe()
        first_lease = _lease_for_session(first_observation, session)
        if first_lease is None:
            raise RuntimeError("HEARTBEAT_LEASE_NOT_ACTIVE_AFTER_ACQUIRE")
        original_expires = _parse_utc(first_lease["expiresAt"])

        time.sleep(wait_before_renew)

        def renew_factory():
            def planner(state, authority_now):
                return coordination.plan_renew_mine(
                    state,
                    owner,
                    authority_now,
                    f"heartbeat-renew:{run_id}:{attempt}",
                )
            return planner

        renewed = _mutate_retry(
            authority,
            renew_factory,
            f"coordination: heartbeat renew {run_id}/{attempt}",
        )
        renewed_observation = authority.observe()
        renewed_lease = _lease_for_session(renewed_observation, session)
        if renewed_lease is None:
            raise RuntimeError("HEARTBEAT_LEASE_NOT_ACTIVE_AFTER_RENEW")
        renewed_expires = _parse_utc(renewed_lease["expiresAt"])
        renewed_at = _parse_utc(renewed_lease["renewedAt"])
        if renewed_expires <= original_expires:
            raise RuntimeError("HEARTBEAT_DID_NOT_EXTEND_EXPIRY")
        if renewed_at <= _parse_utc(first_lease["renewedAt"]):
            raise RuntimeError("HEARTBEAT_RENEWED_AT_NOT_ADVANCED")

        remaining_until_old_expiry = (original_expires - renewed_observation.authority_now).total_seconds()
        waited_after_renew = max(0.0, remaining_until_old_expiry + 2.0)
        if waited_after_renew > 20.0:
            raise RuntimeError("HEARTBEAT_PROBE_WAIT_OUT_OF_BOUNDS")
        time.sleep(waited_after_renew)

        post_original_expiry = authority.observe()
        if post_original_expiry.authority_now <= original_expires:
            raise RuntimeError("HEARTBEAT_OLD_EXPIRY_NOT_REACHED")
        active_after_old_expiry = _lease_for_session(post_original_expiry, session)
        if active_after_old_expiry is None:
            raise RuntimeError("HEARTBEAT_RENEWED_LEASE_EXPIRED_AT_OLD_DEADLINE")
        if _parse_utc(active_after_old_expiry["expiresAt"]) != renewed_expires:
            raise RuntimeError("HEARTBEAT_RENEWED_EXPIRY_CHANGED_UNEXPECTEDLY")

        def release_factory():
            def planner(state, authority_now):
                return coordination.plan_release(
                    state,
                    owner,
                    authority_now,
                    f"heartbeat-release:{run_id}:{attempt}",
                    mine=True,
                )
            return planner

        released = _mutate_retry(
            authority,
            release_factory,
            f"coordination: heartbeat release {run_id}/{attempt}",
        )
    finally:
        try:
            final = authority.observe()
            if _lease_for_session(final, session) is not None:
                def cleanup_factory():
                    def planner(state, authority_now):
                        return coordination.plan_release(
                            state,
                            owner,
                            authority_now,
                            f"heartbeat-cleanup:{run_id}:{attempt}",
                            mine=True,
                        )
                    return planner
                _mutate_retry(
                    authority,
                    cleanup_factory,
                    f"coordination: heartbeat cleanup {run_id}/{attempt}",
                )
        except (CoordinationRemoteError, coordination.CoordinationError):
            pass

    final = authority.observe()
    if _lease_for_session(final, session) is not None:
        raise RuntimeError("HEARTBEAT_PROBE_LEASE_LEFT_ACTIVE")
    required = [acquired, renewed, released, first_observation, renewed_observation, post_original_expiry]
    if any(item is None for item in required):
        raise RuntimeError("HEARTBEAT_PROBE_INCOMPLETE")

    first_lease = next(
        lease for lease in first_observation.state["leases"] if lease["owner"]["session"] == session
    )
    renewed_lease = next(
        lease for lease in renewed_observation.state["leases"] if lease["owner"]["session"] == session
    )
    evidence = {
        "schemaVersion": "CoordinationHeartbeatProbe 0.1",
        "runId": run_id,
        "runAttempt": attempt,
        "owner": owner,
        "resource": resource,
        "acquireHead": acquired.after_sha,
        "renewHead": renewed.after_sha,
        "releaseHead": released.after_sha,
        "authorityNowAfterAcquire": first_observation.authority_now.isoformat(),
        "originalRenewedAt": first_lease["renewedAt"],
        "originalExpiresAt": first_lease["expiresAt"],
        "authorityNowAfterRenew": renewed_observation.authority_now.isoformat(),
        "renewedAt": renewed_lease["renewedAt"],
        "renewedExpiresAt": renewed_lease["expiresAt"],
        "authorityNowAfterOriginalExpiry": post_original_expiry.authority_now.isoformat(),
        "waitBeforeRenewSeconds": wait_before_renew,
        "waitAfterRenewSeconds": waited_after_renew,
        "expiryExtended": True,
        "leaseActivePastOriginalExpiry": True,
        "leaseLeftActive": False,
    }
    output = Path(os.environ.get("COORDINATION_HEARTBEAT_PROBE_OUTPUT", "/tmp/coordination-heartbeat-probe.json"))
    output.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
