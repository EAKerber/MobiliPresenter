#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import inspect
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import coordination
from tools import coordination_apply
from tools import coordination_transition as transition
from tools.coordination_remote import (
    CoordinationRemoteError,
    GhApiTransport,
    GitHubCoordinationAuthority,
)

ERROR_EXIT = 2


def _default_authority() -> GitHubCoordinationAuthority:
    return GitHubCoordinationAuthority(GhApiTransport())


def _common_owner_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--role")
    parser.add_argument("--session")
    parser.add_argument("--branch", dest="owner_branch")
    parser.add_argument("--pr", type=int)


def _json_flag(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", dest="as_json")


def build_parser(*, prog: str = "coordination", legacy: bool = False) -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog=prog,
        description=(
            "Legacy MobiliPresenter coordination lease compatibility surface"
            if legacy
            else "Canonical MobiliPresenter Coordination surface"
        ),
    )
    sub = root.add_subparsers(dest="command", required=True)

    status = sub.add_parser("status")
    _json_flag(status)

    guard = sub.add_parser("guard")
    guard.add_argument("resources", nargs="+")
    _common_owner_flags(guard)
    _json_flag(guard)

    for name in ("intent", "acquire"):
        item = sub.add_parser(name)
        item.add_argument("resources", nargs="+")
        _common_owner_flags(item)
        item.add_argument("--reason", required=True)
        item.add_argument("--ttl", type=int, dest="ttl_seconds")
        item.add_argument("--transition-id", required=not legacy)
        _json_flag(item)

    renew = sub.add_parser("renew")
    _common_owner_flags(renew)
    renew.add_argument("--transition-id", required=not legacy)
    _json_flag(renew)

    release = sub.add_parser("release")
    release.add_argument("resources", nargs="*")
    release.add_argument("--mine", action="store_true")
    _common_owner_flags(release)
    release.add_argument("--transition-id", required=not legacy)
    _json_flag(release)

    if not legacy:
        validate = sub.add_parser("validate")
        validate.add_argument("plan_file")
        _json_flag(validate)

        apply_cmd = sub.add_parser("apply")
        apply_cmd.add_argument("plan_file")
        apply_cmd.add_argument("--expected-plan", required=True)
        _json_flag(apply_cmd)
    return root


