#!/usr/bin/env python3
"""Read-only factual sensors for the MobiliPresenter project machine."""
from __future__ import annotations

from typing import Any

from tools import agent, capability_gates, continuation, coordination
STATUSES = {"PASS", "UNKNOWN", "FAIL"}


def sensor(
    status: str,
    *,
    code: str | None = None,
    data: Any = None,
    required: bool = True,
    authority: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized = str(status).upper()
    if normalized not in STATUSES:
        raise RuntimeError("PROJECT_SENSOR_STATUS_INVALID")
    return {
        "status": normalized,
        "required": bool(required),
        "code": code,
        "authority": authority,
        "data": data,
    }


def summarize_checks(checks: list[dict[str, Any]]) -> tuple[str, str | None]:
    statuses = [str(item.get("status") or "UNKNOWN").upper() for item in checks]
    if any(value == "FAIL" for value in statuses):
        first = next((item for item in checks if str(item.get("status")).upper() == "FAIL"), {})
        return "FAIL", str(first.get("code") or "CHECK_FAILED")
    if any(value == "UNKNOWN" for value in statuses):
        first = next((item for item in checks if str(item.get("status")).upper() == "UNKNOWN"), {})
        return "UNKNOWN", str(first.get("code") or "CHECK_UNKNOWN")
    return "PASS", None


def capability_items() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for value in capability_gates.discover_capabilities():
        plan = capability_gates.build_review_plan(value)
        out.append(
            {
                "id": value["id"],
                "policy": value["policy"],
                "supervisorParticipation": capability_gates.supervisor_participation(value),
                "reviewAction": plan["action"],
                "nextGates": plan["nextGates"],
                "backlogCount": len(plan["backlog"]),
                "roundsWithoutActiveGates": plan["roundsWithoutActiveGates"],
                "maxRoundsWithoutActiveGates": plan["maxRoundsWithoutActiveGates"],
                "deferReason": plan["deferReason"],
                "reviewPlanHash": plan["planHash"],
            }
        )
    return out


def observe_capabilities() -> dict[str, Any]:
    try:
        items = capability_items()
        return sensor(
            "PASS",
            data={"items": items},
            authority={"kind": "repository", "path": "ops/capabilities"},
        )
    except (RuntimeError, OSError, ValueError, KeyError) as exc:
        return sensor(
            "FAIL",
            code="CAPABILITY_OBSERVATION_FAILED",
            data={"items": [], "detail": str(exc)},
            authority={"kind": "repository", "path": "ops/capabilities"},
        )


def continuation_item(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": value["id"],
        "actor": value["actor"],
        "status": value["status"],
        "branch": value["branch"],
        "prNumber": value["prNumber"],
        "completed": value["completed"],
        "remaining": value["remaining"],
        "nextAction": value["nextAction"],
        "lastKnownGood": value["lastKnownGood"],
        "blockedBy": value["blockedBy"],
        "handoffTo": value["handoffTo"],
        "stateHash": continuation.state_hash(value),
    }


def observe_continuations_local() -> dict[str, Any]:
    try:
        items = [continuation_item(value) for value in continuation.discover()]
        return sensor(
            "PASS",
            data={
                "available": True,
                "authorityBranch": None,
                "authorityHead": None,
                "items": items,
                "mode": "local-model",
            },
            required=True,
            authority={"kind": "local-model", "path": "ops/continuations"},
        )
    except (RuntimeError, OSError, ValueError, KeyError) as exc:
        return sensor(
            "FAIL",
            code="CONTINUATION_LOCAL_OBSERVATION_FAILED",
            data={"available": False, "reason": "LOCAL_READ_FAILED", "detail": str(exc), "items": []},
            required=True,
            authority={"kind": "local-model", "path": "ops/continuations"},
        )


def observe_continuations_live() -> dict[str, Any]:
    try:
        from tools.continuation_remote import GitHubContinuationAuthority
        authority = GitHubContinuationAuthority()
        observed = authority.observe()
        items = [continuation_item(value) for _, value in sorted(observed.items.items())]
        return sensor(
            "PASS",
            data={
                "available": True,
                "authorityBranch": authority.authority_branch,
                "authorityHead": observed.head_sha,
                "items": items,
                "mode": "live-authority",
            },
            authority={"kind": "git-authority", "branch": authority.authority_branch},
        )
    except (OSError, RuntimeError, ImportError) as exc:
        return sensor(
            "UNKNOWN",
            code="CONTINUATION_AUTHORITY_UNAVAILABLE",
            data={
                "available": False,
                "reason": getattr(exc, "code", "CONTINUATION_UNAVAILABLE"),
                "detail": getattr(exc, "detail", str(exc)),
                "items": [],
            },
            authority={"kind": "git-authority", "branch": "coordination/continuations"},
        )


def classify_pr(state: dict[str, Any], head_ref: Any) -> str:
    if head_ref == state["git"].get("activeDevelopmentBranch"):
        return "active-development"
    if isinstance(head_ref, str) and head_ref in set(state["git"].get("preserveBranches") or []):
        return "preserved"
    if isinstance(head_ref, str) and head_ref.startswith("ops/"):
        return "operations"
    return "unclassified"


def observe_pull_requests(state: dict[str, Any], *, live: bool) -> dict[str, Any]:
    if not live:
        return sensor(
            "UNKNOWN",
            code="NOT_OBSERVED_IN_LOCAL_SCOPE",
            data={"available": False, "reason": "NOT_REQUESTED", "items": []},
            required=False,
            authority={"kind": "github", "resource": "pull-requests"},
        )

    repo = state["project"]["repository"]
    ok, payload = agent.run_gh_json(f"repos/{repo}/pulls?state=open&per_page=100")
    if not ok or not isinstance(payload, list):
        return sensor(
            "UNKNOWN",
            code="REMOTE_PR_INVENTORY_UNAVAILABLE",
            data={"available": False, "reason": "OPEN_PR_READ_FAILED", "detail": payload, "items": []},
            authority={"kind": "github", "resource": "pull-requests"},
        )

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
            runs_ok, workflow_payload = agent.run_gh_json(
                f"repos/{repo}/actions/runs?head_sha={head_sha}&per_page=100"
            )
            if (
                runs_ok
                and isinstance(workflow_payload, dict)
                and isinstance(workflow_payload.get("workflow_runs"), list)
            ):
                runs = [
                    {
                        "name": item.get("name"),
                        "status": item.get("status"),
                        "conclusion": item.get("conclusion"),
                        "id": item.get("id"),
                    }
                    for item in workflow_payload["workflow_runs"]
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
                "classification": classify_pr(state, head_ref),
                "ci": ci,
                "workflows": runs,
            }
        )

    items.sort(key=lambda item: int(item.get("number") or 0))
    return sensor(
        "PASS",
        data={"available": True, "items": items},
        authority={"kind": "github", "resource": "pull-requests"},
    )


