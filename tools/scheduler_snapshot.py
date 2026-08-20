#!/usr/bin/env python3
"""Build and validate Scheduler snapshots with explicit routine/source/readback lineage."""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import maintenance_inspect, project_machine, routines, scheduler_plan
from tools.canonical import stable_hash

ERROR_EXIT = 2
REPOSITORY = "EAKerber/MobiliPresenter"
SNAPSHOT_SCHEMA = "SchedulerSnapshot 0.3"
HEAD_KEYS = ("inspection", "control", "coordination", "continuation")
CURRENT_HEAD_KEYS = ("control", "coordination", "continuation")


def load_json(path):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("SCHEDULER_SNAPSHOT_INPUT_INVALID") from exc
    if not isinstance(value, dict):
        raise RuntimeError("SCHEDULER_SNAPSHOT_INPUT_INVALID")
    return value


def _valid_hash(value, *, length=64):
    return (
        isinstance(value, str)
        and len(value) == length
        and not any(c not in "0123456789abcdef" for c in value)
    )


def _validate_source_heads(heads):
    if not isinstance(heads, dict):
        raise RuntimeError("SCHEDULER_SNAPSHOT_SOURCE_HEADS_INVALID")
    for name in HEAD_KEYS:
        entry = heads.get(name)
        if not isinstance(entry, dict):
            raise RuntimeError(f"SCHEDULER_SNAPSHOT_{name.upper()}_SOURCE_INVALID")
        sha = entry.get("sha")
        if sha is not None and not _valid_hash(sha, length=40):
            raise RuntimeError(f"SCHEDULER_SNAPSHOT_{name.upper()}_HEAD_INVALID")
        branch = entry.get("branch")
        if branch is not None and not isinstance(branch, str):
            raise RuntimeError(f"SCHEDULER_SNAPSHOT_{name.upper()}_BRANCH_INVALID")
    return heads


def _validate_expected_heads(expected_heads):
    if not isinstance(expected_heads, dict) or set(expected_heads) != set(CURRENT_HEAD_KEYS):
        raise RuntimeError("SCHEDULER_SNAPSHOT_EXPECTED_HEADS_INVALID")
    normalized = {}
    for name in CURRENT_HEAD_KEYS:
        sha = expected_heads.get(name)
        if not _valid_hash(sha, length=40):
            raise RuntimeError(f"SCHEDULER_SNAPSHOT_EXPECTED_{name.upper()}_HEAD_INVALID")
        normalized[name] = sha
    return normalized


def build_snapshot(machine, routine_inspection, inspection, plan):
    project_machine.validate_inspection(machine)
    routines.validate_inspection(routine_inspection, machine)
    maintenance_inspect.validate_derivation(inspection, machine, routine_inspection)
    scheduler_plan.validate_derivation(plan, inspection)
    heads = copy.deepcopy(machine["sourceHeads"])
    _validate_source_heads(heads)
    body = {
        "schemaVersion": SNAPSHOT_SCHEMA,
        "repository": REPOSITORY,
        "projectMachineInspectionHash": machine["inspectionHash"],
        "routineInspectionHash": routine_inspection["inspectionHash"],
        "sourceHeads": heads,
        "inspection": copy.deepcopy(inspection),
        "plan": copy.deepcopy(plan),
        "readOnly": True,
        "semanticAuthority": False,
        "transportSideEffects": False,
    }
    return {**body, "snapshotHash": stable_hash(body)}


def _validate_snapshot_intrinsic(value):
    if not isinstance(value, dict):
        raise RuntimeError("SCHEDULER_SNAPSHOT_INPUT_INVALID")
    expected_fields = {
        "schemaVersion",
        "repository",
        "projectMachineInspectionHash",
        "routineInspectionHash",
        "sourceHeads",
        "inspection",
        "plan",
        "readOnly",
        "semanticAuthority",
        "transportSideEffects",
        "snapshotHash",
    }
    if set(value) != expected_fields:
        raise RuntimeError("SCHEDULER_SNAPSHOT_FIELDS_INVALID")
    if value.get("schemaVersion") != SNAPSHOT_SCHEMA:
        raise RuntimeError("SCHEDULER_SNAPSHOT_SCHEMA_UNSUPPORTED")
    if value.get("repository") != REPOSITORY:
        raise RuntimeError("SCHEDULER_SNAPSHOT_REPOSITORY_MISMATCH")
    if value.get("readOnly") is not True or value.get("transportSideEffects") is not False:
        raise RuntimeError("SCHEDULER_SNAPSHOT_BOUNDARY_INVALID")
    if value.get("semanticAuthority") is not False:
        raise RuntimeError("SCHEDULER_SNAPSHOT_SEMANTIC_AUTHORITY_INVALID")
    source_hash = value.get("projectMachineInspectionHash")
    if not _valid_hash(source_hash):
        raise RuntimeError("SCHEDULER_SNAPSHOT_PROJECT_MACHINE_HASH_INVALID")
    routine_hash = value.get("routineInspectionHash")
    if not _valid_hash(routine_hash):
        raise RuntimeError("SCHEDULER_SNAPSHOT_ROUTINE_HASH_INVALID")
    _validate_source_heads(value.get("sourceHeads"))
    inspection = value.get("inspection")
    plan = value.get("plan")
    maintenance_inspect.validate_inspection(inspection)
    scheduler_plan.validate_plan(plan)
    if inspection.get("projectMachineInspectionHash") != source_hash:
        raise RuntimeError("SCHEDULER_SNAPSHOT_MACHINE_MAINTENANCE_MISMATCH")
    if inspection.get("routineInspectionHash") != routine_hash:
        raise RuntimeError("SCHEDULER_SNAPSHOT_ROUTINE_MAINTENANCE_MISMATCH")
    if plan.get("inspectionHash") != inspection.get("inspectionHash"):
        raise RuntimeError("SCHEDULER_SNAPSHOT_PLAN_INSPECTION_MISMATCH")
    supplied = value.get("snapshotHash")
    body = {k: v for k, v in value.items() if k != "snapshotHash"}
    if not isinstance(supplied, str) or supplied != stable_hash(body):
        raise RuntimeError("SCHEDULER_SNAPSHOT_HASH_MISMATCH")
    return supplied


