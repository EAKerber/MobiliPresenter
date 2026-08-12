#!/usr/bin/env python3
from __future__ import annotations

import argparse
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

ROLE_IDENTITIES = {
    "ui": {"branch": "ui/promotional-detail-v0.2", "pr": 27},
    "engine": {"branch": "engine/technical-presentation-fidelity-v0.1", "pr": None},
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="coordination-contender", description="Parallel UI/Engine lease contender probe")
    parser.add_argument("--role", required=True, choices=("ui", "engine"))
    parser.add_argument("--output", required=True)
    return parser


def _find_shared_winner(authority, resource: str, own_session: str, attempts: int = 8):
    last = None
    for attempt in range(attempts):
        observed = authority.observe()
        active = [
            lease
            for lease in coordination.active_leases(observed.state, observed.authority_now)
            if lease["resource"] == resource
        ]
        if len(active) == 1 and active[0]["owner"]["session"] != own_session:
            return observed, active[0]
        last = (observed, active)
        if attempt + 1 < attempts:
            time.sleep(0.25)
    return last[0], None if last is None else (last[1][0] if len(last[1]) == 1 else None)


def main() -> int:
    args = build_parser().parse_args()
    run_id = os.environ.get("GITHUB_RUN_ID")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "1")
    if not run_id:
        raise RuntimeError("ENV_REQUIRED:GITHUB_RUN_ID")

    identity = ROLE_IDENTITIES[args.role]
    session = f"gha-parallel-{args.role}:{run_id}:{attempt}"
    owner = {
        "role": args.role,
        "session": session,
        "branch": identity["branch"],
        "pr": identity["pr"],
    }
    resource = f"file:ops/coordination/probes/parallel-shared-{run_id}-{attempt}.shared"
    authority = GitHubCoordinationAuthority(GhApiTransport())
    result = None
    winner = False
    loss_code = None
    winning_lease = None
    observed_head_after_loss = None

    def planner(state, authority_now):
        return coordination.plan_acquire(
            state,
            [resource],
            owner,
            "parallel UI x Engine single-winner probe",
            authority_now,
            f"parallel-acquire:{args.role}:{run_id}:{attempt}",
            ttl_seconds=300,
        )

    try:
        result = authority.mutate(
            planner,
            message=f"coordination: parallel contender {args.role} {run_id}/{attempt}",
        )
        winner = True
        winning_lease = next(
            lease
            for lease in result.state["leases"]
            if lease["resource"] == resource and lease["owner"]["session"] == session
        )
    except coordination.CoordinationError as exc:
        if exc.code != "LEASE_CONFLICT":
            raise
        loss_code = exc.code
        observed, winning_lease = _find_shared_winner(authority, resource, session)
        observed_head_after_loss = observed.head_sha
        if winning_lease is None:
            raise RuntimeError("PARALLEL_LOSER_COULD_NOT_OBSERVE_WINNER") from exc
    except CoordinationRemoteError as exc:
        if exc.code != "COORDINATION_REF_DRIFT":
            raise
        loss_code = exc.code
        observed, winning_lease = _find_shared_winner(authority, resource, session)
        observed_head_after_loss = observed.head_sha
        if winning_lease is None:
            raise RuntimeError("PARALLEL_REF_DRIFT_WITHOUT_OBSERVABLE_WINNER") from exc

    if winner and result is None:
        raise RuntimeError("PARALLEL_WINNER_RESULT_MISSING")
    if not winner and winning_lease is not None and winning_lease["owner"]["session"] == session:
        raise RuntimeError("PARALLEL_LOSER_OBSERVED_SELF_AS_WINNER")

    evidence = {
        "schemaVersion": "CoordinationParallelContender 0.1",
        "runId": run_id,
        "runAttempt": attempt,
        "role": args.role,
        "owner": owner,
        "resource": resource,
        "winner": winner,
        "acquireHead": result.after_sha if result else None,
        "lossCode": loss_code,
        "observedHeadAfterLoss": observed_head_after_loss,
        "observedWinner": {
            "leaseId": winning_lease["leaseId"],
            "owner": winning_lease["owner"],
            "expiresAt": winning_lease["expiresAt"],
        } if winning_lease else None,
        "leaseIntentionallyHeldForReconciliation": winner,
    }
    output = Path(args.output)
    output.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
