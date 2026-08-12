#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import sys
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


def plan_break_glass(
    state: dict[str, Any],
    *,
    admin_owner: dict[str, Any],
    resources: list[str],
    reason: str,
    now,
    transition_id: str,
    expected_revision: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    coordination.validate_state(state)
    admin = coordination.validate_owner(admin_owner)
    if admin["role"] != "gitops":
        raise coordination.CoordinationError("BREAK_GLASS_FORBIDDEN", "break-glass requires role gitops")
    if not isinstance(reason, str) or not reason.strip():
        raise coordination.CoordinationError("REASON_INVALID", "break-glass requires a reason")
    if not isinstance(transition_id, str) or not transition_id.strip():
        raise coordination.CoordinationError("TRANSITION_ID_INVALID", "transition_id must be non-empty")
    if not isinstance(expected_revision, str) or len(expected_revision) != 40:
        raise coordination.CoordinationError("EXPECTED_REVISION_INVALID", "expected revision must be a commit SHA")

    targets = coordination.normalize_resources(resources)
    if not targets:
        raise coordination.CoordinationError("RESOURCE_INVALID", "break-glass requires at least one exact resource")
    candidate = coordination.compact_expired(state, now)
    target_set = set(targets)
    removed: list[dict[str, Any]] = []
    kept: list[dict[str, Any]] = []
    for lease in candidate["leases"]:
        if lease["resource"] in target_set:
            removed.append(copy.deepcopy(lease))
        else:
            kept.append(lease)
    if not removed:
        raise coordination.CoordinationError("BREAK_GLASS_TARGET_NOT_FOUND", "no active lease matches the exact resource set")
    candidate["leases"] = kept
    coordination.validate_state(candidate)
    event = {
        "action": "break-glass",
        "transitionId": transition_id.strip(),
        "at": coordination._format_utc(coordination._parse_utc(now)),
        "expectedRevision": expected_revision,
        "admin": admin,
        "reason": reason.strip(),
        "resources": targets,
        "removed": [
            {
                "leaseId": lease["leaseId"],
                "resource": lease["resource"],
                "owner": copy.deepcopy(lease["owner"]),
                "expiresAt": lease["expiresAt"],
            }
            for lease in sorted(removed, key=lambda item: item["leaseId"])
        ],
    }
    return candidate, event


def apply_break_glass(
    authority: GitHubCoordinationAuthority,
    *,
    expected_revision: str,
    admin_owner: dict[str, Any],
    resources: list[str],
    reason: str,
    transition_id: str,
) -> AppliedTransition:
    observed = authority.observe()
    if observed.head_sha != expected_revision:
        raise CoordinationRemoteError(
            "COORDINATION_EXPECTED_REVISION_MISMATCH",
            f"expected {expected_revision}, observed {observed.head_sha}",
        )

    candidate, event = plan_break_glass(
        copy.deepcopy(observed.state),
        admin_owner=admin_owner,
        resources=resources,
        reason=reason,
        now=observed.authority_now,
        transition_id=transition_id,
        expected_revision=expected_revision,
    )
    candidate["revision"] = observed.head_sha
    coordination.validate_state(candidate)
    encoded = json.dumps(candidate, indent=2, ensure_ascii=False) + "\n"
    blob_sha = authority._create_blob(encoded)
    tree_sha = authority._create_tree(observed.tree_sha, blob_sha)
    commit_sha = authority._create_commit(
        observed.head_sha,
        tree_sha,
        f"coordination: break-glass {transition_id}",
        observed.authority_now,
    )
    try:
        authority._advance_ref(commit_sha, observed.head_sha)
    except CoordinationRemoteError as exc:
        if exc.code == "COORDINATION_REF_DRIFT":
            raise CoordinationRemoteError(
                "COORDINATION_EXPECTED_REVISION_MISMATCH",
                "authority changed during break-glass transaction",
            ) from exc
        raise
    authority._verify_published_transition(commit_sha, candidate)
    return AppliedTransition(
        before_sha=observed.head_sha,
        after_sha=commit_sha,
        authority_now=observed.authority_now,
        state=copy.deepcopy(candidate),
        event=copy.deepcopy(event),
    )


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