def observe_coordination(*, live: bool) -> dict[str, Any]:
    if not live:
        return sensor(
            "UNKNOWN",
            code="NOT_OBSERVED_IN_LOCAL_SCOPE",
            data={"available": False, "reason": "NOT_REQUESTED", "intents": [], "leases": []},
            required=False,
            authority={"kind": "git-authority", "branch": "coordination/leases"},
        )
    try:
        from tools.coordination_remote import GhApiTransport, GitHubCoordinationAuthority
        authority = GitHubCoordinationAuthority(GhApiTransport())
        observed = authority.observe()
        current = coordination.compact_expired(observed.state, observed.authority_now)
        return sensor(
            "PASS",
            data={
                "available": True,
                "authorityBranch": authority.authority_branch,
                "authorityHead": observed.head_sha,
                "intents": current["intents"],
                "leases": current["leases"],
            },
            authority={"kind": "git-authority", "branch": authority.authority_branch},
        )
    except (OSError, RuntimeError, ImportError) as exc:
        return sensor(
            "UNKNOWN",
            code="COORDINATION_AUTHORITY_UNAVAILABLE",
            data={
                "available": False,
                "reason": getattr(exc, "code", "COORDINATION_UNAVAILABLE"),
                "detail": getattr(exc, "detail", str(exc)),
                "intents": [],
                "leases": [],
            },
            authority={"kind": "git-authority", "branch": "coordination/leases"},
        )


def observe_control_head(state: dict[str, Any], *, live: bool) -> dict[str, Any]:
    branch = state["git"]["controlBranch"]
    if live:
        repo = state["project"]["repository"]
        ok, payload = agent.run_gh_json(f"repos/{repo}/git/ref/heads/{branch}")
        sha = (
            payload.get("object", {}).get("sha")
            if ok and isinstance(payload, dict) and isinstance(payload.get("object"), dict)
            else None
        )
        if isinstance(sha, str) and len(sha) == 40:
            return sensor(
                "PASS",
                data={"branch": branch, "sha": sha, "mode": "remote"},
                authority={"kind": "git-ref", "branch": branch},
            )
        return sensor(
            "UNKNOWN",
            code="CONTROL_HEAD_UNAVAILABLE",
            data={"branch": branch, "sha": None, "detail": payload},
            authority={"kind": "git-ref", "branch": branch},
        )

    ok, sha = agent.run_git("rev-parse", branch)
    if ok and isinstance(sha, str) and len(sha) == 40:
        return sensor(
            "PASS",
            data={"branch": branch, "sha": sha, "mode": "local"},
            authority={"kind": "git-ref", "branch": branch},
        )
    return sensor(
        "UNKNOWN",
        code="CONTROL_HEAD_NOT_AVAILABLE_LOCALLY",
        data={"branch": branch, "sha": None},
        required=False,
        authority={"kind": "git-ref", "branch": branch},
    )


