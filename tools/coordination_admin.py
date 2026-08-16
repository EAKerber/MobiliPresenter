#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import coordination  # noqa: E402
from tools.coordination_remote import (  # noqa: E402
    AppliedTransition,
    CoordinationRemoteError,
    GhApiTransport,
    GitHubCoordinationAuthority,
)

ERROR_EXIT = 2


def apply_break_glass(
    authority: GitHubCoordinationAuthority,
    *,
    expected_revision: str,
    admin_owner: dict[str, Any],
    resources: list[str],
    reason: str,
    transition_id: str,
) -> AppliedTransition:
    def planner(state: dict[str, Any], authority_now: datetime) -> tuple[dict[str, Any], dict[str, Any]]:
        return coordination.plan_break_glass(
            state,
            admin_owner=admin_owner,
            resources=resources,
            reason=reason,
            now=authority_now,
            transition_id=transition_id,
            expected_revision=expected_revision,
        )

    try:
        return authority.mutate(
            planner,
            message=f"coordination: break-glass {transition_id}",
            expected_revision=expected_revision,
        )
    except CoordinationRemoteError as exc:
        if exc.code == "COORDINATION_REF_DRIFT":
            raise CoordinationRemoteError(
                "COORDINATION_EXPECTED_REVISION_MISMATCH",
                "authority changed during break-glass transaction",
            ) from exc
        raise

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="coordination-admin", description="Experimental coordination break-glass")
    parser.add_argument("resources", nargs="+")
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--role", required=True)
    parser.add_argument("--session", required=True)
    parser.add_argument("--branch")
    parser.add_argument("--pr", type=int)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--transition-id", required=True)
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    owner = {"role": args.role, "session": args.session, "branch": args.branch, "pr": args.pr}
    authority = GitHubCoordinationAuthority(GhApiTransport())
    try:
        result = apply_break_glass(
            authority,
            expected_revision=args.expected_revision,
            admin_owner=owner,
            resources=args.resources,
            reason=args.reason,
            transition_id=args.transition_id,
        )
        payload = {
            "ok": True,
            "action": "break-glass",
            "beforeSha": result.before_sha,
            "afterSha": result.after_sha,
            "authorityNow": result.authority_now.isoformat(),
            "event": result.event,
        }
        print(json.dumps(payload, indent=2 if args.as_json else None, ensure_ascii=False))
        return 0
    except (coordination.CoordinationError, CoordinationRemoteError) as exc:
        payload = {
            "ok": False,
            "error": getattr(exc, "code", "COORDINATION_ADMIN_ERROR"),
            "detail": getattr(exc, "detail", str(exc)),
        }
        print(json.dumps(payload, indent=2 if args.as_json else None, ensure_ascii=False))
        return ERROR_EXIT


if __name__ == "__main__":
    raise SystemExit(main())
