#!/usr/bin/env python3
"""Deterministic read-only routing plan derived from one MaintenanceInspection."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import maintenance_inspect
from tools.canonical import stable_hash
from tools.semantics.actions import OperationalAction

ERROR_EXIT = 2
SCHEMA_VERSION = "SchedulerPlan 0.2"
ACTIONS = {item.value for item in OperationalAction}


def route(value):
    rec = value["recommendation"]
    action = OperationalAction.parse(rec["action"]).value
    work_id = rec.get("workId")
    target = rec.get("targetWorkerId")
    if action == OperationalAction.HANDOFF.value:
        if not isinstance(work_id, str) or not work_id or not isinstance(target, str) or not target:
            raise RuntimeError("SCHEDULER_HANDOFF_TARGET_INVALID")
        return {"shouldWake": True, "channelClass": "worker", "target": target, "workId": work_id}
    if action == OperationalAction.CONTINUE.value:
        if work_id is not None:
            if not isinstance(work_id, str) or not work_id or not isinstance(target, str) or not target:
                raise RuntimeError("SCHEDULER_CONTINUE_TARGET_INVALID")
            return {"shouldWake": True, "channelClass": "worker", "target": target, "workId": work_id}
        return {"shouldWake": True, "channelClass": "supervisor", "target": "gitops-supervisor", "workId": None}
    if action == OperationalAction.RECONCILE.value:
        return {"shouldWake": True, "channelClass": "supervisor", "target": "gitops-supervisor", "workId": work_id}
    if action == OperationalAction.PAUSE.value:
        return {"shouldWake": False, "channelClass": "none", "target": None, "workId": work_id}
    if action == OperationalAction.NEEDS_HUMAN.value:
        return {"shouldWake": True, "channelClass": "human", "target": "human", "workId": work_id}
    raise RuntimeError("SCHEDULER_ACTION_INVALID")


def build_plan(value):
    maintenance_inspect.validate_inspection(value)
    rec = value["recommendation"]
    body = {"schemaVersion": SCHEMA_VERSION, "inspectionHash": value["inspectionHash"], "action": rec["action"], "reasonCode": str(rec.get("reasonCode") or "UNKNOWN"), "focus": rec.get("focus"), "dispatch": route(value), "decisionScope": "operational-only", "semanticAuthority": False, "transportSideEffects": False, "readOnly": True}
    return {**body, "planHash": stable_hash(body)}


def validate_plan(value):
    if not isinstance(value, dict):
        raise RuntimeError("SCHEDULER_PLAN_INVALID")
    if value.get("schemaVersion") != SCHEMA_VERSION:
        raise RuntimeError("SCHEDULER_PLAN_SCHEMA_UNSUPPORTED")
    if value.get("readOnly") is not True or value.get("transportSideEffects") is not False:
        raise RuntimeError("SCHEDULER_PLAN_BOUNDARY_INVALID")
    if value.get("semanticAuthority") is not False or value.get("decisionScope") != "operational-only":
        raise RuntimeError("SCHEDULER_PLAN_SEMANTIC_AUTHORITY_INVALID")
    if value.get("action") not in ACTIONS:
        raise RuntimeError("SCHEDULER_PLAN_ACTION_INVALID")
    dispatch = value.get("dispatch")
    if not isinstance(dispatch, dict) or dispatch.get("channelClass") not in {"worker", "supervisor", "human", "none"} or not isinstance(dispatch.get("shouldWake"), bool):
        raise RuntimeError("SCHEDULER_PLAN_DISPATCH_INVALID")
    supplied = value.get("planHash")
    body = {k: v for k, v in value.items() if k != "planHash"}
    if not isinstance(supplied, str) or supplied != stable_hash(body):
        raise RuntimeError("SCHEDULER_PLAN_HASH_MISMATCH")
    if not isinstance(value.get("inspectionHash"), str):
        raise RuntimeError("SCHEDULER_PLAN_INSPECTION_HASH_INVALID")
    return {"ok": True, "planHash": supplied, "inspectionHash": value["inspectionHash"]}


def validate_derivation(value, inspection):
    maintenance_inspect.validate_inspection(inspection)
    validate_plan(value)
    if value != build_plan(inspection):
        raise RuntimeError("SCHEDULER_PLAN_DERIVATION_MISMATCH")
    return {"ok": True, "planHash": value["planHash"], "inspectionHash": inspection["inspectionHash"]}


def load_json(path):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("SCHEDULER_INPUT_INVALID") from exc
    if not isinstance(value, dict):
        raise RuntimeError("SCHEDULER_INPUT_INVALID")
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(prog="scheduler-plan", description="Read-only Scheduler routing plan")
    parser.add_argument("--input", required=True)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    try:
        payload = build_plan(load_json(args.input))
        print(json.dumps(payload, indent=2 if args.as_json else None, ensure_ascii=False))
        return 0
    except RuntimeError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return ERROR_EXIT


if __name__ == "__main__":
    raise SystemExit(main())