def observe_local_core(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    verification = agent.verify_state(include_remote=False)
    checks = list(verification.get("checks") or [])

    project_checks = [
        item
        for item in checks
        if item.get("name") in {"project-state", "project-state-schema", "development-plan"}
    ]
    publication_checks = [item for item in checks if item.get("name") == "published-artifact-state"]
    git_checks = [item for item in checks if item.get("name") == "git-context"]
    repository_checks = [
        item for item in checks if isinstance(item.get("name"), str) and item["name"].startswith("required:")
    ]

    project_status, project_code = summarize_checks(project_checks)
    publication_status, publication_code = summarize_checks(publication_checks)
    git_status, git_code = summarize_checks(git_checks)
    repository_status, repository_code = summarize_checks(repository_checks)

    observed = agent.observed_git()
    return {
        "projectState": sensor(
            project_status,
            code=project_code,
            data={"verification": verification, "checks": project_checks},
            authority={"kind": "repository", "path": "ops/state/project.json"},
        ),
        "publication": sensor(
            publication_status,
            code=publication_code,
            data={
                "checks": publication_checks,
                "release": state["published"].get("release"),
                "manifest": state["published"].get("artifactManifest"),
                "sha256": state["published"].get("artifactSha256"),
            },
            authority={"kind": "repository", "path": state["published"].get("artifactManifest")},
        ),
        "git": sensor(
            git_status,
            code=git_code,
            data={"observed": observed, "checks": git_checks},
            authority={"kind": "worktree"},
        ),
        "repository": sensor(
            repository_status,
            code=repository_code,
            data={"checks": repository_checks},
            authority={"kind": "repository", "name": state["project"]["repository"]},
        ),
    }


def observe_development(
    state: dict[str, Any],
    pull_requests: dict[str, Any],
    *,
    live: bool,
) -> dict[str, Any]:
    active = state["git"].get("activeDevelopmentBranch")
    pr_number = state["development"].get("prNumber")
    data = {
        "activeDevelopmentBranch": active,
        "developmentPrNumber": pr_number,
        "phase": state["development"]["phase"],
        "checkpoint": state["development"]["checkpoint"],
        "nextTransition": state["development"]["nextTransition"],
        "blockers": state["development"].get("blockers") or [],
    }
    if active is None and pr_number is None:
        return sensor("PASS", code="NO_ACTIVE_DEVELOPMENT", data=data)
    if (active is None) != (pr_number is None):
        return sensor("FAIL", code="DEVELOPMENT_IDENTITY_INCOMPLETE", data=data)
    if not live:
        return sensor(
            "UNKNOWN",
            code="NOT_OBSERVED_IN_LOCAL_SCOPE",
            data=data,
            required=False,
        )
    pr_data = pull_requests.get("data") if isinstance(pull_requests.get("data"), dict) else {}
    if not pr_data.get("available"):
        return sensor("UNKNOWN", code="REMOTE_PR_INVENTORY_UNAVAILABLE", data=data)

    matches = [
        item for item in pr_data.get("items", []) if isinstance(item, dict) and item.get("number") == pr_number
    ]
    if not matches:
        return sensor("FAIL", code="ACTIVE_PR_NOT_OPEN", data=data)

    item = matches[0]
    identity_ok = (
        item.get("headRef") == active
        and item.get("baseRef") == state["git"].get("controlBranch")
    )
    if not identity_ok:
        return sensor("FAIL", code="REMOTE_PR_DIVERGENCE", data={**data, "pr": item})

    ci = str(item.get("ci") or "unknown")
    if ci == "failed":
        return sensor("FAIL", code="REMOTE_CI_FAILED", data={**data, "pr": item})
    if ci == "pending":
        return sensor("UNKNOWN", code="REMOTE_CI_PENDING", data={**data, "pr": item})
    if ci == "unknown":
        return sensor("UNKNOWN", code="REMOTE_CI_UNKNOWN", data={**data, "pr": item})
    return sensor("PASS", data={**data, "pr": item})
