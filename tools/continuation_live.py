#!/usr/bin/env python3
"""Operator CLI for the live Git-backed Continuation authority."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import continuation
from tools import continuation_transition as transition
from tools.continuation_remote import ContinuationRemoteError, GitHubContinuationAuthority

ERROR_EXIT = 2


def flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-plan")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="continuation-live", description="Live Continuation State authority")
    sub = root.add_subparsers(dest="command", required=True)
    for name in ("list", "verify"):
        command = sub.add_parser(name)
        command.add_argument("--json", action="store_true", dest="as_json")
    command = sub.add_parser("show")
    command.add_argument("id")
    command.add_argument("--json", action="store_true", dest="as_json")
    command = sub.add_parser("create")
    command.add_argument("id")
    command.add_argument("--actor", required=True)
    command.add_argument("--remaining", action="append", required=True)
    command.add_argument("--next-action", required=True)
    command.add_argument("--branch")
    command.add_argument("--pr", type=int)
    flags(command)
    command = sub.add_parser("advance")
    command.add_argument("id")
    command.add_argument("--complete", action="append", required=True)
    command.add_argument("--next-action")
    command.add_argument("--last-good-sha")
    command.add_argument("--checkpoint")
    flags(command)
    command = sub.add_parser("wait")
    command.add_argument("id")
    command.add_argument("--blocked-by", action="append", required=True)
    flags(command)
    command = sub.add_parser("handoff")
    command.add_argument("id")
    command.add_argument("--to", required=True)
    command.add_argument("--next-action", required=True)
    flags(command)
    command = sub.add_parser("resume")
    command.add_argument("id")
    command.add_argument("--actor", required=True)
    flags(command)
    command = sub.add_parser("done")
    command.add_argument("id")
    flags(command)
    return root


def plan_for(authority: GitHubContinuationAuthority, args: argparse.Namespace) -> dict:
    observation = authority.observe()
    before = observation.items.get(getattr(args, "id", None))
    if args.command == "create":
        if before is not None:
            raise RuntimeError("CONTINUATION_ALREADY_EXISTS")
        return transition.create(args.id, args.actor, args.remaining, args.next_action, args.branch, args.pr)
    if before is None:
        raise RuntimeError("CONTINUATION_FILE_MISSING")
    if args.command == "advance":
        return transition.advance(before, args.complete, args.next_action, args.last_good_sha, args.checkpoint)
    if args.command == "wait":
        return transition.wait(before, args.blocked_by)
    if args.command == "handoff":
        return transition.handoff(before, args.to, args.next_action)
    if args.command == "resume":
        return transition.resume(before, args.actor)
    if args.command == "done":
        return transition.done(before)
    raise RuntimeError("CONTINUATION_COMMAND_INVALID")


def output(value, as_json: bool) -> None:
    print(json.dumps(value, indent=2 if as_json else None, ensure_ascii=False))


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    authority = GitHubContinuationAuthority()
    try:
        if args.command in {"list", "verify", "show"}:
            observation = authority.observe()
            if args.command == "list":
                payload = {
                    "schemaVersion": "ContinuationDiscovery 0.1",
                    "authorityBranch": authority.authority_branch,
                    "authorityHead": observation.head_sha,
                    "items": [
                        {"id": value["id"], "actor": value["actor"], "status": value["status"], "nextAction": value["nextAction"], "stateHash": continuation.state_hash(value)}
                        for _, value in sorted(observation.items.items())
                    ],
                }
            elif args.command == "verify":
                payload = {
                    "ok": True,
                    "authorityBranch": authority.authority_branch,
                    "authorityHead": observation.head_sha,
                    "count": len(observation.items),
                    "ids": sorted(observation.items),
                }
            else:
                value = observation.items.get(args.id)
                if value is None:
                    raise RuntimeError("CONTINUATION_FILE_MISSING")
                payload = {
                    "authorityBranch": authority.authority_branch,
                    "authorityHead": observation.head_sha,
                    "state": value,
                    "stateHash": continuation.state_hash(value),
                }
            output(payload, args.as_json)
            return 0

        planned = plan_for(authority, args)
        payload = authority.apply(planned, args.expected_plan) if args.apply else planned
        output(payload, args.as_json)
        return 0
    except (RuntimeError, ContinuationRemoteError) as exc:
        output(
            {"ok": False, "error": getattr(exc, "code", str(exc)), "detail": getattr(exc, "detail", "")},
            getattr(args, "as_json", False),
        )
        return ERROR_EXIT


if __name__ == "__main__":
    raise SystemExit(main())
