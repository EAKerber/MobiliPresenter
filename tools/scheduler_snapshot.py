#!/usr/bin/env python3
"""Validate a canonical Scheduler snapshot without GitHub/network access."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ERROR_EXIT = 2
REPOSITORY = "EAKerber/MobiliPresenter"
SNAPSHOT_SCHEMA = "SchedulerSnapshot 0.1"


def stable_hash(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_json(path: str) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("SCHEDULER_SNAPSHOT_INPUT_INVALID") from exc
    if not isinstance(value, dict):
        raise RuntimeError("SCHEDULER_SNAPSHOT_INPUT_INVALID")
    return value


def require_sha(value: Any, code: str) -> str:
    if not isinstance(value, str) or len(value) != 40 or any(c not in "0123456789abcdef" for c in value):
        raise RuntimeError(code)
    return value


def validate_snapshot(
    value: dict[str, Any],
    *,
    expected_control_head: str,
    expected_coordination_head: str,
    expected_continuation_head: str,
) -> dict[str, Any]:
    if value.get("schemaVersion") != SNAPSHOT_SCHEMA:
        raise RuntimeError("SCHEDULER_SNAPSHOT_SCHEMA_UNSUPPORTED")
    if value.get("repository") != REPOSITORY:
        raise RuntimeError("SCHEDULER_SNAPSHOT_REPOSITORY_MISMATCH")
    if value.get("readOnly") is not True:
        raise RuntimeError("SCHEDULER_SNAPSHOT_NOT_READ_ONLY")

    supplied_snapshot_hash = value.get("snapshotHash")
    body = {k: v for k, v in value.items() if k != "snapshotHash"}
    if not isinstance(supplied_snapshot_hash, str) or supplied_snapshot_hash != stable_hash(body):
        raise RuntimeError("SCHEDULER_SNAPSHOT_HASH_MISMATCH")

    inspection = value.get("inspection")
    if not isinstance(inspection, dict) or inspection.get("schemaVersion") != "MaintenanceInspection 0.3":
        raise RuntimeError("SCHEDULER_SNAPSHOT_INSPECTION_INVALID")
    if inspection.get("readOnly") is not True:
        raise RuntimeError("SCHEDULER_SNAPSHOT_INSPECTION_NOT_READ_ONLY")
    supplied_inspection_hash = inspection.get("inspectionHash")
    inspection_body = {k: v for k, v in inspection.items() if k != "inspectionHash"}
    if not isinstance(supplied_inspection_hash, str) or supplied_inspection_hash != stable_hash(inspection_body):
        raise RuntimeError("SCHEDULER_SNAPSHOT_INSPECTION_HASH_MISMATCH")

    plan = value.get("plan")
    if not isinstance(plan, dict) or plan.get("schemaVersion") != "SchedulerPlan 0.2":
        raise RuntimeError("SCHEDULER_SNAPSHOT_PLAN_INVALID")
    if plan.get("readOnly") is not True or plan.get("transportSideEffects") is not False or plan.get("semanticAuthority") is not False:
        raise RuntimeError("SCHEDULER_SNAPSHOT_PLAN_BOUNDARY_INVALID")
    supplied_plan_hash = plan.get("planHash")
    plan_body = {k: v for k, v in plan.items() if k != "planHash"}
    if not isinstance(supplied_plan_hash, str) or supplied_plan_hash != stable_hash(plan_body):
        raise RuntimeError("SCHEDULER_SNAPSHOT_PLAN_HASH_MISMATCH")
    if plan.get("inspectionHash") != supplied_inspection_hash:
        raise RuntimeError("SCHEDULER_SNAPSHOT_PLAN_INSPECTION_MISMATCH")

    heads = value.get("sourceHeads")
    if not isinstance(heads, dict):
        raise RuntimeError("SCHEDULER_SNAPSHOT_SOURCE_HEADS_INVALID")
    control = require_sha(heads.get("control"), "SCHEDULER_SNAPSHOT_CONTROL_HEAD_INVALID")
    coordination = require_sha(heads.get("coordination"), "SCHEDULER_SNAPSHOT_COORDINATION_HEAD_INVALID")
    continuation = require_sha(heads.get("continuation"), "SCHEDULER_SNAPSHOT_CONTINUATION_HEAD_INVALID")

    observed_git = inspection.get("observedGit") if isinstance(inspection.get("observedGit"), dict) else {}
    observed_coordination = inspection.get("coordination") if isinstance(inspection.get("coordination"), dict) else {}
    observed_continuation = inspection.get("continuationAuthority") if isinstance(inspection.get("continuationAuthority"), dict) else {}
    if control != observed_git.get("head"):
        raise RuntimeError("SCHEDULER_SNAPSHOT_CONTROL_INTERNAL_MISMATCH")
    if coordination != observed_coordination.get("authorityHead"):
        raise RuntimeError("SCHEDULER_SNAPSHOT_COORDINATION_INTERNAL_MISMATCH")
    if continuation != observed_continuation.get("authorityHead"):
        raise RuntimeError("SCHEDULER_SNAPSHOT_CONTINUATION_INTERNAL_MISMATCH")

    expected_control = require_sha(expected_control_head, "SCHEDULER_SNAPSHOT_EXPECTED_CONTROL_HEAD_INVALID")
    expected_coordination = require_sha(expected_coordination_head, "SCHEDULER_SNAPSHOT_EXPECTED_COORDINATION_HEAD_INVALID")
    expected_continuation = require_sha(expected_continuation_head, "SCHEDULER_SNAPSHOT_EXPECTED_CONTINUATION_HEAD_INVALID")
    if control != expected_control:
        raise RuntimeError("SCHEDULER_SNAPSHOT_STALE_CONTROL")
    if coordination != expected_coordination:
        raise RuntimeError("SCHEDULER_SNAPSHOT_STALE_COORDINATION")
    if continuation != expected_continuation:
        raise RuntimeError("SCHEDULER_SNAPSHOT_STALE_CONTINUATION")

    return {
        "ok": True,
        "snapshotHash": supplied_snapshot_hash,
        "inspectionHash": supplied_inspection_hash,
        "planHash": supplied_plan_hash,
        "sourceHeads": heads,
        "dispatch": plan.get("dispatch"),
        "plan": plan,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scheduler-snapshot", description="Offline Scheduler snapshot validation")
    parser.add_argument("snapshot")
    parser.add_argument("--expected-control-head", required=True)
    parser.add_argument("--expected-coordination-head", required=True)
    parser.add_argument("--expected-continuation-head", required=True)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    try:
        result = validate_snapshot(
            load_json(args.snapshot),
            expected_control_head=args.expected_control_head,
            expected_coordination_head=args.expected_coordination_head,
            expected_continuation_head=args.expected_continuation_head,
        )
        print(json.dumps(result, indent=2 if args.as_json else None, ensure_ascii=False))
        return 0
    except RuntimeError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return ERROR_EXIT


if __name__ == "__main__":
    raise SystemExit(main())
