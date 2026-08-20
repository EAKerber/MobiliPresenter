#!/usr/bin/env python3
"""Operational policy derived from ProjectMachine + RoutineInspection lineage."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import project_machine, routines
from tools.canonical import stable_hash
from tools.semantics.actions import OperationalAction

ERROR_EXIT = 2
SCHEMA_VERSION = "MaintenanceInspection 0.6"
ACTIONS = tuple(item.value for item in OperationalAction)
ACTION_PRIORITY = {"CONTINUE": 0, "HANDOFF": 1, "PAUSE": 2, "RECONCILE": 3, "NEEDS_HUMAN": 4}
TOP_FIELDS = {
    "schemaVersion",
    "repository",
    "projectMachineInspectionHash",
    "routineInspectionHash",
    "findings",
    "recommendation",
    "readOnly",
    "inspectionHash",
}
RECOMMENDATION_FIELDS = {
    "action", "reasonCode", "focus", "detail", "decisionScope",
    "semanticAuthority", "allowedActions", "workId", "targetWorkerId",
}
ROUTINE_ACTIONS = {
    "CAPABILITY_GATES_DUE": "CONTINUE",
    "CAPABILITY_EMPTY_REVIEW_DUE": "CONTINUE",
    "CAPABILITY_EMPTY_LIMIT": "NEEDS_HUMAN",
}


def finding(action, code, detail, subject=None, *, work_id=None, target_worker_id=None):
    try:
        action = OperationalAction.parse(str(action)).value
    except RuntimeError as exc:
        raise RuntimeError("MAINTENANCE_ACTION_INVALID") from exc
    value = {"action": action, "code": str(code), "detail": str(detail)}
    if subject is not None:
        value["subject"] = subject
    if work_id is not None:
        value["workId"] = work_id
    if target_worker_id is not None:
        value["targetWorkerId"] = target_worker_id
    return value


def _sensor_data(machine, name):
    sensors = machine.get("sensors")
    if not isinstance(sensors, dict) or not isinstance(sensors.get(name), dict):
        raise RuntimeError(f"PROJECT_MACHINE_SENSOR_MISSING:{name}")
    data = sensors[name].get("data")
    if not isinstance(data, dict):
        raise RuntimeError(f"PROJECT_MACHINE_SENSOR_DATA_INVALID:{name}")
    return data


def _sensor_focus(name):
    return {
        "pullRequests": "github",
        "coordination": "coordination-leases",
        "continuations": "work",
        "projectState": "repository",
        "publication": "publication",
        "control": "main",
    }.get(name, name)


def _coherence_focus(check):
    code = str(check.get("code") or "")
    detail = check.get("detail") if isinstance(check.get("detail"), dict) else {}
    if code == "UNCLASSIFIED_OPEN_PR":
        items = detail.get("unclassified") if isinstance(detail.get("unclassified"), list) else []
        if items and isinstance(items[0], dict) and isinstance(items[0].get("number"), int):
            return f"pr:{items[0]['number']}"
    if code.startswith("LEASE_OWNER_"):
        return "coordination-leases"
    if code.startswith("WORK_"):
        return "work"
    subjects = check.get("subjects") if isinstance(check.get("subjects"), list) else []
    return str(subjects[0]) if subjects else None


def _machine_findings(machine):
    out = []
    sensors = machine.get("sensors") if isinstance(machine.get("sensors"), dict) else {}
    for name in ("continuations", "coordination"):
        sensor = sensors.get(name) if isinstance(sensors.get(name), dict) else None
        if sensor is None or sensor.get("required") is True:
            continue
        status = str(sensor.get("status") or "UNKNOWN").upper()
        if status != "PASS":
            out.append(
                finding(
                    "PAUSE",
                    sensor.get("code") or "AUTHORITY_NOT_OBSERVED_IN_SCOPE",
                    f"branch-backed authority {name} was not observed in this inspection scope",
                    _sensor_focus(name),
                )
            )
    trust = machine.get("trust") if isinstance(machine.get("trust"), dict) else {}
    status = str(trust.get("status") or "UNKNOWN").upper()
    names = trust.get("failedSensors") if status == "FAIL" else trust.get("unknownSensors")
    action = "RECONCILE" if status == "FAIL" else ("NEEDS_HUMAN" if status == "UNKNOWN" else None)
    if action:
        for name in names or ["project-machine"]:
            sensor = sensors.get(name) if isinstance(sensors.get(name), dict) else {}
            code = sensor.get("code") or (
                "PROJECT_MACHINE_FAILED" if status == "FAIL" else "PROJECT_MACHINE_INCOMPLETE"
            )
            out.append(
                finding(
                    action,
                    code,
                    f"factual sensor {name} status is {status}",
                    _sensor_focus(str(name)),
                )
            )
    coherence = machine.get("coherence") if isinstance(machine.get("coherence"), dict) else {}
    for check in coherence.get("checks") or []:
        if not isinstance(check, dict) or check.get("required") is not True:
            continue
        check_status = str(check.get("status") or "UNKNOWN").upper()
        if check_status not in {"FAIL", "UNKNOWN"}:
            continue
        action = "RECONCILE" if check_status == "FAIL" else "NEEDS_HUMAN"
        detail = check.get("detail")
        rendered = (
            json.dumps(detail, sort_keys=True, ensure_ascii=False)
            if detail is not None
            else str(check.get("id"))
        )
        out.append(
            finding(
                action,
                check.get("code") or "PROJECT_COHERENCE_UNKNOWN",
                rendered,
                _coherence_focus(check),
            )
        )
    return out


def _work_items(machine):
    data = _sensor_data(machine, "continuations")
    items = data.get("items") if isinstance(data.get("items"), list) else []
    if any(not isinstance(item, dict) for item in items):
        raise RuntimeError("PROJECT_MACHINE_WORK_ITEMS_INVALID")
    return items


def _work_item(items, work_id):
    for item in items:
        if item.get("id") == work_id:
            return item
    raise RuntimeError("MAINTENANCE_WORK_ITEM_MISSING")


def _pull_requests(machine):
    data = _sensor_data(machine, "pullRequests")
    items = data.get("items") if isinstance(data.get("items"), list) else []
    return data.get("available") is True, [item for item in items if isinstance(item, dict)]


def _work_selection(machine, work_items):
    graph = machine["workGraph"]
    handoffs = sorted(str(work_id) for work_id in graph.get("handoffRequired") or [])
    if handoffs:
        work_id = handoffs[0]
        item = _work_item(work_items, work_id)
        target = item.get("handoffToWorkerId")
        if not isinstance(target, str) or not target:
            raise RuntimeError("MAINTENANCE_HANDOFF_TARGET_INVALID")
        return [
            finding(
                "HANDOFF",
                "WORK_HANDOFF_REQUIRED",
                f"handoff to {target}: {item.get('nextAction') or 'resume work'}",
                f"work:{work_id}",
                work_id=work_id,
                target_worker_id=target,
            )
        ]

    runnable = sorted(str(work_id) for work_id in graph.get("runnable") or [])
    if not runnable:
        return []
    pr_available, prs = _pull_requests(machine)
    by_number = {item.get("number"): item for item in prs if isinstance(item.get("number"), int)}
    ready = []
    blocked = []
    for work_id in runnable:
        item = _work_item(work_items, work_id)
        target = item.get("workerId")
        if not isinstance(target, str) or not target:
            raise RuntimeError("MAINTENANCE_WORKER_ID_INVALID")
        pr_number = item.get("prNumber")
        if not isinstance(pr_number, int):
            ready.append((work_id, target, item))
            continue
        if not pr_available:
            continue
        pr = by_number.get(pr_number)
        if pr is None:
            continue
        ci = str(pr.get("ci") or "unknown").lower()
        observed = pr.get("ciObserved") is True
        if ci == "green" and observed:
            ready.append((work_id, target, item))
        elif ci == "failed":
            blocked.append(
                finding(
                    "RECONCILE",
                    "WORK_PR_CI_FAILED",
                    f"PR #{pr_number} CI is failed",
                    f"work:{work_id}",
                    work_id=work_id,
                    target_worker_id=target,
                )
            )
        elif ci == "pending":
            blocked.append(
                finding(
                    "PAUSE",
                    "WORK_PR_CI_PENDING",
                    f"PR #{pr_number} CI is pending",
                    f"work:{work_id}",
                    work_id=work_id,
                    target_worker_id=target,
                )
            )
        else:
            blocked.append(
                finding(
                    "NEEDS_HUMAN",
                    "WORK_PR_CI_UNKNOWN",
                    f"PR #{pr_number} CI could not be established",
                    f"work:{work_id}",
                    work_id=work_id,
                    target_worker_id=target,
                )
            )
    if ready:
        work_id, target, item = sorted(ready, key=lambda entry: entry[0])[0]
        return [
            finding(
                "CONTINUE",
                "WORK_RUNNABLE",
                item.get("nextAction") or "finish and mark done",
                f"work:{work_id}",
                work_id=work_id,
                target_worker_id=target,
            )
        ]
    return blocked


def _pending_work_pause(work_items, graph):
    candidates = []
    for item in work_items:
        work_id = str(item.get("id") or "")
        if item.get("status") == "WAITING":
            candidates.append(
                (work_id, "WORK_WAITING", "; ".join(str(v) for v in item.get("blockers") or []))
            )
    for work_id in graph.get("dependencyBlocked") or []:
        item = _work_item(work_items, work_id)
        pending = [
            dep
            for dep in item.get("dependsOn") or []
            if dep not in set(graph.get("terminal") or [])
        ]
        candidates.append(
            (
                str(work_id),
                "WORK_DEPENDENCY_BLOCKED",
                f"waiting for dependencies: {', '.join(sorted(str(v) for v in pending))}",
            )
        )
    if not candidates:
        return None
    work_id, code, detail = sorted(candidates, key=lambda entry: entry[0])[0]
    return finding("PAUSE", code, detail, f"work:{work_id}", work_id=work_id)


def _routine_findings(routine_inspection):
    """Translate routine facts into operational policy; routines never emit actions."""
    out = []
    status = str(routine_inspection.get("status") or "UNKNOWN").upper()
    if status == "FAIL":
        out.append(
            finding(
                "RECONCILE",
                "ROUTINE_INSPECTION_FAILED",
                "one or more required recurring routine evaluations failed",
                "routines",
            )
        )
    elif status == "UNKNOWN":
        out.append(
            finding(
                "NEEDS_HUMAN",
                "ROUTINE_INSPECTION_INCOMPLETE",
                "one or more required recurring routine evaluations are unknown",
                "routines",
            )
        )
    elif status != "PASS":
        raise RuntimeError("MAINTENANCE_ROUTINE_STATUS_INVALID")

    results = routine_inspection.get("results")
    if not isinstance(results, list):
        raise RuntimeError("MAINTENANCE_ROUTINE_RESULTS_INVALID")
    for result in results:
        if not isinstance(result, dict):
            raise RuntimeError("MAINTENANCE_ROUTINE_RESULT_INVALID")
        findings = result.get("findings")
        if not isinstance(findings, list):
            raise RuntimeError("MAINTENANCE_ROUTINE_FINDINGS_INVALID")
        for item in findings:
            if not isinstance(item, dict):
                raise RuntimeError("MAINTENANCE_ROUTINE_FINDING_INVALID")
            if item.get("supervisorEligible") is not True:
                continue
            code = str(item.get("code") or "")
            action = ROUTINE_ACTIONS.get(code)
            if action is None:
                raise RuntimeError(f"MAINTENANCE_ROUTINE_FINDING_UNSUPPORTED:{code}")
            out.append(finding(action, code, item.get("detail"), item.get("subject")))
    return out


def decide(machine, routine_inspection):
    findings = _machine_findings(machine)
    work_items = _work_items(machine)
    selection = _work_selection(machine, work_items)
    findings.extend(selection)
    findings.extend(_routine_findings(routine_inspection))
    if not selection and not any(item.get("action") in {"CONTINUE", "HANDOFF"} for item in findings):
        pending = _pending_work_pause(work_items, machine["workGraph"])
        if pending is not None:
            findings.append(pending)
    if not findings:
        findings.append(
            finding(
                "CONTINUE",
                "NEXT_TRANSITION_AVAILABLE",
                machine["project"]["nextTransition"],
                "development",
            )
        )
    indexed = list(enumerate(findings))
    _, best = max(indexed, key=lambda pair: (ACTION_PRIORITY[pair[1]["action"]], -pair[0]))
    recommendation = {
        "action": best["action"],
        "reasonCode": best["code"],
        "focus": best.get("subject"),
        "detail": best["detail"],
        "decisionScope": "operational-only",
        "semanticAuthority": False,
        "allowedActions": list(ACTIONS),
        "workId": best.get("workId"),
        "targetWorkerId": best.get("targetWorkerId"),
    }
    return findings, recommendation


def from_inputs(machine, routine_inspection):
    project_machine.validate_inspection(machine)
    routines.validate_inspection(routine_inspection, machine)
    findings, recommendation = decide(machine, routine_inspection)
    body = {
        "schemaVersion": SCHEMA_VERSION,
        "repository": machine["repository"],
        "projectMachineInspectionHash": machine["inspectionHash"],
        "routineInspectionHash": routine_inspection["inspectionHash"],
        "findings": findings,
        "recommendation": recommendation,
        "readOnly": True,
    }
    return {**body, "inspectionHash": stable_hash(body)}


def from_project_inspection(machine):
    """Convenience wrapper; canonical workflows materialize RoutineInspection explicitly."""
    project_machine.validate_inspection(machine)
    return from_inputs(machine, routines.build_inspection(machine))


def validate_inspection(value):
    if not isinstance(value, dict) or set(value) != TOP_FIELDS:
        raise RuntimeError("MAINTENANCE_INPUT_INVALID")
    if value.get("schemaVersion") != SCHEMA_VERSION:
        raise RuntimeError("MAINTENANCE_SCHEMA_UNSUPPORTED")
    if value.get("repository") != project_machine.REPOSITORY:
        raise RuntimeError("MAINTENANCE_REPOSITORY_MISMATCH")
    source_hash = value.get("projectMachineInspectionHash")
    if (
        not isinstance(source_hash, str)
        or len(source_hash) != 64
        or any(c not in "0123456789abcdef" for c in source_hash)
    ):
        raise RuntimeError("MAINTENANCE_PROJECT_MACHINE_HASH_INVALID")
    routine_hash = value.get("routineInspectionHash")
    if (
        not isinstance(routine_hash, str)
        or len(routine_hash) != 64
        or any(c not in "0123456789abcdef" for c in routine_hash)
    ):
        raise RuntimeError("MAINTENANCE_ROUTINE_HASH_INVALID")
    if value.get("readOnly") is not True or not isinstance(value.get("findings"), list):
        raise RuntimeError("MAINTENANCE_BOUNDARY_INVALID")
    rec = value.get("recommendation")
    if not isinstance(rec, dict) or set(rec) != RECOMMENDATION_FIELDS or rec.get("action") not in ACTIONS:
        raise RuntimeError("MAINTENANCE_RECOMMENDATION_INVALID")
    if (
        rec.get("decisionScope") != "operational-only"
        or rec.get("semanticAuthority") is not False
        or rec.get("allowedActions") != list(ACTIONS)
    ):
        raise RuntimeError("MAINTENANCE_SEMANTIC_AUTHORITY_INVALID")
    if rec.get("workId") is not None and (
        not isinstance(rec.get("workId"), str) or not rec["workId"]
    ):
        raise RuntimeError("MAINTENANCE_WORK_ID_INVALID")
    if rec.get("targetWorkerId") is not None and (
        not isinstance(rec.get("targetWorkerId"), str) or not rec["targetWorkerId"]
    ):
        raise RuntimeError("MAINTENANCE_TARGET_WORKER_INVALID")
    supplied = value.get("inspectionHash")
    body = {key: item for key, item in value.items() if key != "inspectionHash"}
    if not isinstance(supplied, str) or supplied != stable_hash(body):
        raise RuntimeError("MAINTENANCE_HASH_MISMATCH")
    return {
        "ok": True,
        "inspectionHash": supplied,
        "projectMachineInspectionHash": source_hash,
        "routineInspectionHash": routine_hash,
    }


def validate_derivation(value, machine, routine_inspection):
    project_machine.validate_inspection(machine)
    routines.validate_inspection(routine_inspection, machine)
    validate_inspection(value)
    if value.get("routineInspectionHash") != routine_inspection["inspectionHash"]:
        raise RuntimeError("MAINTENANCE_ROUTINE_MISMATCH")
    if value != from_inputs(machine, routine_inspection):
        raise RuntimeError("MAINTENANCE_DERIVATION_MISMATCH")
    return {
        "ok": True,
        "inspectionHash": value["inspectionHash"],
        "projectMachineInspectionHash": machine["inspectionHash"],
        "routineInspectionHash": routine_inspection["inspectionHash"],
    }


def load_json(path):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("MAINTENANCE_INPUT_INVALID") from exc
    if not isinstance(value, dict):
        raise RuntimeError("MAINTENANCE_INPUT_INVALID")
    return value


def inspect_scope(scope):
    if scope == "local":
        machine = project_machine.inspect_local()
    elif scope == "base":
        machine = project_machine.inspect_base()
    elif scope == "live":
        machine = project_machine.inspect_live()
    else:
        raise RuntimeError("MAINTENANCE_SCOPE_INVALID")
    routine_inspection = routines.build_inspection(machine)
    return from_inputs(machine, routine_inspection)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="maintenance-inspect")
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("--input")
    group.add_argument("--local", action="store_true")
    group.add_argument("--base", action="store_true")
    group.add_argument("--live", action="store_true")
    parser.add_argument("--routines")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    try:
        if args.input:
            if not args.routines:
                raise RuntimeError("MAINTENANCE_ROUTINES_REQUIRED")
            payload = from_inputs(load_json(args.input), load_json(args.routines))
        else:
            if args.routines:
                raise RuntimeError("MAINTENANCE_ROUTINES_WITHOUT_INPUT")
            payload = inspect_scope("live" if args.live else ("base" if args.base else "local"))
        if args.as_json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(
                "MAINTENANCE INSPECT\n"
                f"  recommendation: {payload['recommendation']['action']}\n"
                f"  reason: {payload['recommendation']['reasonCode']}\n"
                f"  focus: {payload['recommendation']['focus']}\n"
                f"  source ProjectMachine: {payload['projectMachineInspectionHash']}\n"
                f"  source RoutineInspection: {payload['routineInspectionHash']}"
            )
        return 0
    except RuntimeError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return ERROR_EXIT


if __name__ == "__main__":
    raise SystemExit(main())
