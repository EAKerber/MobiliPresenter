#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, Callable, Mapping

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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lock", description="Experimental MobiliPresenter coordination leases")
    parser.add_argument("command", choices=("status", "intent", "acquire", "renew", "release", "guard"))
    parser.add_argument("resources", nargs="*")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--role")
    parser.add_argument("--session")
    parser.add_argument("--branch", dest="owner_branch")
    parser.add_argument("--pr", type=int)
    parser.add_argument("--reason")
    parser.add_argument("--ttl", type=int, dest="ttl_seconds")
    parser.add_argument("--mine", action="store_true")
    parser.add_argument("--transition-id")
    return parser


def _git_branch() -> str | None:
    env_branch = os.environ.get("GITHUB_HEAD_REF") or (
        os.environ.get("GITHUB_REF_NAME") if os.environ.get("GITHUB_REF_TYPE") == "branch" else None
    )
    if env_branch:
        return env_branch
    try:
        proc = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        return None
    branch = proc.stdout.strip() if proc.returncode == 0 else ""
    return branch or None


def _env_int(environ: Mapping[str, str], *names: str) -> int | None:
    for name in names:
        value = environ.get(name)
        if not value:
            continue
        try:
            parsed = int(value)
        except ValueError as exc:
            raise coordination.CoordinationError("OWNER_INVALID", f"{name} must be integer") from exc
        if parsed <= 0:
            raise coordination.CoordinationError("OWNER_INVALID", f"{name} must be positive")
        return parsed
    return None


def _owner(args: argparse.Namespace, environ: Mapping[str, str]) -> dict[str, Any]:
    role = args.role or environ.get("MOBILIPRESENTER_AGENT_ROLE")
    session = args.session or environ.get("MOBILIPRESENTER_AGENT_SESSION")
    if not role:
        raise coordination.CoordinationError("OWNER_REQUIRED", "--role or MOBILIPRESENTER_AGENT_ROLE is required")
    if not session:
        raise coordination.CoordinationError("OWNER_REQUIRED", "--session or MOBILIPRESENTER_AGENT_SESSION is required")
    branch = args.owner_branch or environ.get("MOBILIPRESENTER_AGENT_BRANCH") or _git_branch()
    pr = args.pr if args.pr is not None else _env_int(environ, "MOBILIPRESENTER_PR_NUMBER", "PR_NUMBER")
    return coordination.validate_owner({"role": role, "session": session, "branch": branch, "pr": pr})


def _transition_id(args: argparse.Namespace, action: str, owner: dict[str, Any]) -> str:
    if args.transition_id:
        return args.transition_id
    return f"{action}:{owner['session']}:{uuid.uuid4().hex[:12]}"


def _default_authority() -> GitHubCoordinationAuthority:
    return GitHubCoordinationAuthority(GhApiTransport())


