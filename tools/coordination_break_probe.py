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
from tools.coordination_admin import apply_break_glass  # noqa: E402
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


def _active_for(observation, session: str):
    return [
        lease
        for lease in coordination.active_leases(observation.state, observation.authority_now)
        if lease["owner"]["session"] == session
    ]


def main() -> int:
    run_id = _required("GITHUB_RUN_ID")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "1")
    target_owner = {
        "role": "engine",
        "session": f"gha-break-target:{run_id}:{attempt}",
        "branch": "engine/break-target-probe",
        "pr": 950001,
    }
    foreign_owner = {
        "role": "ui",
        "session": f"gha-break-foreign:{run_id}:{attempt}",
        "branch": "ui/break-foreign-probe",
        "pr": 950002,
    }
    admin_owner = {
        "role": "gitops",
        "session": f"gha-break-admin:{run_id}:{attempt}",
        "branch": "ops/git-ops-1.3-coordination-leases",
        "pr": 32,
    }
    target_resource = f"file:ops/coordination/probes/break-target-{run_id}-{attempt}.shared"
    foreign_resource = f"file:ops/coordination/probes/break-foreign-{run_id}-{attempt}.shared"
    authority = GitHubCoordinationAuthority(GhApiTransport())

    target_acquire = foreign_acquire = break_result = foreign_release = None
    stale_expected = None
    stale_error = None
    try:
        def acquire_factory(owner, resource, transition):
            def factory():
                def planner(state, authority_now):
                    return coordination.plan_acquire(
                        state,
                        [resource],
                        owner,
                        "live break-glass probe",
                        authority_now,
                        transition,
                        ttl_seconds=120,
                    )
                return planner
            return factory

        target_acquire = _mutate_retry(
            authority,
            acquire_factory(target_owner, target_resource, f"break-target:{run_id}:{attempt}"),
            f"coordination: break target acquire {run_id}/{attempt}",
        )
        stale_expected = target_acquire.after_sha

        foreign_acquire = _mutate_retry(
            authority,
            acquire_factory(foreign_owner, foreign_resource, f"break-foreign:{run_id}:{attempt}"),
            f"coordination: break foreign acquire {run_id}/{attempt}",
        )

        try:
            apply_break_glass(
                authority,
                expected_revision=stale_expected,
                admin_owner=admin_owner,
                resources=[target_resource],
                reason="prove stale expected revision is rejected",
                transition_id=f"break-stale:{run_id}:{attempt}",
            )
        except CoordinationRemoteError as exc:
            stale_error = exc.code
        else:
            raise RuntimeError("BREAK_GLASS_STALE_REVISION_WAS_ACCEPTED")
        if stale_error != "COORDINATION_EXPECTED_REVISION_MISMATCH":
            raise RuntimeError(f"BREAK_GLASS_WRONG_STALE_ERROR:{stale_error}")

        after_stale = authority.observe()
        if not _active_for(after_stale, target_owner["session"]):
            raise RuntimeError("BREAK_GLASS_STALE_ATTEMPT_REMOVED_TARGET")
        if not _active_for(after_stale, foreign_owner["session"]):
            raise RuntimeError("BREAK_GLASS_STALE_ATTEMPT_REMOVED_FOREIGN")

        current_expected = after_stale.head_sha
        break_result = apply_break_glass(
            authority,
            expected_revision=current_expected,
            admin_owner=admin_owner,
            resources=[target_resource],
            reason="synthetic emergency break-glass acceptance probe",
            transition_id=f"break-valid:{run_id}:{attempt}",
        )
        after_break = authority.observe()
        if _active_for(after_break, target_owner["session"]):
            raise RuntimeError("BREAK_GLASS_TARGET_STILL_ACTIVE")
        if not _active_for(after_break, foreign_owner["session"]):
            raise RuntimeError("BREAK_GLASS_REMOVED_FOREIGN_LEASE")
        removed = break_result.event.get("removed") or []
        if len(removed) != 1 or removed[0]["owner"]["session"] != target_owner["session"]:
            raise RuntimeError("BREAK_GLASS_AUDIT_TARGET_MISMATCH")
        if break_result.event.get("admin") != admin_owner:
            raise RuntimeError("BREAK_GLASS_AUDIT_ADMIN_MISMATCH")
        if break_result.event.get("expectedRevision") != current_expected:
            raise RuntimeError("BREAK_GLASS_AUDIT_REVISION_MISMATCH")

        def release_foreign_factory():
            def planner(state, authority_now):
                return coordination.plan_release(
                    state,
                    foreign_owner,
                    authority_now,
                    f"break-foreign-release:{run_id}:{attempt}",
                    mine=True,
                )
            return planner

        foreign_release = _mutate_retry(
            authority,
            release_foreign_factory,
            f"coordination: break foreign release {run_id}/{attempt}",
        )
    finally:
        for owner in (target_owner, foreign_owner):
            try:
                observed = authority.observe()
                if not _active_for(observed, owner["session"]):
                    continue
                def cleanup_factory(owner=owner):
                    def planner(state, authority_now):
                        return coordination.plan_release(
                            state,
                            owner,
                            authority_now,
                            f"break-probe-cleanup:{owner['session']}",
                            mine=True,
                        )
                    return planner
                _mutate_retry(
                    authority,
                    cleanup_factory,
                    f"coordination: break probe cleanup {owner['session']}",
                )
            except (CoordinationRemoteError, coordination.CoordinationError):
                pass

    final = authority.observe()
    probe_sessions = {target_owner["session"], foreign_owner["session"]}
    if any(
        lease["owner"]["session"] in probe_sessions
        for lease in coordination.active_leases(final.state, final.authority_now)
    ):
        raise RuntimeError("BREAK_GLASS_PROBE_LEASE_LEFT_ACTIVE")
    if any(item is None for item in (target_acquire, foreign_acquire, break_result, foreign_release, stale_expected)):
        raise RuntimeError("BREAK_GLASS_PROBE_INCOMPLETE")

    evidence = {
        "schemaVersion": "CoordinationBreakGlassProbe 0.1",
        "runId": run_id,
        "runAttempt": attempt,
        "targetOwner": target_owner,
        "foreignOwner": foreign_owner,
        "adminOwner": admin_owner,
        "targetResource": target_resource,
        "foreignResource": foreign_resource,
        "targetAcquireHead": target_acquire.after_sha,
        "foreignAcquireHead": foreign_acquire.after_sha,
        "staleExpectedRevision": stale_expected,
        "staleAttemptError": stale_error,
        "breakBeforeHead": break_result.before_sha,
        "breakAfterHead": break_result.after_sha,
        "breakEvent": break_result.event,
        "foreignReleaseHead": foreign_release.after_sha,
        "staleRevisionRejected": True,
        "targetRemoved": True,
        "foreignLeasePreserved": True,
        "auditComplete": True,
        "leaseLeftActive": False,
    }
    output = Path(os.environ.get("COORDINATION_BREAK_PROBE_OUTPUT", "/tmp/coordination-break-probe.json"))
    output.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