def _git_branch() -> str | None:
    env_branch = os.environ.get("GITHUB_HEAD_REF") or (
        os.environ.get("GITHUB_REF_NAME")
        if os.environ.get("GITHUB_REF_TYPE") == "branch"
        else None
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
            raise coordination.CoordinationError(
                "OWNER_INVALID", f"{name} must be integer"
            ) from exc
        if parsed <= 0:
            raise coordination.CoordinationError(
                "OWNER_INVALID", f"{name} must be positive"
            )
        return parsed
    return None


def _owner(args: argparse.Namespace, environ: Mapping[str, str]) -> dict[str, Any]:
    role = args.role or environ.get("MOBILIPRESENTER_AGENT_ROLE")
    session = args.session or environ.get("MOBILIPRESENTER_AGENT_SESSION")
    if not role:
        raise coordination.CoordinationError(
            "OWNER_REQUIRED", "--role or MOBILIPRESENTER_AGENT_ROLE is required"
        )
    if not session:
        raise coordination.CoordinationError(
            "OWNER_REQUIRED",
            "--session or MOBILIPRESENTER_AGENT_SESSION is required",
        )
    branch = (
        args.owner_branch
        or environ.get("MOBILIPRESENTER_AGENT_BRANCH")
        or _git_branch()
    )
    pr = (
        args.pr
        if args.pr is not None
        else _env_int(environ, "MOBILIPRESENTER_PR_NUMBER", "PR_NUMBER")
    )
    return coordination.validate_owner(
        {"role": role, "session": session, "branch": branch, "pr": pr}
    )


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


def _status(authority: GitHubCoordinationAuthority) -> dict[str, Any]:
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


def _guard(
    authority: GitHubCoordinationAuthority,
    args: argparse.Namespace,
    owner: dict[str, Any],
) -> dict[str, Any]:
    observed = authority.observe()
    checked = []
    for requested in coordination.normalize_resources(args.resources):
        allowed, lease = coordination.can_write(
            observed.state, requested, owner, observed.authority_now
        )
        entry = {"resource": requested, "allowed": allowed, "lease": lease}
        checked.append(entry)
        if not allowed:
            detail = {
                "resource": requested,
                "owner": lease["owner"] if lease else None,
                "expiresAt": lease["expiresAt"] if lease else None,
                "authorityHead": observed.head_sha,
            }
            raise coordination.CoordinationError(
                "WRITE_BLOCKED_BY_LEASE",
                json.dumps(detail, separators=(",", ":")),
            )
    return {
        "ok": True,
        "action": "guard",
        "authorityHead": observed.head_sha,
        "authorityNow": observed.authority_now.isoformat(),
        "checked": checked,
    }


def _plan(
    authority: GitHubCoordinationAuthority,
    args: argparse.Namespace,
    owner: dict[str, Any],
    *,
    legacy: bool,
) -> dict[str, Any]:
    observed = authority.observe()
    tid = args.transition_id
    if legacy and not tid:
        tid = f"{args.command}:{owner['session']}:{uuid.uuid4().hex[:12]}"
    if not tid:
        raise coordination.CoordinationError(
            "TRANSITION_ID_INVALID", "--transition-id is required"
        )
    common = {
        "before": observed.state,
        "authority_head": observed.head_sha,
        "authority_now": observed.authority_now,
        "owner": owner,
        "transition_id": tid,
        "repository": getattr(authority, "repository", transition.DEFAULT_REPOSITORY),
        "authority_branch": getattr(
            authority, "authority_branch", transition.DEFAULT_BRANCH
        ),
        "state_path": getattr(authority, "state_path", transition.DEFAULT_PATH),
    }
    if args.command == "intent":
        kwargs = {}
        if args.ttl_seconds is not None:
            kwargs["ttl_seconds"] = args.ttl_seconds
        return transition.plan_intent(
            **common, resources=args.resources, reason=args.reason, **kwargs
        )
    if args.command == "acquire":
        kwargs = {}
        if args.ttl_seconds is not None:
            kwargs["ttl_seconds"] = args.ttl_seconds
        return transition.plan_acquire(
            **common, resources=args.resources, reason=args.reason, **kwargs
        )
    if args.command == "renew":
        return transition.plan_renew(**common)
    if args.command == "release":
        if args.mine == bool(args.resources):
            raise coordination.CoordinationError(
                "RELEASE_INVALID", "use resources or --mine, not both/neither"
            )
        return transition.plan_release(
            **common,
            resources=None if args.mine else args.resources,
            mine=args.mine,
        )
    raise coordination.CoordinationError(
        "COORDINATION_COMMAND_INVALID", args.command
    )


def _load_plan(path: str) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("COORDINATION_PLAN_INPUT_INVALID") from exc
    if not isinstance(value, dict):
        raise RuntimeError("COORDINATION_PLAN_INPUT_INVALID")
    return value


def _validate_live(
    authority: GitHubCoordinationAuthority, plan: dict[str, Any]
) -> dict[str, Any]:
    observed = authority.observe()
    if observed.head_sha != plan.get("intent", {}).get("expectedAuthorityHead"):
        raise RuntimeError("COORDINATION_PLAN_STALE")
    transition.validate_plan(
        plan,
        observed.state,
        repository=getattr(
            authority, "repository", transition.DEFAULT_REPOSITORY
        ),
        authority_branch=getattr(
            authority, "authority_branch", transition.DEFAULT_BRANCH
        ),
        state_path=getattr(authority, "state_path", transition.DEFAULT_PATH),
        bind_before=True,
        authority_now=observed.authority_now,
    )
    return {
        "ok": True,
        "planHash": plan["planHash"],
        "authorityHead": observed.head_sha,
        "status": "PASS",
        "readOnly": True,
        "authorizesMutation": False,
    }


def _legacy_event(plan: dict[str, Any]) -> dict[str, Any]:
    intent = plan["intent"]
    at = intent["plannedAt"]
    base = {
        "action": plan["action"],
        "transitionId": intent["transitionId"],
        "owner": copy.deepcopy(intent["owner"]),
        "resources": list(intent["resources"]),
        "at": at,
    }
    if plan["action"] == "intent":
        entries = [
            item
            for item in plan["candidate"]["intents"]
            if str(item["intentId"]).startswith(f"{intent['transitionId']}:")
        ]
        if entries:
            base["expiresAt"] = entries[0]["expiresAt"]
    elif plan["action"] == "acquire":
        entries = [
            item
            for item in plan["candidate"]["leases"]
            if str(item["leaseId"]).startswith(f"{intent['transitionId']}:")
        ]
        if entries:
            base["expiresAt"] = entries[0]["expiresAt"]
            base["leaseIds"] = [item["leaseId"] for item in entries]
    elif plan["action"] == "release" and intent.get("mine"):
        base["action"] = "release-mine"
    return base


def _legacy_apply(
    authority: GitHubCoordinationAuthority,
    plan: dict[str, Any],
) -> dict[str, Any]:
    expected_head = plan["intent"]["expectedAuthorityHead"]

    def planner(state, authority_now):
        try:
            transition.validate_plan(
                plan,
                state,
                repository=getattr(
                    authority, "repository", transition.DEFAULT_REPOSITORY
                ),
                authority_branch=getattr(
                    authority, "authority_branch", transition.DEFAULT_BRANCH
                ),
                state_path=getattr(
                    authority, "state_path", transition.DEFAULT_PATH
                ),
                bind_before=True,
                authority_now=authority_now,
            )
        except RuntimeError as exc:
            raise CoordinationRemoteError(str(exc).split(":", 1)[0]) from exc
        return copy.deepcopy(plan["candidate"]), _legacy_event(plan)

    mutate_kwargs = {
        "message": f"coordination: {plan['action']} {plan['intent']['transitionId']}"
    }
    try:
        if "expected_revision" in inspect.signature(authority.mutate).parameters:
            mutate_kwargs["expected_revision"] = expected_head
        result = authority.mutate(planner, **mutate_kwargs)
    except (TypeError, ValueError) as exc:
        raise CoordinationRemoteError("COORDINATION_LEGACY_ADAPTER_INVALID", str(exc)) from exc
    if result.before_sha != expected_head:
        raise CoordinationRemoteError(
            "COORDINATION_PLAN_STALE",
            f"expected {expected_head}, observed {result.before_sha}",
        )
    planned_at = datetime.fromisoformat(
        plan["intent"]["plannedAt"].replace("Z", "+00:00")
    )
    return {
        "ok": True,
        "action": plan["action"],
        "beforeSha": result.before_sha,
        "afterSha": result.after_sha,
        "authorityNow": planned_at.isoformat(),
        "state": result.state,
        "event": result.event,
    }


def _dispatch(
    args: argparse.Namespace,
    *,
    authority_factory: Callable[[], GitHubCoordinationAuthority],
    environ: Mapping[str, str],
    legacy: bool,
) -> tuple[dict[str, Any], bool]:
    authority = authority_factory()
    if args.command == "status":
        return _status(authority), args.as_json
    if args.command == "guard":
        return _guard(authority, args, _owner(args, environ)), args.as_json
    if not legacy and args.command == "validate":
        plan = _load_plan(args.plan_file)
        return _validate_live(authority, plan), args.as_json
    if not legacy and args.command == "apply":
        plan = _load_plan(args.plan_file)
        receipt = coordination_apply.apply(authority, plan, args.expected_plan)
        return {
            "kind": "transition-receipt",
            "plan": plan,
            "receipt": receipt,
        }, args.as_json
    owner = _owner(args, environ)
    plan = _plan(authority, args, owner, legacy=legacy)
    if legacy:
        return _legacy_apply(authority, plan), args.as_json
    return plan, args.as_json


def _main(
    argv: list[str] | None,
    *,
    legacy: bool,
    authority_factory: Callable[[], GitHubCoordinationAuthority],
    environ: Mapping[str, str] | None,
) -> int:
    parser = build_parser(prog="lock" if legacy else "coordination", legacy=legacy)
    args = parser.parse_args(argv)
    env = os.environ if environ is None else environ
    try:
        payload, as_json = _dispatch(
            args,
            authority_factory=authority_factory,
            environ=env,
            legacy=legacy,
        )
        _print(payload, as_json=as_json)
        return 0
    except (coordination.CoordinationError, CoordinationRemoteError, RuntimeError) as exc:
        code = getattr(exc, "code", str(exc).split(":", 1)[0] or "COORDINATION_ERROR")
        detail = getattr(exc, "detail", "")
        payload = {"ok": False, "error": code, "detail": detail}
        if getattr(args, "as_json", False):
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(
                f"BLOCKED\n{code}{':' + detail if detail else ''}",
                file=sys.stderr,
            )
        return ERROR_EXIT


def main(
    argv: list[str] | None = None,
    *,
    authority_factory: Callable[[], GitHubCoordinationAuthority] = _default_authority,
    environ: Mapping[str, str] | None = None,
) -> int:
    return _main(
        argv,
        legacy=False,
        authority_factory=authority_factory,
        environ=environ,
    )


def legacy_lock_main(
    argv: list[str] | None = None,
    *,
    authority_factory: Callable[[], GitHubCoordinationAuthority] = _default_authority,
    environ: Mapping[str, str] | None = None,
) -> int:
    return _main(
        argv,
        legacy=True,
        authority_factory=authority_factory,
        environ=environ,
    )


if __name__ == "__main__":
    raise SystemExit(main())
