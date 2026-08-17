"""Canonical WorkItem / ContinuationState 0.2 model."""
from __future__ import annotations

import copy
import re
from typing import Any

from tools import transition_protocol as protocol
from tools.semantics.identity import WorkerId
from tools.semantics.work import WorkStatus

CURRENT_SCHEMA_VERSION = "ContinuationState 0.2"
INVENTORY_SCHEMA_VERSION = "WorkAuthorityInventory 0.1"
SCHEMA = CURRENT_SCHEMA_VERSION
STATUSES = {item.value for item in WorkStatus}
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
FIELDS = {
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


def validate_current(value: Any, expected_id: str | None = None) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return ["CONTINUATION_ROOT_INVALID"]
    if set(value) != FIELDS:
        errors.append("CONTINUATION_FIELDS_INVALID")
    if value.get("schemaVersion") != CURRENT_SCHEMA_VERSION:
        errors.append("CONTINUATION_SCHEMA_UNSUPPORTED")
    cid = value.get("id")
    if not isinstance(cid, str) or not ID_RE.fullmatch(cid):
        errors.append("CONTINUATION_ID_INVALID")
    elif expected_id and cid != expected_id:
        errors.append("CONTINUATION_ID_PATH_MISMATCH")
    try:
        _worker(value.get("workerId"), "CONTINUATION_WORKER_ID_INVALID")
    except RuntimeError as exc:
        errors.append(str(exc))
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
        dependencies = strings(value.get("dependsOn"), "CONTINUATION_DEPENDENCIES_INVALID")
        if any(not ID_RE.fullmatch(dep) for dep in dependencies):
            errors.append("CONTINUATION_DEPENDENCIES_INVALID")
        if cid in dependencies:
            errors.append("CONTINUATION_SELF_DEPENDENCY")
    except RuntimeError as exc:
        errors.append(str(exc)); dependencies = []
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
        blockers = strings(value.get("blockers"), "CONTINUATION_BLOCKERS_INVALID")
    except RuntimeError as exc:
        errors.append(str(exc)); blockers = []
    target = value.get("handoffToWorkerId")
    if target is not None:
        try:
            _worker(target, "CONTINUATION_HANDOFF_WORKER_ID_INVALID")
        except RuntimeError as exc:
            errors.append(str(exc))
    status = value.get("status")
    if status == WorkStatus.DONE.value and (remaining or next_action is not None or blockers or target is not None):
        errors.append("CONTINUATION_DONE_STATE_INVALID")
    if status == WorkStatus.WAITING.value and (not blockers or next_action is None or target is not None):
        errors.append("CONTINUATION_WAITING_STATE_INVALID")
    if status == WorkStatus.HANDOFF.value and (target is None or next_action is None or blockers):
        errors.append("CONTINUATION_HANDOFF_STATE_INVALID")
    if status in {WorkStatus.READY.value, WorkStatus.IN_PROGRESS.value} and (
        blockers or target is not None or (remaining and next_action is None)
    ):
        errors.append("CONTINUATION_ACTIVE_STATE_INVALID")
    return errors


def validate(value: Any, expected_id: str | None = None) -> list[str]:
    return validate_current(value, expected_id)


def valid(value: dict[str, Any], expected_id: str | None = None) -> dict[str, Any]:
    errors = validate_current(value, expected_id)
    if errors:
        raise RuntimeError(errors[0])
    return value


def require_current(value: dict[str, Any], expected_id: str | None = None) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("schemaVersion") != CURRENT_SCHEMA_VERSION:
        raise RuntimeError("CONTINUATION_SCHEMA_NOT_CURRENT")
    return valid(value, expected_id)


def operational_view(value: dict[str, Any]) -> dict[str, Any]:
    value = valid(value, value.get("id") if isinstance(value, dict) else None)
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


def inventory_state(items: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(items, dict):
        raise RuntimeError("WORK_AUTHORITY_INVENTORY_INVALID")
    ordered: list[dict[str, Any]] = []
    for cid in sorted(items):
        if not ID_RE.fullmatch(str(cid)):
            raise RuntimeError("WORK_AUTHORITY_INVENTORY_ID_INVALID")
        value = valid(items[cid], cid)
        ordered.append(copy.deepcopy(value))
    return {"schemaVersion": INVENTORY_SCHEMA_VERSION, "items": ordered}


def inventory_items(value: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict) or set(value) != {"schemaVersion", "items"}:
        raise RuntimeError("WORK_AUTHORITY_INVENTORY_FIELDS_INVALID")
    if value.get("schemaVersion") != INVENTORY_SCHEMA_VERSION or not isinstance(value.get("items"), list):
        raise RuntimeError("WORK_AUTHORITY_INVENTORY_SCHEMA_INVALID")
    out: dict[str, dict[str, Any]] = {}
    for item in value["items"]:
        if not isinstance(item, dict):
            raise RuntimeError("WORK_AUTHORITY_INVENTORY_ITEM_INVALID")
        cid = item.get("id")
        if not isinstance(cid, str) or not ID_RE.fullmatch(cid) or cid in out:
            raise RuntimeError("WORK_AUTHORITY_INVENTORY_ID_INVALID")
        out[cid] = copy.deepcopy(valid(item, cid))
    if list(out) != sorted(out):
        raise RuntimeError("WORK_AUTHORITY_INVENTORY_ORDER_INVALID")
    return out
