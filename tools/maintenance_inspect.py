#!/usr/bin/env python3
"""Operational policy derived from one ProjectMachineInspection."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import project_machine, work_graph as work_graph_module
from tools.canonical import stable_hash
from tools.semantics.actions import OperationalAction

ERROR_EXIT = 2
SCHEMA_VERSION = "MaintenanceInspection 0.4"
ACTIONS = tuple(item.value for item in OperationalAction)
ACTION_PRIORITY = {"CONTINUE": 0, "HANDOFF": 1, "PAUSE": 2, "RECONCILE": 3, "NEEDS_HUMAN": 4}


def finding(action, code, detail, subject=None):
    try:
        action = OperationalAction.parse(str(action)).value
    except RuntimeError as exc:
        raise RuntimeError("MAINTENANCE_ACTION_INVALID") from exc
    value = {"action": action, "code": code, "detail": detail}
    if subject is not None:
        value["subject"] = subject
    return value


def _sensor_focus(name):
    return {"pullRequests": "github", "coordination": "coordination-leases", "continuations": "continuations", "projectState": "repository", "publication": "publication", "control": "main"}.get(name, name)


def _coherence_focus(check):
    code = check.get("code")
    detail = check.get("detail") if isinstance(check.get("detail"), dict) else {}
    if code == "UNCLASSIFIED_OPEN_PR":
        items = detail.get("unclassified") if isinstance(detail.get("unclassified"), list) else []
        if items and isinstance(items[0], dict) and isinstance(items[0].get("number"), int):
            return f"pr:{items[0]['number']}"
    if isinstance(code, str) and code.startswith("ACTIVE_PR_"):
        return "development"
    if isinstance(code, str) and code.startswith("LEASE_OWNER_"):
        return "coordination-leases"
    if isinstance(code, str) and code.startswith("CONTINUATION_"):
        return "continuations"
    subjects = check.get("subjects") if isinstance(check.get("subjects"), list) else []
    return str(subjects[0]) if subjects else None


def _machine_findings(machine_trust=None, machine_coherence=None, machine_sensors=None):
    out = []
    sensors = machine_sensors if isinstance(machine_sensors, dict) else {}
    if isinstance(machine_trust, dict):
        status = str(machine_trust.get("status") or "UNKNOWN").upper()
        names = machine_trust.get("failedSensors") if status == "FAIL" else machine_trust.get("unknownSensors")
        action = "RECONCILE" if status == "FAIL" else ("NEEDS_HUMAN" if status == "UNKNOWN" else None)
        if action:
            for name in names or ["project-machine"]:
                sensor = sensors.get(name) if isinstance(sensors.get(name), dict) else {}
                code = sensor.get("code") or ("PROJECT_MACHINE_FAILED" if status == "FAIL" else "PROJECT_MACHINE_INCOMPLETE")
                out.append(finding(action, str(code), f"factual sensor {name} status is {status}", _sensor_focus(str(name))))
    if isinstance(machine_coherence, dict):
        for check in machine_coherence.get("checks") or []:
            if not isinstance(check, dict) or check.get("required") is not True:
                continue
            status = str(check.get("status") or "UNKNOWN").upper()
            if status not in {"FAIL", "UNKNOWN"}:
                continue
            action = "RECONCILE" if status == "FAIL" else "NEEDS_HUMAN"
            detail = check.get("detail")
            rendered = json.dumps(detail, sort_keys=True, ensure_ascii=False) if detail is not None else str(check.get("id"))
            out.append(finding(action, str(check.get("code") or "PROJECT_COHERENCE_UNKNOWN"), rendered, _coherence_focus(check)))
    return out


def _work_item(work_items, work_id):
    for item in work_items:
        if isinstance(item, dict) and item.get("id") == work_id:
            return item
    raise RuntimeError("MAINTENANCE_WORK_ITEM_MISSING")


def _work_candidate(work_items, graph):
    handoffs = sorted(str(item) for item in graph.get("handoffRequired") or [])
    if handoffs:
        work_id = handoffs[0]
        item = _work_item(work_items, work_id)
        target = item.get("handoffToWorkerId")
        if not isinstance(target, str) or not target:
            raise RuntimeError("MAINTENANCE_HANDOFF_TARGET_INVALID")
        return finding("HANDOFF", "WORK_HANDOFF_REQUIRED", f"handoff to {target}: {item.get('nextAction') or 'resume work'}", f"work:{work_id}")
    runnable = sorted(str(item) for item in graph.get("runnable") or [])
    if runnable:
        work_id = runnable[0]
        item = _work_item(work_items, work_id)
        return finding("CONTINUE", "WORK_RUNNABLE", item.get("nextAction") or "finish and mark done", f"work:{work_id}")
    return None


def _pending_work_pause(work_items, graph):
    candidates = []
    for item in work_items:
        if not isinstance(item, dict):
            continue
        work_id = str(item.get("id") or "")
        if item.get("status") == "WAITING":
            candidates.append((work_id, "WORK_WAITING", "; ".join(str(v) for v in item.get("blockers") or [])))
    for work_id in graph.get("dependencyBlocked") or []:
        item = _work_item(work_items, work_id)
        pending = [dep for dep in item.get("dependsOn") or [] if dep not in set(graph.get("terminal") or [])]
        candidates.append((str(work_id), "WORK_DEPENDENCY_BLOCKED", f"waiting for dependencies: {', '.join(sorted(str(v) for v in pending))}"))
    if not candidates:
        return None
    work_id, code, detail = sorted(candidates, key=lambda entry: entry[0])[0]
    return finding("PAUSE", code, detail, f"work:{work_id}")


def decide(state, verification, capabilities, *, remote_requested, pull_requests, coordination_state, work_items=None, work_graph=None, machine_trust=None, machine_coherence=None, machine_sensors=None):
    findings = _machine_findings(machine_trust, machine_coherence, machine_sensors)
    work_items = work_items or []
    graph = work_graph if isinstance(work_graph, dict) else work_graph_module.build(work_items)
    work_graph_module.validate(graph)
    if not verification.get("ok"):
        failed = [i.get("name") for i in verification.get("checks", []) if i.get("status") == "FAIL"]
        findings.append(finding("RECONCILE", "VERIFICATION_FAILED", f"failed checks: {', '.join(str(i) for i in failed)}", "repository"))
    blockers = state["development"].get("blockers") or []
    if blockers:
        findings.append(finding("PAUSE", "EXPLICIT_BLOCKERS", "; ".join(str(i) for i in blockers), "development"))
    work_candidate = _work_candidate(work_items, graph)
    if work_candidate is not None:
        findings.append(work_candidate)
    for item in capabilities:
        if item["policy"] != "experimental" or item.get("supervisorParticipation", "active") == "isolated":
            continue
        if item["reviewAction"] == "REVIEW_EMPTY_LIMIT":
            findings.append(finding("NEEDS_HUMAN", "CAPABILITY_EMPTY_LIMIT", "formal capability review reached its configured empty-round limit", item["id"]))
        elif item["reviewAction"] == "TEST_NEXT_GATES":
            findings.append(finding("CONTINUE", "CAPABILITY_GATES_DUE", f"next Gates: {', '.join(item['nextGates'])}", item["id"]))
        elif item["reviewAction"] == "REVIEW_EMPTY_ROUND":
            findings.append(finding("CONTINUE", "CAPABILITY_EMPTY_REVIEW_DUE", "re-evaluate the recorded deferral reason", item["id"]))
    if work_candidate is None and not any(item.get("action") in {"CONTINUE", "HANDOFF"} for item in findings):
        pending = _pending_work_pause(work_items, graph)
        if pending is not None:
            findings.append(pending)
    if remote_requested and pull_requests.get("available"):
        active_pr = state["development"].get("prNumber")
        if isinstance(active_pr, int):
            matches = [i for i in pull_requests.get("items", []) if i.get("number") == active_pr]
            if matches:
                ci = str(matches[0].get("ci") or "unknown")
                observed = matches[0].get("ciObserved") is True
                if ci == "failed":
                    findings.append(finding("RECONCILE", "ACTIVE_PR_CI_FAILED", f"PR #{active_pr} CI is failed", f"pr:{active_pr}"))
                elif ci == "pending":
                    findings.append(finding("PAUSE", "ACTIVE_PR_CI_PENDING", f"PR #{active_pr} CI is pending", f"pr:{active_pr}"))
                elif ci == "unknown" or not observed:
                    findings.append(finding("NEEDS_HUMAN", "ACTIVE_PR_CI_UNKNOWN", f"PR #{active_pr} CI could not be established", f"pr:{active_pr}"))
    if not findings:
        findings.append(finding("CONTINUE", "NEXT_TRANSITION_AVAILABLE", state["development"]["nextTransition"], "development"))
    indexed = list(enumerate(findings))
    _, best = max(indexed, key=lambda p: (ACTION_PRIORITY[p[1]["action"]], -p[0]))
    recommendation = {"action": best["action"], "reasonCode": best["code"], "focus": best.get("subject"), "detail": best["detail"], "decisionScope": "operational-only", "semanticAuthority": False, "allowedActions": list(ACTIONS)}
    return findings, recommendation


def build_inspection(state, verification, observed_git, capabilities, *, project_machine_inspection_hash, remote_requested, pull_requests, coordination_state, work_items=None, work_graph=None, machine_trust=None, machine_coherence=None, machine_sensors=None):
    if not isinstance(project_machine_inspection_hash, str) or len(project_machine_inspection_hash) != 64 or any(c not in "0123456789abcdef" for c in project_machine_inspection_hash):
        raise RuntimeError("MAINTENANCE_PROJECT_MACHINE_HASH_INVALID")
    work_items = work_items or []
    graph = work_graph if isinstance(work_graph, dict) else work_graph_module.build(work_items)
    findings, recommendation = decide(state, verification, capabilities, remote_requested=remote_requested, pull_requests=pull_requests, coordination_state=coordination_state, work_items=work_items, work_graph=graph, machine_trust=machine_trust, machine_coherence=machine_coherence, machine_sensors=machine_sensors)
    body = {"schemaVersion": SCHEMA_VERSION, "repository": state["project"]["repository"], "projectMachineInspectionHash": project_machine_inspection_hash, "projectState": {"phase": state["development"]["phase"], "checkpoint": state["development"]["checkpoint"], "nextTransition": state["development"]["nextTransition"], "activeDevelopmentBranch": state["git"].get("activeDevelopmentBranch"), "developmentPrNumber": state["development"].get("prNumber"), "blockers": state["development"].get("blockers") or []}, "verification": verification, "observedGit": observed_git, "capabilities": capabilities, "workItems": work_items, "workGraph": graph, "remoteRequested": remote_requested, "pullRequests": pull_requests, "coordination": coordination_state, "findings": findings, "recommendation": recommendation, "readOnly": True}
    return {**body, "inspectionHash": stable_hash(body)}


def _sensor_data(machine, name):
    sensors = machine.get("sensors")
    if not isinstance(sensors, dict) or not isinstance(sensors.get(name), dict):
        raise RuntimeError(f"PROJECT_MACHINE_SENSOR_MISSING:{name}")
    data = sensors[name].get("data")
    if not isinstance(data, dict):
        raise RuntimeError(f"PROJECT_MACHINE_SENSOR_DATA_INVALID:{name}")
    return data


def from_project_inspection(machine):
    project_machine.validate_inspection(machine)
    project = machine["project"]
    state = {"project": {"repository": machine["repository"]}, "git": {"activeDevelopmentBranch": project.get("activeDevelopmentBranch"), "controlBranch": project.get("controlBranch")}, "development": {"phase": project["phase"], "checkpoint": project["checkpoint"], "nextTransition": project["nextTransition"], "prNumber": project.get("developmentPrNumber"), "blockers": project.get("blockers") or []}}
    project_state = _sensor_data(machine, "projectState")
    git_data = _sensor_data(machine, "git")
    capability_data = _sensor_data(machine, "capabilities")
    pull_request_data = _sensor_data(machine, "pullRequests")
    coordination_data = _sensor_data(machine, "coordination")
    continuation_data = _sensor_data(machine, "continuations")
    verification = project_state.get("verification")
    observed_git = git_data.get("observed")
    if not isinstance(verification, dict):
        raise RuntimeError("PROJECT_MACHINE_VERIFICATION_INVALID")
    if not isinstance(observed_git, dict):
        raise RuntimeError("PROJECT_MACHINE_GIT_OBSERVATION_INVALID")
    work_items = continuation_data.get("items") or []
    if not isinstance(work_items, list):
        raise RuntimeError("PROJECT_MACHINE_WORK_ITEMS_INVALID")
    return build_inspection(state, verification, observed_git, capability_data.get("items") or [], project_machine_inspection_hash=machine["inspectionHash"], remote_requested=machine["scope"] in {"base", "live"}, pull_requests=pull_request_data, coordination_state=coordination_data, work_items=work_items, work_graph=machine["workGraph"], machine_trust=machine.get("trust"), machine_coherence=machine.get("coherence"), machine_sensors=machine.get("sensors"))


def validate_inspection(value):
    if not isinstance(value, dict):
        raise RuntimeError("MAINTENANCE_INPUT_INVALID")
    if value.get("schemaVersion") != SCHEMA_VERSION:
        raise RuntimeError("MAINTENANCE_SCHEMA_UNSUPPORTED")
    if value.get("repository") != project_machine.REPOSITORY:
        raise RuntimeError("MAINTENANCE_REPOSITORY_MISMATCH")
    source_hash = value.get("projectMachineInspectionHash")
    if not isinstance(source_hash, str) or len(source_hash) != 64 or any(c not in "0123456789abcdef" for c in source_hash):
        raise RuntimeError("MAINTENANCE_PROJECT_MACHINE_HASH_INVALID")
    if value.get("readOnly") is not True:
        raise RuntimeError("MAINTENANCE_NOT_READ_ONLY")
    rec = value.get("recommendation")
    if not isinstance(rec, dict) or rec.get("action") not in ACTIONS:
        raise RuntimeError("MAINTENANCE_RECOMMENDATION_INVALID")
    if rec.get("decisionScope") != "operational-only" or rec.get("semanticAuthority") is not False:
        raise RuntimeError("MAINTENANCE_SEMANTIC_AUTHORITY_INVALID")
    graph = value.get("workGraph")
    if not isinstance(graph, dict):
        raise RuntimeError("MAINTENANCE_WORK_GRAPH_INVALID")
    work_graph_module.validate(graph)
    supplied = value.get("inspectionHash")
    body = {key: item for key, item in value.items() if key != "inspectionHash"}
    if not isinstance(supplied, str) or supplied != stable_hash(body):
        raise RuntimeError("MAINTENANCE_HASH_MISMATCH")
    return {"ok": True, "inspectionHash": supplied, "projectMachineInspectionHash": source_hash}


def validate_derivation(value, machine):
    project_machine.validate_inspection(machine)
    validate_inspection(value)
    if value != from_project_inspection(machine):
        raise RuntimeError("MAINTENANCE_DERIVATION_MISMATCH")
    return {"ok": True, "inspectionHash": value["inspectionHash"], "projectMachineInspectionHash": machine["inspectionHash"]}


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
        return from_project_inspection(project_machine.inspect_local())
    if scope == "base":
        return from_project_inspection(project_machine.inspect_base())
    if scope == "live":
        return from_project_inspection(project_machine.inspect_live())
    raise RuntimeError("MAINTENANCE_SCOPE_INVALID")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="maintenance-inspect")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--input")
    group.add_argument("--local", action="store_true")
    group.add_argument("--base", action="store_true")
    group.add_argument("--live", action="store_true")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    try:
        if args.input:
            payload = from_project_inspection(load_json(args.input))
        else:
            payload = inspect_scope("live" if args.live else ("base" if args.base else "local"))
        print(json.dumps(payload, indent=2, ensure_ascii=False) if args.as_json else "MAINTENANCE INSPECT\n  recommendation: %s\n  reason: %s\n  focus: %s\n  work items: %d\n  source ProjectMachine: %s\n  inspectionHash: %s" % (payload["recommendation"]["action"], payload["recommendation"]["reasonCode"], payload["recommendation"].get("focus") or "(none)", len(payload["workItems"]), payload["projectMachineInspectionHash"], payload["inspectionHash"]))
        return 0
    except RuntimeError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False) if args.as_json else f"BLOCKED\n{exc}")
        return ERROR_EXIT


if __name__ == "__main__":
    raise SystemExit(main())
