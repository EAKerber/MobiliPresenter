#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import coordination  # noqa: E402
from tools.coordination_remote import CoordinationRemoteError, GhApiTransport, GitHubCoordinationAuthority  # noqa: E402

EXPECTED_LOSS_CODES = {"LEASE_CONFLICT", "COORDINATION_REF_DRIFT"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="coordination-parallel-reconcile", description="Reconcile parallel UI/Engine contender evidence")
    parser.add_argument("--ui", required=True)
    parser.add_argument("--engine", required=True)
    parser.add_argument("--output", required=True)
    return parser


def _load(path: str) -> dict:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"PARALLEL_EVIDENCE_INVALID:{path}")
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


def _release_owner(authority, owner, run_id: str, attempt: str, suffix: str):
    def factory():
        def planner(state, authority_now):
            return coordination.plan_release(
                state,
                owner,
                authority_now,
                f"parallel-release:{suffix}:{run_id}:{attempt}",
                mine=True,
            )
        return planner
    return _mutate_retry(
        authority,
        factory,
        f"coordination: parallel release {suffix} {run_id}/{attempt}",
    )


def main() -> int:
    args = build_parser().parse_args()
    ui = _load(args.ui)
    engine = _load(args.engine)
    run_id = os.environ.get("GITHUB_RUN_ID")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "1")
    if not run_id:
        raise RuntimeError("ENV_REQUIRED:GITHUB_RUN_ID")

    contenders = [ui, engine]
    if {item.get("role") for item in contenders} != {"ui", "engine"}:
        raise RuntimeError("PARALLEL_ROLES_INVALID")
    resources = {item.get("resource") for item in contenders}
    if len(resources) != 1 or None in resources:
        raise RuntimeError("PARALLEL_RESOURCE_MISMATCH")
    resource = next(iter(resources))
    winners = [item for item in contenders if item.get("winner") is True]
    losers = [item for item in contenders if item.get("winner") is False]
    if len(winners) != 1 or len(losers) != 1:
        raise RuntimeError(f"PARALLEL_SINGLE_WINNER_FAILED:winners={len(winners)}:losers={len(losers)}")
    winner = winners[0]
    loser = losers[0]
    if loser.get("lossCode") not in EXPECTED_LOSS_CODES:
        raise RuntimeError(f"PARALLEL_LOSS_CODE_UNEXPECTED:{loser.get('lossCode')}")

    authority = GitHubCoordinationAuthority(GhApiTransport())
    independent_acquire = independent_release = winner_release = None
    independent_resource = f"file:ops/coordination/probes/parallel-independent-{run_id}-{attempt}.shared"
    try:
        observed = authority.observe()
        shared = [
            lease
            for lease in coordination.active_leases(observed.state, observed.authority_now)
            if lease["resource"] == resource
        ]
        if len(shared) != 1:
            raise RuntimeError(f"PARALLEL_AUTHORITY_WINNER_COUNT:{len(shared)}")
        shared_lease = shared[0]
        if shared_lease["owner"]["session"] != winner["owner"]["session"]:
            raise RuntimeError("PARALLEL_AUTHORITY_WINNER_IDENTITY_MISMATCH")

        loser_owner = loser["owner"]
        def independent_factory():
            def planner(state, authority_now):
                return coordination.plan_acquire(
                    state,
                    [independent_resource],
                    loser_owner,
                    "parallel loser continues on independent resource",
                    authority_now,
                    f"parallel-independent:{loser['role']}:{run_id}:{attempt}",
                    ttl_seconds=120,
                )
            return planner

        independent_acquire = _mutate_retry(
            authority,
            independent_factory,
            f"coordination: parallel independent {loser['role']} {run_id}/{attempt}",
        )
        coexist = authority.observe()
        active = coordination.active_leases(coexist.state, coexist.authority_now)
        sessions = {lease["owner"]["session"] for lease in active}
        if winner["owner"]["session"] not in sessions or loser_owner["session"] not in sessions:
            raise RuntimeError("PARALLEL_INDEPENDENT_PROGRESS_NOT_OBSERVED")

        independent_release = _release_owner(
            authority,
            loser_owner,
            run_id,
            attempt,
            f"independent-{loser['role']}",
        )
        winner_release = _release_owner(
            authority,
            winner["owner"],
            run_id,
            attempt,
            f"winner-{winner['role']}",
        )
    finally:
        for contender in contenders:
            owner = contender.get("owner")
            if not isinstance(owner, dict):
                continue
            try:
                observed = authority.observe()
                if not any(
                    lease["owner"]["session"] == owner.get("session")
                    for lease in coordination.active_leases(observed.state, observed.authority_now)
                ):
                    continue
                _release_owner(
                    authority,
                    owner,
                    run_id,
                    attempt,
                    f"cleanup-{contender.get('role')}",
                )
            except (coordination.CoordinationError, CoordinationRemoteError):
                pass

    final = authority.observe()
    contender_sessions = {item["owner"]["session"] for item in contenders}
    remaining = [
        lease
        for lease in coordination.active_leases(final.state, final.authority_now)
        if lease["owner"]["session"] in contender_sessions
    ]
    if remaining:
        raise RuntimeError("PARALLEL_RECONCILIATION_LEASE_LEFT_ACTIVE")
    if any(item is None for item in (independent_acquire, independent_release, winner_release)):
        raise RuntimeError("PARALLEL_RECONCILIATION_INCOMPLETE")

    evidence = {
        "schemaVersion": "CoordinationParallelReconciliation 0.1",
        "runId": run_id,
        "runAttempt": attempt,
        "resource": resource,
        "winner": winner,
        "loser": loser,
        "exactlyOneWinner": True,
        "expectedLoserCode": loser["lossCode"],
        "independentResource": independent_resource,
        "independentAcquireHead": independent_acquire.after_sha,
        "independentReleaseHead": independent_release.after_sha,
        "winnerReleaseHead": winner_release.after_sha,
        "loserProgressedOnIndependentResourceWhileWinnerHeldShared": True,
        "authorityCleanAfterReconciliation": True,
    }
    output = Path(args.output)
    output.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