def _print(payload: Any, *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return
    if isinstance(payload, dict):
        for key, value in payload.items():
            if isinstance(value, (dict, list)):
                print(f"{key}: {json.dumps(value, ensure_ascii=False)}")
            else:
                print(f"{key}: {value}")
    else:
        print(payload)


def _transition_payload(action: str, result: AppliedTransition) -> dict[str, Any]:
    return {
        "ok": True,
        "action": action,
        "beforeSha": result.before_sha,
        "afterSha": result.after_sha,
        "authorityNow": result.authority_now.isoformat(),
        "state": result.state,
        "event": result.event,
    }


def command_status(authority: GitHubCoordinationAuthority) -> dict[str, Any]:
    observed = authority.observe()
    current = coordination.compact_expired(observed.state, observed.authority_now)
    return {
        "ok": True,
        "schemaVersion": current["schemaVersion"],
        "authorityBranch": authority.authority_branch,
        "authorityHead": observed.head_sha,
        "authorityNow": observed.authority_now.isoformat(),
        "intents": current["intents"],
        "leases": current["leases"],
    }


def command_intent(authority: GitHubCoordinationAuthority, args: argparse.Namespace, owner: dict[str, Any]) -> dict[str, Any]:
    if not args.resources:
        raise coordination.CoordinationError("RESOURCE_INVALID", "intent requires at least one resource")
    if not args.reason:
        raise coordination.CoordinationError("REASON_INVALID", "intent requires --reason")
    transition_id = _transition_id(args, "intent", owner)

    def planner(state, authority_now):
        kwargs = {}
        if args.ttl_seconds is not None:
            kwargs["ttl_seconds"] = args.ttl_seconds
        return coordination.plan_intent(
            state,
            args.resources,
            owner,
            args.reason,
            authority_now,
            transition_id,
            **kwargs,
        )

    result = authority.mutate(planner, message=f"coordination: intent {transition_id}")
    return _transition_payload("intent", result)


def command_acquire(authority: GitHubCoordinationAuthority, args: argparse.Namespace, owner: dict[str, Any]) -> dict[str, Any]:
    if not args.resources:
        raise coordination.CoordinationError("RESOURCE_INVALID", "acquire requires at least one resource")
    if not args.reason:
        raise coordination.CoordinationError("REASON_INVALID", "acquire requires --reason")
    transition_id = _transition_id(args, "acquire", owner)

    def planner(state, authority_now):
        kwargs = {}
        if args.ttl_seconds is not None:
            kwargs["ttl_seconds"] = args.ttl_seconds
        return coordination.plan_acquire(
            state,
            args.resources,
            owner,
            args.reason,
            authority_now,
            transition_id,
            **kwargs,
        )

    result = authority.mutate(planner, message=f"coordination: acquire {transition_id}")
    return _transition_payload("acquire", result)


def command_renew(authority: GitHubCoordinationAuthority, args: argparse.Namespace, owner: dict[str, Any]) -> dict[str, Any]:
    if args.resources:
        raise coordination.CoordinationError("RENEW_INVALID", "renew currently supports --mine only")
    transition_id = _transition_id(args, "renew", owner)

    def planner(state, authority_now):
        return coordination.plan_renew_mine(state, owner, authority_now, transition_id)

    result = authority.mutate(planner, message=f"coordination: renew {transition_id}")
    return _transition_payload("renew", result)


def command_release(authority: GitHubCoordinationAuthority, args: argparse.Namespace, owner: dict[str, Any]) -> dict[str, Any]:
    if args.mine == bool(args.resources):
        raise coordination.CoordinationError("RELEASE_INVALID", "use resources or --mine, not both/neither")
    transition_id = _transition_id(args, "release", owner)

    def planner(state, authority_now):
        if args.mine:
            return coordination.plan_release(state, owner, authority_now, transition_id, mine=True)
        return coordination.plan_release(state, owner, authority_now, transition_id, resources=args.resources)

    result = authority.mutate(planner, message=f"coordination: release {transition_id}")
    return _transition_payload("release", result)


def command_guard(authority: GitHubCoordinationAuthority, args: argparse.Namespace, owner: dict[str, Any]) -> dict[str, Any]:
    if not args.resources:
        raise coordination.CoordinationError("RESOURCE_INVALID", "guard requires at least one resource")
    observed = authority.observe()
    checked = []
    for requested in coordination.normalize_resources(args.resources):
        allowed, lease = coordination.can_write(observed.state, requested, owner, observed.authority_now)
        entry = {"resource": requested, "allowed": allowed, "lease": lease}
        checked.append(entry)
        if not allowed:
            detail = {
                "resource": requested,
                "owner": lease["owner"] if lease else None,
                "expiresAt": lease["expiresAt"] if lease else None,
                "authorityHead": observed.head_sha,
            }
            raise coordination.CoordinationError("WRITE_BLOCKED_BY_LEASE", json.dumps(detail, separators=(",", ":")))
    return {
        "ok": True,
        "action": "guard",
        "authorityHead": observed.head_sha,
        "authorityNow": observed.authority_now.isoformat(),
        "checked": checked,
    }


def main(
    argv: list[str] | None = None,
    *,
    authority_factory: Callable[[], GitHubCoordinationAuthority] = _default_authority,
    environ: Mapping[str, str] | None = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    env = os.environ if environ is None else environ
    try:
        authority = authority_factory()
        if args.command == "status":
            if args.resources:
                raise coordination.CoordinationError("STATUS_INVALID", "status accepts no resources")
            payload = command_status(authority)
        else:
            owner = _owner(args, env)
            if args.command == "intent":
                payload = command_intent(authority, args, owner)
            elif args.command == "acquire":
                payload = command_acquire(authority, args, owner)
            elif args.command == "renew":
                payload = command_renew(authority, args, owner)
            elif args.command == "release":
                payload = command_release(authority, args, owner)
            else:
                payload = command_guard(authority, args, owner)
        _print(payload, as_json=args.as_json)
        return 0
    except (coordination.CoordinationError, CoordinationRemoteError) as exc:
        code = getattr(exc, "code", "COORDINATION_ERROR")
        detail = getattr(exc, "detail", str(exc))
        payload = {"ok": False, "error": code, "detail": detail}
        if args.as_json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(f"BLOCKED\n{code}{':' + detail if detail else ''}", file=sys.stderr)
        return ERROR_EXIT


if __name__ == "__main__":
    raise SystemExit(main())
