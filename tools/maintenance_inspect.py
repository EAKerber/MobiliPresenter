#!/usr/bin/env python3
"""Read-only global operational sensor for the future MobiliPresenter supervisor."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import agent  # noqa: E402
from tools import capability_gates  # noqa: E402
from tools import coordination  # noqa: E402
from tools.coordination_remote import (  # noqa: E402
    CoordinationRemoteError,
    GhApiTransport,
    GitHubCoordinationAuthority,
)

ERROR_EXIT = 2
ACTIONS = ("CONTINUE", "RECONCILE", "HANDOFF", "PAUSE", "NEEDS_HUMAN")
ACTION_PRIORITY = {"CONTINUE": 0, "HANDOFF": 1, "PAUSE": 2, "RECONCILE": 3, "NEEDS_HUMAN": 4}


def capability_snapshot() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for value in capability_gates.discover_capabilities():
        plan = capability_gates.build_review_plan(value)
        result.append(
            {
                "id": value["id"],
                "policy": value["policy"],
                "reviewAction": plan["action"],
                "nextGates": plan["nextGates"],
                "backlogCount": len(plan["backlog"]),
                "roundsWithoutActiveGates": plan["roundsWithoutActiveGates"],
                "maxRoundsWithoutActiveGates": plan["maxRoundsWithoutActiveGates"],
                "deferReason": plan["deferReason"],
                "reviewPlanHash": plan["planHash"],
            }
        )
    return result


def _pr_class(state: dict[str, Any], head_ref: str | None) -> str:
    if head_ref == state["git"].get("activeDevelopmentBranch"):
        return "active-development"
    if isinstance(head_ref, str) and head_ref in set(state["git"].get("preserveBranches") or []):
        return "preserved"
    if isinstance(head_ref, str) and head_ref.startswith("ops/git-ops-"):
        return "operations"
    return "unclassified"


def observe_open_prs(state: dict[str, Any]) -> dict[str, Any]:
    repo = state["project"]["repository"]
    ok, payload = agent.run_gh_json(f"repos/{repo}/pulls?state=open&per_page=100")
    if not ok or not isinstance(payload, list):
        return {"available": False, "reason": "OPEN_PR_READ_FAILED", "detail": payload, "items": []}
    items: list[dict[str, Any]] = []
    for raw in payload:
        if not isinstance(raw, dict):
            continue
        head = raw.get("head") if isinstance(raw.get("head"), dict) else {}
        base = raw.get("base") if isinstance(raw.get("base"), dict) else {}
        head_sha = head.get("sha")
        runs: list[dict[str, Any]] = []
        ci = "unknown"
        if isinstance(head_sha, str):
            runs_ok, runs_payload = agent.run_gh_json(f"repos/{repo}/actions/runs?head_sha={head_sha}&per_page=100")
            if runs_ok and isinstance(runs_payload, dict) and isinstance(runs_payload.get("workflow_runs"), list):
                runs = [
                    {
                        "name": item.get("name"),
                        "status": item.get("status"),
                        "conclusion": item.get("conclusion"),
                        "id": item.get("id"),
                    }
                    for item in runs_payload["workflow_runs"]
                    if isinstance(item, dict)
                ]
                ci = agent.aggregate_ci(runs)
        head_ref = head.get("ref")
        items.append(
            {
                "number": raw.get("number"),
                "draft": raw.get("draft"),
                "headRef": head_ref,
                "headSha": head_sha,
                "baseRef": base.get("ref"),
                "classification": _pr_class(state, head_ref),
                "ci": ci,
                "workflows": runs,
            }
        )
    items.sort(key=lambda item: int(item.get("number") or 0))
    return {"available": True, "items": items}


def observe_coordination() -> dict[str, Any]:
    try:
        authority = GitHubCoordinationAuthority(GhApiTransport())
        observed = authority.observe()
        current = coordination.compact_expired(observed.state, observed.authority_now)
        return {
            "available": True,
            "authorityBranch": authority.authority_branch,
            "authorityHead": observed.head_sha,
            "intents": current["intents"],
            "leases": current["leases"],
        }
    except (CoordinationRemoteError, OSError) as exc:
        return {
            "available": False,
            "reason": getattr(exc, "code", "COORDINATION_UNAVAILABLE"),
            "detail": getattr(exc, "detail", str(exc)),
            "intents": [],
            "leases": [],
        }


def _finding(action: str, code: str, detail: str, *, subject: str | None = None) -> dict[str, Any]:
    if action not in ACTIONS:
        raise RuntimeError("MAINTENANCE_ACTION_INVALID")
    value: dict[str, Any] = {"action": action, "code": code, "detail": detail}
    if subject is not None:
        value["subject"] = subject
    return value


def decide(
    state: dict[str, Any],
    verification: dict[str, Any],
    capabilities: list[dict[str, Any]],
    *,
    remote_requested: bool,
    pull_requests: dict[str, Any],
    coordination_state: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    findings: list[dict[str, Any]] = []

    if not verification.get("ok"):
        failed = [check.get("name") for check in verification.get("checks", []) if check.get("status") == "FAIL"]
        findings.append(_finding("RECONCILE", "VERIFICATION_FAILED", f"failed checks: {', '.join(str(x) for x in failed)}", subject="repository"))

    blockers = state["development"].get("blockers") or []
    if blockers:
        findings.append(_finding("PAUSE", "EXPLICIT_BLOCKERS", "; ".join(str(item) for item in blockers), subject="development"))

    for item in capabilities:
        if item["policy"] != "experimental":
            continue
        if item["reviewAction"] == "REVIEW_EMPTY_LIMIT":
            findings.append(_finding("NEEDS_HUMAN", "CAPABILITY_EMPTY_LIMIT", "formal capability review reached its configured empty-round limit", subject=item["id"]))
        elif item["reviewAction"] == "TEST_NEXT_GATES":
            findings.append(_finding("CONTINUE", "CAPABILITY_GATES_DUE", f"next Gates: {', '.join(item['nextGates'])}", subject=item["id"]))
        elif item["reviewAction"] == "REVIEW_EMPTY_ROUND":
            findings.append(_finding("CONTINUE", "CAPABILITY_EMPTY_REVIEW_DUE", "re-evaluate the recorded deferral reason", subject=item["id"]))

    if remote_requested:
        if not pull_requests.get("available"):
            findings.append(_finding("NEEDS_HUMAN", "REMOTE_PR_INVENTORY_UNAVAILABLE", str(pull_requests.get("reason") or "unknown"), subject="github"))
        else:
            for pr in pull_requests.get("items", []):
                if pr.get("classification") == "unclassified":
                    findings.append(_finding("RECONCILE", "UNCLASSIFIED_OPEN_PR", f"open PR #{pr.get('number')} head {pr.get('headRef')} is not mapped to active/preserved/operations state", subject=f"pr:{pr.get('number')}"))
            active_pr = state["development"].get("prNumber")
            if isinstance(active_pr, int):
                matches = [item for item in pull_requests.get("items", []) if item.get("number") == active_pr]
                if not matches:
                    findings.append(_finding("RECONCILE", "ACTIVE_PR_NOT_OPEN", f"ProjectState references PR #{active_pr}, but it is not in the open PR inventory", subject="development"))
                else:
                    ci = matches[0].get("ci")
                    if ci == "failed":
                        findings.append(_finding("RECONCILE", "ACTIVE_PR_CI_FAILED", f"PR #{active_pr} CI is failed", subject=f"pr:{active_pr}"))
                    elif ci == "pending":
                        findings.append(_finding("PAUSE", "ACTIVE_PR_CI_PENDING", f"PR #{active_pr} CI is pending", subject=f"pr:{active_pr}"))
                    elif ci == "unknown":
                        findings.append(_finding("NEEDS_HUMAN", "ACTIVE_PR_CI_UNKNOWN", f"PR #{active_pr} CI could not be established", subject=f"pr:{active_pr}"))

        coordination_canonical = any(item["id"] == "coordination-leases" and item["policy"] == "canonical" for item in capabilities)
        if coordination_canonical and not coordination_state.get("available"):
            findings.append(_finding("NEEDS_HUMAN", "COORDINATION_AUTHORITY_UNAVAILABLE", str(coordination_state.get("reason") or "unknown"), subject="coordination-leases"))
        elif coordination_state.get("available") and pull_requests.get("available"):
            open_numbers = {item.get("number") for item in pull_requests.get("items", []) if isinstance(item.get("number"), int)}
            for lease in coordination_state.get("leases", []):
                owner = lease.get("owner") if isinstance(lease, dict) and isinstance(lease.get("owner"), dict) else {}
                owner_pr = owner.get("pr")
                if isinstance(owner_pr, int) and owner_pr not in open_numbers:
                    findings.append(_finding("RECONCILE", "LEASE_OWNER_PR_NOT_OPEN", f"lease {lease.get('leaseId')} references non-open PR #{owner_pr}", subject="coordination-leases"))

    if not findings:
        findings.append(_finding("CONTINUE", "NEXT_TRANSITION_AVAILABLE", state["development"]["nextTransition"], subject="development"))

    indexed = list(enumerate(findings))
    best_index, best = max(indexed, key=lambda pair: (ACTION_PRIORITY[pair[1]["action"]], -pair[0]))
    recommendation = {
        "action": best["action"],
        "reasonCode": best["code"],
        "focus": best.get("subject"),
        "detail": best["detail"],
        "decisionScope": "operational-only",
        "semanticAuthority": False,
        "allowedActions": list(ACTIONS),
    }
    return findings, recommendation


def build_inspection(
    state: dict[str, Any],
    verification: dict[str, Any],
    observed_git: dict[str, Any],
    capabilities: list[dict[str, Any]],
    *,
    remote_requested: bool,
    pull_requests: dict[str, Any],
    coordination_state: dict[str, Any],
) -> dict[str, Any]:
    findings, recommendation = decide(
        state,
        verification,
        capabilities,
        remote_requested=remote_requested,
        pull_requests=pull_requests,
        coordination_state=coordination_state,
    )
    body = {
        "schemaVersion": "MaintenanceInspection 0.1",
        "repository": state["project"]["repository"],
        "projectState": {
            "phase": state["development"]["phase"],
            "checkpoint": state["development"]["checkpoint"],
            "nextTransition": state["development"]["nextTransition"],
            "activeDevelopmentBranch": state["git"].get("activeDevelopmentBranch"),
            "developmentPrNumber": state["development"].get("prNumber"),
            "blockers": state["development"].get("blockers") or [],
        },
        "verification": verification,
        "observedGit": observed_git,
        "capabilities": capabilities,
        "remoteRequested": remote_requested,
        "pullRequests": pull_requests,
        "coordination": coordination_state,
        "findings": findings,
        "recommendation": recommendation,
        "readOnly": True,
    }
    return {**body, "inspectionHash": capability_gates.stable_hash(body)}


def inspect(include_remote: bool) -> dict[str, Any]:
    state = agent.load_json(agent.STATE_PATH)
    errors = agent.validate_state_shape(state)
    if errors:
        raise RuntimeError(f"STATE_SCHEMA_INVALID:{errors[0]['detail']}")
    verification = agent.verify_state(include_remote=include_remote)
    observed = agent.observed_git()
    capabilities = capability_snapshot()
    prs = observe_open_prs(state) if include_remote else {"available": False, "reason": "NOT_REQUESTED", "items": []}
    coordination_state = observe_coordination() if include_remote else {"available": False, "reason": "NOT_REQUESTED", "intents": [], "leases": []}
    return build_inspection(
        state,
        verification,
        observed,
        capabilities,
        remote_requested=include_remote,
        pull_requests=prs,
        coordination_state=coordination_state,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="maintenance-inspect", description="Read-only global operational sensor")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--remote", action="store_true", help="Observe open PRs, CI and Coordination authority")
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
            print(f"  findings: {len(payload['findings'])}")
            print(f"  inspectionHash: {payload['inspectionHash']}")
        return 0
    except RuntimeError as exc:
        payload = {"ok": False, "error": str(exc)}
        print(json.dumps(payload, ensure_ascii=False) if args.as_json else f"BLOCKED\n{exc}")
        return ERROR_EXIT


if __name__ == "__main__":
    raise SystemExit(main())
