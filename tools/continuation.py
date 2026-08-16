#!/usr/bin/env python3
"""ContinuationState compatibility model and read-only local inspection helpers.

Operational mutation lives exclusively on the Git-backed live authority via
continuation_transition + continuation_remote. This module never writes state.
During M5A, ContinuationState 0.1 remains current; 0.2 is candidate-only.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import transition_protocol as protocol
from tools.semantics.identity import WorkerId
from tools.semantics.work import WorkStatus

DIR = ROOT / "ops" / "continuations"
CURRENT_SCHEMA_VERSION = "ContinuationState 0.1"
CANDIDATE_SCHEMA_VERSION = "ContinuationState 0.2"
SCHEMA = CURRENT_SCHEMA_VERSION
ERROR_EXIT = 2
STATUSES = {item.value for item in WorkStatus}
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
V01_FIELDS = {
    "schemaVersion", "id", "actor", "status", "branch", "prNumber",
    "completed", "remaining", "nextAction", "lastKnownGood", "blockedBy", "handoffTo",
}
V02_FIELDS = {
    "schemaVersion", "id", "workerId", "status", "branch", "prNumber", "dependsOn",
    "completed", "remaining", "nextAction", "lastKnownGood", "blockers", "handoffToWorkerId",
}


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


def _worker(value: Any, code: str) -> str:
    try:
        return str(WorkerId(text(value, code)))
    except RuntimeError as exc:
        raise RuntimeError(code) from exc


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


def _validate_common(value: Any, expected_id: str | None, fields: set[str], schema_version: str) -> tuple[list[str], list[str], list[str], str | None]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return ["CONTINUATION_ROOT_INVALID"], [], [], None
    if set(value) != fields:
        errors.append("CONTINUATION_FIELDS_INVALID")
    if value.get("schemaVersion") != schema_version:
        errors.append("CONTINUATION_SCHEMA_UNSUPPORTED")
    cid = value.get("id")
    if not isinstance(cid, str) or not ID_RE.fullmatch(cid):
        errors.append("CONTINUATION_ID_INVALID")
    elif expected_id and cid != expected_id:
        errors.append("CONTINUATION_ID_PATH_MISMATCH")
    try:
        WorkStatus.parse(str(value.get("status") or ""))
    except RuntimeError:
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
    return errors, completed, remaining, next_action


def validate_v01(value: Any, expected_id: str | None = None) -> list[str]:
    errors, _completed, remaining, next_action = _validate_common(value, expected_id, V01_FIELDS, CURRENT_SCHEMA_VERSION)
    if not isinstance(value, dict):
        return errors
    if not isinstance(value.get("actor"), str) or not value["actor"].strip():
        errors.append("CONTINUATION_ACTOR_INVALID")
    status = value.get("status")
    try:
        blocked = strings(value.get("blockedBy"), "CONTINUATION_BLOCKERS_INVALID")
    except RuntimeError as exc:
        errors.append(str(exc)); blocked = []
    target = value.get("handoffTo")
    if target is not None and (not isinstance(target, str) or not target.strip()):
        errors.append("CONTINUATION_HANDOFF_TO_INVALID")
    if status == WorkStatus.DONE.value and (remaining or next_action is not None or blocked or target is not None):
        errors.append("CONTINUATION_DONE_STATE_INVALID")
    if status == WorkStatus.WAITING.value and (not blocked or next_action is None or target is not None):
        errors.append("CONTINUATION_WAITING_STATE_INVALID")
    if status == WorkStatus.HANDOFF.value and (target is None or next_action is None or blocked):
        errors.append("CONTINUATION_HANDOFF_STATE_INVALID")
    if status in {WorkStatus.READY.value, WorkStatus.IN_PROGRESS.value} and (blocked or target is not None or (remaining and next_action is None)):
        errors.append("CONTINUATION_ACTIVE_STATE_INVALID")
    return errors


def validate_v02(value: Any, expected_id: str | None = None) -> list[str]:
    errors, _completed, remaining, next_action = _validate_common(value, expected_id, V02_FIELDS, CANDIDATE_SCHEMA_VERSION)
    if not isinstance(value, dict):
        return errors
    try:
        _worker(value.get("workerId"), "CONTINUATION_WORKER_ID_INVALID")
    except RuntimeError as exc:
        errors.append(str(exc))
    try:
        dependencies = strings(value.get("dependsOn"), "CONTINUATION_DEPENDENCIES_INVALID")
        for dependency in dependencies:
            if not ID_RE.fullmatch(dependency):
                raise RuntimeError("CONTINUATION_DEPENDENCIES_INVALID")
        if value.get("id") in dependencies:
            errors.append("CONTINUATION_SELF_DEPENDENCY")
    except RuntimeError as exc:
        errors.append(str(exc)); dependencies = []
    status = value.get("status")
    try:
        blockers = strings(value.get("blockers"), "CONTINUATION_BLOCKERS_INVALID")
    except RuntimeError as exc:
        errors.append(str(exc)); blockers = []
    target = value.get("handoffToWorkerId")
    if target is not None:
        try:
            _worker(target, "CONTINUATION_HANDOFF_WORKER_ID_INVALID")
        except RuntimeError as exc:
            errors.append(str(exc))
    if status == WorkStatus.DONE.value and (remaining or next_action is not None or blockers or target is not None):
        errors.append("CONTINUATION_DONE_STATE_INVALID")
    if status == WorkStatus.WAITING.value and (not blockers or next_action is None or target is not None):
        errors.append("CONTINUATION_WAITING_STATE_INVALID")
    if status == WorkStatus.HANDOFF.value and (target is None or next_action is None or blockers):
        errors.append("CONTINUATION_HANDOFF_STATE_INVALID")
    if status in {WorkStatus.READY.value, WorkStatus.IN_PROGRESS.value} and (blockers or target is not None or (remaining and next_action is None)):
        errors.append("CONTINUATION_ACTIVE_STATE_INVALID")
    return errors


def validate_current(value: Any, expected_id: str | None = None) -> list[str]:
    return validate_v01(value, expected_id)


def validate_compatible(value: Any, expected_id: str | None = None) -> list[str]:
    if not isinstance(value, dict):
        return ["CONTINUATION_ROOT_INVALID"]
    version = value.get("schemaVersion")
    if version == CURRENT_SCHEMA_VERSION:
        return validate_v01(value, expected_id)
    if version == CANDIDATE_SCHEMA_VERSION:
        return validate_v02(value, expected_id)
    return ["CONTINUATION_SCHEMA_UNSUPPORTED"]


def validate(value: Any, expected_id: str | None = None) -> list[str]:
    """Compatibility alias for the live/current 0.1 contract during M5A."""
    return validate_current(value, expected_id)


def valid(value: dict[str, Any], expected_id: str | None = None) -> dict[str, Any]:
    errors = validate_current(value, expected_id)
    if errors:
        raise RuntimeError(errors[0])
    return value


def valid_compatible(value: dict[str, Any], expected_id: str | None = None) -> dict[str, Any]:
    errors = validate_compatible(value, expected_id)
    if errors:
        raise RuntimeError(errors[0])
    return value


def require_current(value: dict[str, Any], expected_id: str | None = None) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("schemaVersion") != CURRENT_SCHEMA_VERSION:
        raise RuntimeError("CONTINUATION_SCHEMA_NOT_CURRENT")
    return valid(value, expected_id)


def migrate_v01_to_v02(value: dict[str, Any]) -> dict[str, Any]:
    valid(value, value.get("id"))
    worker_id = _worker(value["actor"], "CONTINUATION_WORKER_ID_INVALID")
    target = value["handoffTo"]
    target_worker = None if target is None else _worker(target, "CONTINUATION_HANDOFF_WORKER_ID_INVALID")
    candidate = {
        "schemaVersion": CANDIDATE_SCHEMA_VERSION,
        "id": value["id"],
        "workerId": worker_id,
        "status": value["status"],
        "branch": value["branch"],
        "prNumber": value["prNumber"],
        "dependsOn": [],
        "completed": copy.deepcopy(value["completed"]),
        "remaining": copy.deepcopy(value["remaining"]),
        "nextAction": value["nextAction"],
        "lastKnownGood": copy.deepcopy(value["lastKnownGood"]),
        "blockers": copy.deepcopy(value["blockedBy"]),
        "handoffToWorkerId": target_worker,
    }
    errors = validate_v02(candidate, value["id"])
    if errors:
        raise RuntimeError(errors[0])
    return candidate


def operational_view(value: dict[str, Any]) -> dict[str, Any]:
    value = valid_compatible(value, value.get("id") if isinstance(value, dict) else None)
    if value["schemaVersion"] == CURRENT_SCHEMA_VERSION:
        value = migrate_v01_to_v02(value)
    return {
        "id": value["id"],
        "workerId": value["workerId"],
        "status": value["status"],
        "branch": value["branch"],
        "prNumber": value["prNumber"],
        "dependsOn": copy.deepcopy(value["dependsOn"]),
        "completed": copy.deepcopy(value["completed"]),
        "remaining": copy.deepcopy(value["remaining"]),
        "nextAction": value["nextAction"],
        "lastKnownGood": copy.deepcopy(value["lastKnownGood"]),
        "blockers": copy.deepcopy(value["blockers"]),
        "handoffToWorkerId": value["handoffToWorkerId"],
    }


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
