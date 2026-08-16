#!/usr/bin/env python3
"""Pure cross-authority coherence for ProjectMachineInspection."""
from __future__ import annotations

import json
from typing import Any

STATUSES = {"PASS", "UNKNOWN", "FAIL"}
AUTHORITY_IDS = {
    "projectState": "project-state",
    "publication": "publication",
    "git": "git-worktree",
    "repository": "repository",
    "control": "control",
    "capabilities": "capabilities",
    "pullRequests": "github-pull-requests",
    "coordination": "coordination",
    "continuations": "continuations",
}


def _status(sensor: Any) -> str:
    if not isinstance(sensor, dict):
        return "FAIL"
    value = str(sensor.get("status") or "UNKNOWN").upper()
    return value if value in STATUSES else "FAIL"


def _data(sensors: dict[str, dict[str, Any]], name: str) -> dict[str, Any]:
    sensor = sensors.get(name)
    if not isinstance(sensor, dict):
        return {}
    data = sensor.get("data")
    return data if isinstance(data, dict) else {}


def derive_authorities(sensors: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Derive a deterministic authority projection; never persist an authority registry."""
    grouped: dict[str, dict[str, Any]] = {}
    for sensor_name in sorted(sensors):
        sensor = sensors[sensor_name]
        authority = sensor.get("authority") if isinstance(sensor, dict) else None
        if not isinstance(authority, dict) or not authority:
            continue
        key = json.dumps(authority, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        if key not in grouped:
            grouped[key] = {"authority": authority, "observedBy": []}
        grouped[key]["observedBy"].append(sensor_name)

    out: list[dict[str, Any]] = []
    for key in sorted(grouped):
        group = grouped[key]
        observed_by = sorted(group["observedBy"])
        authority = group["authority"]
        preferred = next((AUTHORITY_IDS[name] for name in observed_by if name in AUTHORITY_IDS), observed_by[0])
        out.append(
            {
                "id": preferred,
                "kind": authority.get("kind"),
                "locator": {name: authority[name] for name in sorted(authority) if name != "kind"},
                "observedBy": observed_by,
            }
        )
    out.sort(key=lambda item: (str(item["id"]), json.dumps(item["locator"], sort_keys=True)))
    return out


def coherence_check(
    check_id: str,
    status: str,
    code: str,
    subjects: list[str],
    *,
    required: bool = True,
    detail: Any = None,
) -> dict[str, Any]:
    normalized = str(status).upper()
    if normalized not in STATUSES:
        raise RuntimeError("PROJECT_COHERENCE_STATUS_INVALID")
    return {
        "id": check_id,
        "status": normalized,
        "required": bool(required),
        "code": code,
        "subjects": list(subjects),
        "detail": detail,
    }


def aggregate_coherence(checks: list[dict[str, Any]]) -> dict[str, Any]:
    failed = sorted(item["id"] for item in checks if item.get("required") is True and item.get("status") == "FAIL")
    unknown = sorted(item["id"] for item in checks if item.get("required") is True and item.get("status") == "UNKNOWN")
    status = "FAIL" if failed else ("UNKNOWN" if unknown else "PASS")
    return {
        "status": status,
        "ok": status != "FAIL",
        "complete": status == "PASS",
        "failedChecks": failed,
        "unknownChecks": unknown,
        "checks": checks,
    }


def classify_open_pr(project: dict[str, Any], pr: dict[str, Any]) -> str:
    number = pr.get("number")
    head = pr.get("headRef")
    if (
        isinstance(number, int)
        and number == project.get("developmentPrNumber")
        and isinstance(head, str)
        and head == project.get("activeDevelopmentBranch")
    ):
        return "active-development"
    preserve = project.get("preserveBranches") or []
    if isinstance(head, str) and head in set(preserve):
        return "preserved"
    if isinstance(head, str) and head.startswith("ops/"):
        return "operations"
    return "unclassified"


def _pull_request_items(sensors: dict[str, dict[str, Any]]) -> tuple[bool, list[dict[str, Any]]]:
    data = _data(sensors, "pullRequests")
    available = data.get("available") is True
    items = data.get("items") if isinstance(data.get("items"), list) else []
    return available, [item for item in items if isinstance(item, dict)]


def _development_checks(project: dict[str, Any], sensors: dict[str, dict[str, Any]], scope: str) -> list[dict[str, Any]]:
    active = project.get("activeDevelopmentBranch")
    pr_number = project.get("developmentPrNumber")
    remote_required = scope in {"base", "live"}
    checks: list[dict[str, Any]] = []

    if active is None and pr_number is None:
        checks.append(coherence_check("development.identity.complete", "PASS", "NO_ACTIVE_DEVELOPMENT", ["project-state"], detail=None))
        for check_id in ("development.pr.open", "development.pr.head", "development.pr.base"):
            checks.append(coherence_check(check_id, "PASS", "NOT_APPLICABLE", ["project-state", "github-pull-requests"], required=False))
        return checks

    if (active is None) != (pr_number is None):
        checks.append(
            coherence_check(
                "development.identity.complete",
                "FAIL",
                "DEVELOPMENT_IDENTITY_INCOMPLETE",
                ["project-state"],
                detail={"activeDevelopmentBranch": active, "developmentPrNumber": pr_number},
            )
        )
        for check_id in ("development.pr.open", "development.pr.head", "development.pr.base"):
            checks.append(coherence_check(check_id, "PASS", "NOT_APPLICABLE", ["project-state", "github-pull-requests"], required=False))
        return checks

    checks.append(coherence_check("development.identity.complete", "PASS", "DEVELOPMENT_IDENTITY_COMPLETE", ["project-state"]))
    if not remote_required:
        for check_id in ("development.pr.open", "development.pr.head", "development.pr.base"):
            checks.append(coherence_check(check_id, "UNKNOWN", "NOT_OBSERVED_IN_LOCAL_SCOPE", ["project-state", "github-pull-requests"], required=False))
        return checks

    available, prs = _pull_request_items(sensors)
    if not available:
        checks.append(coherence_check("development.pr.open", "UNKNOWN", "REMOTE_PR_INVENTORY_UNAVAILABLE", ["project-state", "github-pull-requests"]))
        checks.append(coherence_check("development.pr.head", "UNKNOWN", "PR_IDENTITY_NOT_OBSERVABLE", ["project-state", "github-pull-requests"], required=False))
        checks.append(coherence_check("development.pr.base", "UNKNOWN", "PR_IDENTITY_NOT_OBSERVABLE", ["project-state", "github-pull-requests"], required=False))
        return checks

    matches = [item for item in prs if item.get("number") == pr_number]
    if not matches:
        checks.append(coherence_check("development.pr.open", "FAIL", "ACTIVE_PR_NOT_OPEN", ["project-state", "github-pull-requests"], detail={"prNumber": pr_number}))
        checks.append(coherence_check("development.pr.head", "UNKNOWN", "PR_IDENTITY_NOT_OBSERVABLE", ["project-state", "github-pull-requests"], required=False))
        checks.append(coherence_check("development.pr.base", "UNKNOWN", "PR_IDENTITY_NOT_OBSERVABLE", ["project-state", "github-pull-requests"], required=False))
        return checks

    pr = matches[0]
    checks.append(coherence_check("development.pr.open", "PASS", "ACTIVE_PR_OPEN", ["project-state", "github-pull-requests"], detail={"prNumber": pr_number}))
    if pr.get("headRef") != active:
        checks.append(coherence_check("development.pr.head", "FAIL", "ACTIVE_PR_HEAD_MISMATCH", ["project-state", "github-pull-requests"], detail={"expected": active, "observed": pr.get("headRef"), "prNumber": pr_number}))
    else:
        checks.append(coherence_check("development.pr.head", "PASS", "ACTIVE_PR_HEAD_MATCH", ["project-state", "github-pull-requests"], detail={"prNumber": pr_number}))
    control = project.get("controlBranch")
    if pr.get("baseRef") != control:
        checks.append(coherence_check("development.pr.base", "FAIL", "ACTIVE_PR_BASE_MISMATCH", ["project-state", "github-pull-requests"], detail={"expected": control, "observed": pr.get("baseRef"), "prNumber": pr_number}))
    else:
        checks.append(coherence_check("development.pr.base", "PASS", "ACTIVE_PR_BASE_MATCH", ["project-state", "github-pull-requests"], detail={"prNumber": pr_number}))
    return checks


def _pr_classification_check(project: dict[str, Any], sensors: dict[str, dict[str, Any]], scope: str) -> dict[str, Any]:
    required = scope in {"base", "live"}
    available, prs = _pull_request_items(sensors)
    if not available:
        return coherence_check("pull-requests.classification", "UNKNOWN", "REMOTE_PR_INVENTORY_UNAVAILABLE", ["project-state", "github-pull-requests"], required=required)
    items = [{"number": item.get("number"), "headRef": item.get("headRef"), "classification": classify_open_pr(project, item)} for item in prs]
    unclassified = [item for item in items if item["classification"] == "unclassified"]
    if unclassified:
        return coherence_check("pull-requests.classification", "FAIL", "UNCLASSIFIED_OPEN_PR", ["project-state", "github-pull-requests"], required=required, detail={"items": items, "unclassified": unclassified})
    return coherence_check("pull-requests.classification", "PASS", "OPEN_PRS_CLASSIFIED", ["project-state", "github-pull-requests"], required=required, detail={"items": items})


def _lease_pr_check(sensors: dict[str, dict[str, Any]], scope: str) -> dict[str, Any]:
    required = scope in {"base", "live"}
    coordination = _data(sensors, "coordination")
    if coordination.get("available") is not True:
        return coherence_check("coordination.lease.pr", "UNKNOWN", "COORDINATION_AUTHORITY_UNAVAILABLE", ["coordination", "github-pull-requests"], required=required)
    leases = coordination.get("leases") if isinstance(coordination.get("leases"), list) else []
    linked = []
    for lease in leases:
        owner = lease.get("owner") if isinstance(lease, dict) and isinstance(lease.get("owner"), dict) else {}
        if isinstance(owner.get("pr"), int):
            linked.append((lease, owner))
    if not linked:
        return coherence_check("coordination.lease.pr", "PASS", "NO_PR_LINKED_LEASES", ["coordination", "github-pull-requests"], required=required, detail={"checked": 0})
    available, prs = _pull_request_items(sensors)
    if not available:
        return coherence_check("coordination.lease.pr", "UNKNOWN", "REMOTE_PR_INVENTORY_UNAVAILABLE", ["coordination", "github-pull-requests"], required=required, detail={"checked": len(linked)})
    by_number = {item.get("number"): item for item in prs if isinstance(item.get("number"), int)}
    missing = []
    mismatch = []
    for lease, owner in linked:
        pr_number = owner["pr"]
        pr = by_number.get(pr_number)
        if pr is None:
            missing.append({"leaseId": lease.get("leaseId"), "prNumber": pr_number})
            continue
        branch = owner.get("branch")
        if isinstance(branch, str) and branch != pr.get("headRef"):
            mismatch.append({"leaseId": lease.get("leaseId"), "prNumber": pr_number, "expected": branch, "observed": pr.get("headRef")})
    if missing:
        return coherence_check("coordination.lease.pr", "FAIL", "LEASE_OWNER_PR_NOT_OPEN", ["coordination", "github-pull-requests"], required=required, detail={"missing": missing, "branchMismatch": mismatch})
    if mismatch:
        return coherence_check("coordination.lease.pr", "FAIL", "LEASE_OWNER_BRANCH_MISMATCH", ["coordination", "github-pull-requests"], required=required, detail={"branchMismatch": mismatch})
    return coherence_check("coordination.lease.pr", "PASS", "LEASE_PR_RELATIONS_COHERENT", ["coordination", "github-pull-requests"], required=required, detail={"checked": len(linked)})


def _continuation_pr_check(sensors: dict[str, dict[str, Any]], scope: str) -> dict[str, Any]:
    required = scope == "live"
    continuations = _data(sensors, "continuations")
    if continuations.get("available") is not True:
        return coherence_check("continuations.pr", "UNKNOWN", "CONTINUATION_AUTHORITY_UNAVAILABLE", ["continuations", "github-pull-requests"], required=required)
    items = continuations.get("items") if isinstance(continuations.get("items"), list) else []
    linked = [item for item in items if isinstance(item, dict) and item.get("status") != "DONE" and isinstance(item.get("prNumber"), int)]
    if not linked:
        return coherence_check("continuations.pr", "PASS", "NO_ACTIVE_PR_LINKED_CONTINUATIONS", ["continuations", "github-pull-requests"], required=required, detail={"checked": 0})
    available, prs = _pull_request_items(sensors)
    if not available:
        return coherence_check("continuations.pr", "UNKNOWN", "REMOTE_PR_INVENTORY_UNAVAILABLE", ["continuations", "github-pull-requests"], required=required, detail={"checked": len(linked)})
    by_number = {item.get("number"): item for item in prs if isinstance(item.get("number"), int)}
    missing = []
    mismatch = []
    for item in linked:
        pr_number = item["prNumber"]
        pr = by_number.get(pr_number)
        if pr is None:
            missing.append({"continuationId": item.get("id"), "prNumber": pr_number})
            continue
        branch = item.get("branch")
        if isinstance(branch, str) and branch != pr.get("headRef"):
            mismatch.append({"continuationId": item.get("id"), "prNumber": pr_number, "expected": branch, "observed": pr.get("headRef")})
    if missing:
        return coherence_check("continuations.pr", "FAIL", "CONTINUATION_PR_NOT_OPEN", ["continuations", "github-pull-requests"], required=required, detail={"missing": missing, "branchMismatch": mismatch})
    if mismatch:
        return coherence_check("continuations.pr", "FAIL", "CONTINUATION_PR_BRANCH_MISMATCH", ["continuations", "github-pull-requests"], required=required, detail={"branchMismatch": mismatch})
    return coherence_check("continuations.pr", "PASS", "CONTINUATION_PR_RELATIONS_COHERENT", ["continuations", "github-pull-requests"], required=required, detail={"checked": len(linked)})


def evaluate_coherence(project: dict[str, Any], sensors: dict[str, dict[str, Any]], *, scope: str) -> dict[str, Any]:
    if scope not in {"local", "base", "live"}:
        raise RuntimeError("PROJECT_COHERENCE_SCOPE_INVALID")
    checks = _development_checks(project, sensors, scope)
    checks.append(_pr_classification_check(project, sensors, scope))
    checks.append(_lease_pr_check(sensors, scope))
    checks.append(_continuation_pr_check(sensors, scope))
    return aggregate_coherence(checks)