def validate_snapshot(
    value,
    *,
    source_machine,
    routine_inspection,
    readback_machine,
    expected_heads=None,
):
    supplied = _validate_snapshot_intrinsic(value)
    project_machine.validate_inspection(source_machine)
    project_machine.validate_inspection(readback_machine)
    routines.validate_inspection(routine_inspection, source_machine)
    if value["projectMachineInspectionHash"] != source_machine["inspectionHash"]:
        raise RuntimeError("SCHEDULER_SNAPSHOT_SOURCE_MACHINE_MISMATCH")
    if value["routineInspectionHash"] != routine_inspection["inspectionHash"]:
        raise RuntimeError("SCHEDULER_SNAPSHOT_ROUTINE_MISMATCH")
    if value["sourceHeads"] != source_machine["sourceHeads"]:
        raise RuntimeError("SCHEDULER_SNAPSHOT_SOURCE_HEADS_MISMATCH")
    maintenance_inspect.validate_derivation(
        value["inspection"], source_machine, routine_inspection
    )
    scheduler_plan.validate_derivation(value["plan"], value["inspection"])
    readback_heads = _validate_source_heads(readback_machine["sourceHeads"])
    stale = [name for name in HEAD_KEYS if value["sourceHeads"][name] != readback_heads[name]]
    if stale:
        raise RuntimeError("SCHEDULER_SNAPSHOT_STALE_" + "_".join(name.upper() for name in stale))
    if expected_heads is not None:
        current = _validate_expected_heads(expected_heads)
        stale_current = [
            name
            for name in CURRENT_HEAD_KEYS
            if value["sourceHeads"][name].get("sha") != current[name]
        ]
        if stale_current:
            raise RuntimeError(
                "SCHEDULER_SNAPSHOT_STALE_CURRENT_"
                + "_".join(name.upper() for name in stale_current)
            )
    return {
        "ok": True,
        "snapshotHash": supplied,
        "projectMachineInspectionHash": source_machine["inspectionHash"],
        "routineInspectionHash": routine_inspection["inspectionHash"],
        "inspectionHash": value["inspection"]["inspectionHash"],
        "planHash": value["plan"]["planHash"],
        "sourceHeads": value["sourceHeads"],
        "dispatch": value["plan"].get("dispatch"),
        "plan": value["plan"],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(prog="scheduler-snapshot")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--project-machine", required=True)
    build.add_argument("--routines", required=True)
    build.add_argument("--inspection", required=True)
    build.add_argument("--plan", required=True)
    build.add_argument("--json", action="store_true", dest="as_json")
    validate = sub.add_parser("validate")
    validate.add_argument("--snapshot", required=True)
    validate.add_argument("--source-machine", required=True)
    validate.add_argument("--routines", required=True)
    validate.add_argument("--readback-machine", required=True)
    validate.add_argument("--expected-control-head")
    validate.add_argument("--expected-coordination-head")
    validate.add_argument("--expected-continuation-head")
    validate.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            payload = build_snapshot(
                load_json(args.project_machine),
                load_json(args.routines),
                load_json(args.inspection),
                load_json(args.plan),
            )
        else:
            supplied_expected = [
                args.expected_control_head,
                args.expected_coordination_head,
                args.expected_continuation_head,
            ]
            if any(item is not None for item in supplied_expected) and not all(
                item is not None for item in supplied_expected
            ):
                raise RuntimeError("SCHEDULER_SNAPSHOT_EXPECTED_HEADS_INCOMPLETE")
            expected_heads = (
                None
                if all(item is None for item in supplied_expected)
                else {
                    "control": args.expected_control_head,
                    "coordination": args.expected_coordination_head,
                    "continuation": args.expected_continuation_head,
                }
            )
            payload = validate_snapshot(
                load_json(args.snapshot),
                source_machine=load_json(args.source_machine),
                routine_inspection=load_json(args.routines),
                readback_machine=load_json(args.readback_machine),
                expected_heads=expected_heads,
            )
        print(json.dumps(payload, indent=2 if args.as_json else None, ensure_ascii=False))
        return 0
    except RuntimeError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return ERROR_EXIT


if __name__ == "__main__":
    raise SystemExit(main())
