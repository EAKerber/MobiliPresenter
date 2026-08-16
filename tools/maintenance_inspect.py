#!/usr/bin/env python3
"""Operational policy over a factual ProjectMachineInspection."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import capability_gates, project_machine

ERROR_EXIT = 2
ACTIONS = ("CONTINUE", "RECONCILE", "HANDOFF", "PAUSE", "NEEDS_HUMAN")
ACTION_PRIORITY = {"CONTINUE": 0, "HANDOFF": 1, "PAUSE": 2, "RECONCILE": 3, "NEEDS_HUMAN": 4}


def finding(action, code, detail, subject=None):
    if action not in ACTIONS:
        raise RuntimeError("MAINTENANCE_ACTION_INVALID")
    value = {"action": action, "code": code, "detail": detail}
    if subject is not None:
        value["subject"] = subject
    return value


def decide(state, verification, capabilities, *, remote_requested, pull_requests, coordination_state, continuations=None, machine_trust=None):
    findings = []
    continuations = continuations or []
    if isinstance(machine_trust, dict):
        trust_status = str(machine_trust.get("status") or "UNKNOWN").upper()
        if trust_status == "FAIL":
            failed = ", ".join(str(item) for item in machine_trust.get("failedSensors") or []) or "unknown"
            findings.append(finding("RECONCILE", "PROJECT_MACHINE_FAILED", f"failed factual sensors: {failed}", "project-machine"))
        elif trust_status == "UNKNOWN":
            unknown = ", ".join(str(item) for item in machine_trust.get("unknownSensors") or []) or "unknown"
            findings.append(finding("NEEDS_HUMAN", "PROJECT_MACHINE_INCOMPLETE", f"required factual sensors are unknown: {unknown}", "project-machine"))
    if not verification.get("ok"):
        failed = [item.get("name") for item in verification.get("checks", []) if item.get("status") == "FAIL"]
        findings.append(finding("RECONCILE", "VERIFICATION_FAILED", f"failed checks: {', '.join(str(item) for item in failed)}", "repository"))
    blockers = state["development"].get("blockers") or []
    if blockers:
        findings.append(finding("PAUSE", "EXPLICIT_BLOCKERS", "; ".join(str(item) for item in blockers), "development"))
    for task in continuations:
        subject = f"continuation:{task['id']}"
        status = task["status"]
        if status == "HANDOFF":
            findings.append(finding("HANDOFF", "CONTINUATION_HANDOFF_REQUIRED", f"handoff to {task['handoffTo']}: {task['nextAction']}", subject))
        elif status == "WAITING":
            findings.append(finding("PAUSE", "CONTINUATION_WAITING", "; ".join(task["blockedBy"]), subject))
        elif status in {"READY", "IN_PROGRESS"}:
            findings.append(finding("CONTINUE", "CONTINUATION_RUNNABLE", task["nextAction"] or "finish and mark done", subject))
    for item in capabilities:
        if item["policy"] != "experimental":
            continue
        if item.get("supervisorParticipation", "active") == "isolated":
            continue
        if item["reviewAction"] == "REVIEW_EMPTY_LIMIT":
            findings.append(finding("NEEDS_HUMAN", "CAPABILITY_EMPTY_LIMIT", "formal capability review reached its configured empty-round limit", item["id"]))
        elif item["reviewAction"] == "TEST_NEXT_GATES":
            findings.append(finding("CONTINUE", "CAPABILITY_GATES_DUE", f"next Gates: {', '.join(item['nextGates'])}", item["id"]))
        elif item["reviewAction"] == "REVIEW_EMPTY_ROUND":
            findings.append(finding("CONTINUE", "CAPABILITY_EMPTY_REVIEW_DUE", "re-evaluate the recorded deferral reason", item["id"]))
    if remote_requested:
        if not pull_requests.get("available"):
            findings.append(finding("NEEDS_HUMAN", "REMOTE_PR_INVENTORY_UNAVAILABLE", str(pull_requests.get("reason") or "unknown"), "github"))
        else:
            for pr in pull_requests.get("items", []):
                if pr.get("classification") == "unclassified":
                    findings.append(finding("RECONCILE", "UNCLASSIFIED_OPEN_PR", f"open PR #{pr.get('number')} head {pr.get('headRef')} is not mapped to active/preserved/operations state", f"pr:{pr.get('number')}"))
            active_pr = state["development"].get("prNumber")
            if isinstance(active_pr, int):
                matches = [item for item in pull_requests.get("items", []) if item.get("number") == active_pr]
                if not matches:
                    findings.append(finding("RECONCILE", "ACTIVE_PR_NOT_OPEN", f"ProjectState references PR #{active_pr}, but it is not open", "development"))
                else:
                    ci = matches[0].get("ci")
                    if ci == "failed":
                        findings.append(finding("RECONCILE", "ACTIVE_PR_CI_FAILED", f"PR #{active_pr} CI is failed", f"pr:{active_pr}"))
                    elif ci == "pending":
                        findings.append(finding("PAUSE", "ACTIVE_PR_CI_PENDING", f"PR #{active_pr} CI is pending", f"pr:{active_pr}"))
                    elif ci == "unknown":
                        findings.append(finding("NEEDS_HUMAN", "ACTIVE_PR_CI_UNKNOWN", f"PR #{active_pr} CI could not be established", f"pr:{active_pr}"))
        canonical = any(item["id"] == "coordination-leases" and item["policy"] == "canonical" for item in capabilities)
        if canonical and not coordination_state.get("available"):
            findings.append(finding("NEEDS_HUMAN", "COORDINATION_AUTHORITY_UNAVAILABLE", str(coordination_state.get("reason") or "unknown"), "coordination-leases"))
        elif coordination_state.get("available") and pull_requests.get("available"):
            open_numbers = {item.get("number") for item in pull_requests.get("items", []) if isinstance(item.get("number"), int)}
            for lease in coordination_state.get("leases", []):
                owner = lease.get("owner") if isinstance(lease, dict) and isinstance(lease.get("owner"), dict) else {}
                owner_pr = owner.get("pr")
                if isinstance(owner_pr, int) and owner_pr not in open_numbers:
                    findings.append(finding("RECONCILE", "LEASE_OWNER_PR_NOT_OPEN", f"lease {lease.get('leaseId')} references non-open PR #{owner_pr}", "coordination-leases"))
    if not findings:
        findings.append(finding("CONTINUE", "NEXT_TRANSITION_AVAILABLE", state["development"]["nextTransition"], "development"))
    indexed = list(enumerate(findings))
    _, best = max(indexed, key=lambda pair: (ACTION_PRIORITY[pair[1]["action"]], -pair[0]))
    recommendation = {"action": best["action"], "reasonCode": best["code"], "focus": best.get("subject"), "detail": best["detail"], "decisionScope": "operational-only", "semanticAuthority": False, "allowedActions": list(ACTIONS)}
    return findings, recommendation


def build_inspection(state, verification, observed_git, capabilities, *, remote_requested, pull_requests, coordination_state, continuations=None, machine_trust=None):
    continuations = continuations or []
    findings, recommendation = decide(state, verification, capabilities, remote_requested=remote_requested, pull_requests=pull_requests, coordination_state=coordination_state, continuations=continuations, machine_trust=machine_trust)
    body = {"schemaVersion": "MaintenanceInspection 0.2", "repository": state["project"]["repository"], "projectState": {"phase": state["development"]["phase"], "checkpoint": state["development"]["checkpoint"], "nextTransition": state["development"]["nextTransition"], "activeDevelopmentBranch": state["git"].get("activeDevelopmentBranch"), "developmentPrNumber": state["development"].get("prNumber"), "blockers": state["development"].get("blockers") or []}, "verification": verification, "observedGit": observed_git, "capabilities": capabilities, "continuations": continuations, "remoteRequested": remote_requested, "pullRequests": pull_requests, "coordination": coordination_state, "findings": findings, "recommendation": recommendation, "readOnly": True}
    return {**body, "inspectionHash": capability_gates.stable_hash(body)}


def _sensor_data(machine: dict[str, Any], name: str) -> dict[str, Any]:
    sensors = machine.get("sensors")
    if not isinstance(sensors, dict) or not isinstance(sensors.get(name), dict):
        raise RuntimeError(f"PROJECT_MACHINE_SENSOR_MISSING:{name}")
    data = sensors[name].get("data")
    if not isinstance(data, dict):
        raise RuntimeError(f"PROJECT_MACHINE_SENSOR_DATA_INVALID:{name}")
    return data


def from_project_inspection(machine: dict[str, Any]) -> dict[str, Any]:
    project_machine.validate_inspection(machine)
    project = machine["project"]
    state = {"project": {"repository": machine["repository"]}, "git": {"activeDevelopmentBranch": project.get("activeDevelopmentBranch")}, "development": {"phase": project["phase"], "checkpoint": project["checkpoint"], "nextTransition": project["nextTransition"], "prNumber": project.get("developmentPrNumber"), "blockers": project.get("blockers") or []}}
    project_state = _sensor_data(machine, "projectState")
    git_data = _sensor_data(machine, "git")
    capability_data = _sensor_data(machine, "capabilities")
    pull_request_data = _sensor_data(machine, "pullRequests")
    coordination_data = _sensor_data(machine, "coordination")
    continuation_data = _sensor_data(machine, "continuations")
    verification = project_state.get("verification")
    if not isinstance(verification, dict):
        raise RuntimeError("PROJECT_MACHINE_VERIFICATION_INVALID")
    observed_git = git_data.get("observed")
    if not isinstance(observed_git, dict):
        raise RuntimeError("PROJECT_MACHINE_GIT_OBSERVATION_INVALID")
    return build_inspection(state, verification, observed_git, capability_data.get("items") or [], remote_requested=machine["scope"] in {"base", "live"}, pull_requests=pull_request_data, coordination_state=coordination_data, continuations=continuation_data.get("items") or [], machine_trust=machine.get("trust"))


def inspect(include_remote):
    machine = project_machine.inspect_base() if include_remote else project_machine.inspect_local()
    return from_project_inspection(machine)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="maintenance-inspect")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--remote", action="store_true")
    args = parser.parse_args(argv)
    try:
        payload = inspect(args.remote)
        if args.as_json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print("MAINTENANCE INSPECT")
            print(f"  recommendation: {payload['recommendation']['action']}")
            print(f"  reason: {payload['recommendation']['reasonCode']}")
            print(f"  focus: {payload['recommendation'].get('focus') or '(none)'}")
            print(f"  continuations: {len(payload['continuations'])}")
            print(f"  inspectionHash: {payload['inspectionHash']}")
        return 0
    except RuntimeError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False) if args.as_json else f"BLOCKED\n{exc}")
        return ERROR_EXIT


if __name__ == "__main__":
    raise SystemExit(main())
