#!/usr/bin/env python3
"""ContinuationState 0.1 model and read-only local inspection helpers.

Operational mutation lives exclusively on the Git-backed live authority via
continuation_transition + continuation_remote. This module never writes state.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import transition_protocol as protocol

DIR = ROOT / "ops" / "continuations"
SCHEMA = "ContinuationState 0.1"
ERROR_EXIT = 2
STATUSES = {"READY", "IN_PROGRESS", "WAITING", "HANDOFF", "DONE"}
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def text(value: Any, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(code)
    return value.strip()


def strings(value: Any, code: str) -> list[str]:
    if not isinstance(value, list):
        raise RuntimeError(code)
    out: list[str] = []
    for item in value:
        item = text(item, code)
        if item in out:
            raise RuntimeError(code)
        out.append(item)
    return out


def state_hash(value: dict[str, Any] | None) -> str | None:
    return protocol.state_hash(value)


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError("CONTINUATION_FILE_MISSING") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("CONTINUATION_JSON_INVALID") from exc
    if not isinstance(value, dict):
        raise RuntimeError("CONTINUATION_ROOT_INVALID")
    return value


def validate(value: Any, expected_id: str | None = None) -> list[str]:
    errors: list[str] = []
    fields = {
        "schemaVersion", "id", "actor", "status", "branch", "prNumber",
        "completed", "remaining", "nextAction", "lastKnownGood", "blockedBy", "handoffTo",
    }
    if not isinstance(value, dict):
        return ["CONTINUATION_ROOT_INVALID"]
    if set(value) != fields:
        errors.append("CONTINUATION_FIELDS_INVALID")
    if value.get("schemaVersion") != SCHEMA:
        errors.append("CONTINUATION_SCHEMA_UNSUPPORTED")
    cid = value.get("id")
    if not isinstance(cid, str) or not ID_RE.fullmatch(cid):
        errors.append("CONTINUATION_ID_INVALID")
    elif expected_id and cid != expected_id:
        errors.append("CONTINUATION_ID_PATH_MISMATCH")
    if not isinstance(value.get("actor"), str) or not value["actor"].strip():
        errors.append("CONTINUATION_ACTOR_INVALID")
    status = value.get("status")
    if status not in STATUSES:
        errors.append("CONTINUATION_STATUS_INVALID")
    branch = value.get("branch")
    pr = value.get("prNumber")
    if branch is not None and (not isinstance(branch, str) or not branch.strip()):
        errors.append("CONTINUATION_BRANCH_INVALID")
    if pr is not None and (type(pr) is not int or pr <= 0):
        errors.append("CONTINUATION_PR_INVALID")
    if pr is not None and branch is None:
        errors.append("CONTINUATION_PR_REQUIRES_BRANCH")
    try:
        completed = strings(value.get("completed"), "CONTINUATION_COMPLETED_INVALID")
    except RuntimeError as exc:
        errors.append(str(exc)); completed = []
    try:
        remaining = strings(value.get("remaining"), "CONTINUATION_REMAINING_INVALID")
    except RuntimeError as exc:
        errors.append(str(exc)); remaining = []
    if set(completed) & set(remaining):
        errors.append("CONTINUATION_WORK_OVERLAP")
    next_action = value.get("nextAction")
    if next_action is not None and (not isinstance(next_action, str) or not next_action.strip()):
        errors.append("CONTINUATION_NEXT_ACTION_INVALID")
    last = value.get("lastKnownGood")
    if not isinstance(last, dict) or set(last) != {"sha", "checkpoint"}:
        errors.append("CONTINUATION_LAST_GOOD_INVALID")
    else:
        sha = last.get("sha")
        checkpoint = last.get("checkpoint")
        if sha is not None and (not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}", sha)):
            errors.append("CONTINUATION_LAST_GOOD_SHA_INVALID")
        if checkpoint is not None and (not isinstance(checkpoint, str) or not checkpoint.strip()):
            errors.append("CONTINUATION_LAST_GOOD_CHECKPOINT_INVALID")
    try:
        blocked = strings(value.get("blockedBy"), "CONTINUATION_BLOCKERS_INVALID")
    except RuntimeError as exc:
        errors.append(str(exc)); blocked = []
    target = value.get("handoffTo")
    if target is not None and (not isinstance(target, str) or not target.strip()):
        errors.append("CONTINUATION_HANDOFF_TO_INVALID")
    if status == "DONE" and (remaining or next_action is not None or blocked or target is not None):
        errors.append("CONTINUATION_DONE_STATE_INVALID")
    if status == "WAITING" and (not blocked or next_action is None or target is not None):
        errors.append("CONTINUATION_WAITING_STATE_INVALID")
    if status == "HANDOFF" and (target is None or next_action is None or blocked):
        errors.append("CONTINUATION_HANDOFF_STATE_INVALID")
    if status in {"READY", "IN_PROGRESS"} and (blocked or target is not None or (remaining and next_action is None)):
        errors.append("CONTINUATION_ACTIVE_STATE_INVALID")
    return errors


def valid(value: dict[str, Any], expected_id: str | None = None) -> dict[str, Any]:
    errors = validate(value, expected_id)
    if errors:
        raise RuntimeError(errors[0])
    return value


def load(cid: str) -> dict[str, Any]:
    if not ID_RE.fullmatch(cid):
        raise RuntimeError("CONTINUATION_ID_INVALID")
    return valid(load_json(DIR / f"{cid}.json"), cid)


def discover() -> list[dict[str, Any]]:
    if not DIR.is_dir():
        return []
    return [valid(load_json(path), path.stem) for path in sorted(DIR.glob("*.json"))]


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="continuation", description="Read-only local ContinuationState inspection")
    sub = root.add_subparsers(dest="command", required=True)
    for name in ("list", "verify"):
        command = sub.add_parser(name)
        command.add_argument("--json", action="store_true", dest="as_json")
    command = sub.add_parser("show")
    command.add_argument("id")
    command.add_argument("--json", action="store_true", dest="as_json")
    return root


def output(value: Any, as_json: bool) -> None:
    print(json.dumps(value, indent=2 if as_json else None, ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "list":
            values = discover()
            payload = {
                "schemaVersion": "ContinuationDiscovery 0.1",
                "readOnly": True,
                "items": [
                    {"id": value["id"], "actor": value["actor"], "status": value["status"], "nextAction": value["nextAction"], "stateHash": state_hash(value)}
                    for value in values
                ],
            }
        elif args.command == "show":
            value = load(args.id)
            payload = {"readOnly": True, "state": value, "stateHash": state_hash(value)}
        elif args.command == "verify":
            values = discover()
            payload = {"ok": True, "readOnly": True, "count": len(values), "ids": [value["id"] for value in values]}
        else:
            raise RuntimeError("CONTINUATION_COMMAND_INVALID")
        output(payload, args.as_json)
        return 0
    except RuntimeError as exc:
        output({"ok": False, "error": str(exc)}, getattr(args, "as_json", False))
        return ERROR_EXIT


if __name__ == "__main__":
    raise SystemExit(main())
