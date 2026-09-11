#!/usr/bin/env python3
"""Read-only factual sensors for the MobiliPresenter project machine."""
from __future__ import annotations

from typing import Any

from tools import (
    agent,
    capability_gates,
    continuation,
    coordination,
    project_ci_observation,
    project_state,
    publication,
)
from tools.semantics.branches import parse_branch_name
from tools.semantics.observation import ObservationStatus


def sensor(
    status: str,
    *,
    code: str | None = None,
    data: Any = None,
    required: bool = True,
    authority: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        normalized = ObservationStatus.parse(str(status).upper()).value
    except RuntimeError as exc:
        raise RuntimeError("PROJECT_SENSOR_STATUS_INVALID") from exc
    return {
        "status": normalized,
        "required": bool(required),
        "code": code,
        "authority": authority,
        "data": data,
    }


def summarize_checks(checks: list[dict[str, Any]]) -> tuple[str, str | None]:
    statuses: list[str] = []
    for item in checks:
        try:
            statuses.append(
                ObservationStatus.parse(
                    str(item.get("status") or ObservationStatus.UNKNOWN.value).upper()
                ).value
            )
        except RuntimeError:
            statuses.append(ObservationStatus.FAIL.value)
    if ObservationStatus.FAIL.value in statuses:
        first = next(
            (
                item
                for item in checks
                if str(item.get("status")).upper() == ObservationStatus.FAIL.value
            ),
            {},
        )
        return ObservationStatus.FAIL.value, str(first.get("code") or "CHECK_FAILED")
    if ObservationStatus.UNKNOWN.value in statuses:
        first = next(
            (
                item
                for item in checks
                if str(item.get("status")).upper() == ObservationStatus.UNKNOWN.value
            ),
            {},
        )
        return ObservationStatus.UNKNOWN.value, str(first.get("code") or "CHECK_UNKNOWN")
    return ObservationStatus.PASS.value, None


def capability_items() -> list[dict[str, Any]]:
    out = []
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


def observe_capabilities():
    try:
        return sensor(
            "PASS",
            data={"items": capability_items()},
            authority={"kind": "repository", "path": "ops/capabilities"},
        )
    except (RuntimeError, OSError, ValueError, KeyError) as exc:
        return sensor(
            "FAIL",
            code="CAPABILITY_OBSERVATION_FAILED",
            data={"items": [], "detail": str(exc)},
            authority={"kind": "repository", "path": "ops/capabilities"},
        )


def continuation_item(value):
    view = continuation.operational_view(value)
    return {
        **view,
        "sourceSchemaVersion": value["schemaVersion"],
        "stateHash": continuation.state_hash(value),
    }


def observe_continuations_local():
    return sensor(
        "UNKNOWN",
        code="NOT_OBSERVED_IN_LOCAL_SCOPE",
        data={
            "available": False,
            "reason": "NOT_REQUESTED",
            "authorityBranch": "coordination/continuations",
            "authorityHead": None,
            "items": [],
            "mode": "not-observed",
        },
        required=False,
        authority={"kind": "git-authority", "branch": "coordination/continuations"},
    )


def observe_continuations_live():
    try:
        from tools.continuation_remote import GitHubContinuationAuthority

        authority = GitHubContinuationAuthority()
        observed = authority.observe()
        items = [
            continuation_item(value)
            for _, value in sorted(observed.items.items())
        ]
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


def _operations_branch(branch: Any) -> bool:
    if not isinstance(branch, str):
        return False
    try:
        identity = parse_branch_name(branch)
    except RuntimeError:
        return False
    if identity.get("semanticDomain") != "operations":
        return False
    if identity.get("grammar") == "canonical":
        return identity.get("declaredClass") in {"work", "experiment"}
    return identity.get("grammar") == "legacy"


def _list_pages(endpoint: str) -> tuple[list[Any], bool]:
    items: list[Any] = []
    page = 1
    while True:
        separator = "&" if "?" in endpoint else "?"
        ok, payload = agent.run_gh_json(
            f"{endpoint}{separator}per_page=100&page={page}"
        )
        if not ok or not isinstance(payload, list):
            return items, False
        items.extend(payload)
        if len(payload) < 100:
            return items, True
        page += 1


def _workflow_run_pages(
    repository: str, head_sha: str
) -> tuple[list[Any], bool, bool]:
    raw_runs: list[Any] = []
    page = 1
    expected_total: int | None = None
    complete = True
    observed = False
    while True:
        ok, payload = agent.run_gh_json(
            f"repos/{repository}/actions/runs?head_sha={head_sha}&per_page=100&page={page}"
        )
        if (
            not ok
            or not isinstance(payload, dict)
            or not isinstance(payload.get("workflow_runs"), list)
        ):
            return raw_runs, False, observed
        observed = True
        page_runs = payload["workflow_runs"]
        total = payload.get("total_count")
        if type(total) is int and total >= 0:
            if expected_total is None:
                expected_total = total
            elif total != expected_total:
                complete = False
        elif total is not None:
            complete = False
        raw_runs.extend(page_runs)
        if expected_total is not None and len(raw_runs) >= expected_total:
            if len(raw_runs) != expected_total:
                complete = False
            return raw_runs, complete, observed
        if len(page_runs) < 100:
            if expected_total is not None and len(raw_runs) != expected_total:
                complete = False
            return raw_runs, complete, observed
        page += 1


def _workflow_runs(
    repository: str, head_sha: str, raw_runs: list[Any]
) -> tuple[list[dict[str, Any]], bool]:
    runs: list[dict[str, Any]] = []
    complete = True
    for raw in raw_runs:
        if not isinstance(raw, dict):
            complete = False
            continue
        jobs_observed = False
        job_count = None
        run_id = raw.get("id")
        if (
            str(raw.get("conclusion") or "").lower() == "action_required"
            and type(run_id) is int
            and run_id > 0
        ):
            jobs_ok, jobs_payload = agent.run_gh_json(
                f"repos/{repository}/actions/runs/{run_id}/jobs?per_page=100"
            )
            if jobs_ok and isinstance(jobs_payload, dict):
                total = jobs_payload.get("total_count")
                jobs = jobs_payload.get("jobs")
                if type(total) is int and total >= 0 and isinstance(jobs, list):
                    jobs_observed = True
                    job_count = total
        try:
            runs.append(
                project_ci_observation.normalize_run(
                    raw,
                    repository=repository,
                    jobs_observed=jobs_observed,
                    job_count=job_count,
                )
            )
        except RuntimeError:
            complete = False
    return runs, complete


def observe_pull_requests(repository: str, *, live: bool):
    authority = {"kind": "github", "resource": "pull-requests"}
    if not isinstance(repository, str) or not repository:
        return sensor(
            "FAIL",
            code="REPOSITORY_IDENTITY_INVALID",
            data={"available": False, "items": []},
            authority=authority,
        )
    if not live:
        return sensor(
            "UNKNOWN",
            code="NOT_OBSERVED_IN_LOCAL_SCOPE",
            data={"available": False, "reason": "NOT_REQUESTED", "items": []},
            required=False,
            authority=authority,
        )
    payload, inventory_complete = _list_pages(
        f"repos/{repository}/pulls?state=open"
    )
    if not inventory_complete:
        return sensor(
            "UNKNOWN",
            code="REMOTE_PR_INVENTORY_UNAVAILABLE",
            data={
                "available": False,
                "reason": "OPEN_PR_READ_INCOMPLETE",
                "items": [],
            },
            authority=authority,
        )
    items = []
    for raw in payload:
        if not isinstance(raw, dict):
            continue
        head = raw.get("head") if isinstance(raw.get("head"), dict) else {}
        base = raw.get("base") if isinstance(raw.get("base"), dict) else {}
        head_sha = head.get("sha")
        runs: list[dict[str, Any]] = []
        ci = "unknown"
        ci_observed = False
        ci_complete = False
        if isinstance(head_sha, str):
            raw_runs, pages_complete, ci_observed = _workflow_run_pages(
                repository, head_sha
            )
            if ci_observed:
                runs, normalization_complete = _workflow_runs(
                    repository, head_sha, raw_runs
                )
                ci_complete = pages_complete and normalization_complete
                try:
                    ci = project_ci_observation.classify_runs(
                        runs,
                        head_sha,
                        include_agent_ops=_operations_branch(head.get("ref")),
                        observation_complete=ci_complete,
                    )
                except RuntimeError:
                    ci = "unknown"
        items.append(
            {
                "number": raw.get("number"),
                "draft": raw.get("draft"),
                "headRef": head.get("ref"),
                "headSha": head_sha,
                "baseRef": base.get("ref"),
                "ci": ci,
                "ciObserved": ci_observed,
                "ciComplete": ci_complete,
                "workflows": runs,
            }
        )
    items.sort(key=lambda item: int(item.get("number") or 0))
    return sensor(
        "PASS",
        data={"available": True, "items": items},
        authority=authority,
    )


def observe_coordination(*, live):
    if not live:
        return sensor(
            "UNKNOWN",
            code="NOT_OBSERVED_IN_LOCAL_SCOPE",
            data={
                "available": False,
                "reason": "NOT_REQUESTED",
                "intents": [],
                "leases": [],
            },
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


def observe_control_head(state, *, live):
    view = project_state.operational_view(state)
    branch = view["git"]["controlBranch"]
    if live:
        repo = view["project"]["repository"]
        ok, payload = agent.run_gh_json(f"repos/{repo}/git/ref/heads/{branch}")
        sha = (
            payload.get("object", {}).get("sha")
            if ok
            and isinstance(payload, dict)
            and isinstance(payload.get("object"), dict)
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


def observe_local_core(state):
    state_errors = project_state.validate_current(state)
    project_checks = []
    if state_errors:
        project_checks.extend(
            {"name": "project-state", "status": "FAIL", **error}
            for error in state_errors
        )
        view = None
    else:
        project_checks.append(
            {"name": "project-state", "status": "PASS", "code": None}
        )
        view = project_state.operational_view(state)
    schema_ok = project_state.CURRENT_SCHEMA_PATH.is_file()
    project_checks.append(
        {
            "name": "project-state-schema",
            "status": "PASS" if schema_ok else "FAIL",
            "code": None if schema_ok else "SCHEMA_FILE_MISSING",
        }
    )

    repository_checks = []
    for rel in ("AGENTS.md", "README.md"):
        exists = (agent.ROOT / rel).is_file()
        repository_checks.append(
            {
                "name": f"required:{rel}",
                "status": "PASS" if exists else "FAIL",
                "code": None if exists else "REQUIRED_FILE_MISSING",
            }
        )

    publication_checks = []
    publication_data = {"checks": publication_checks}
    publication_path = "ops/published/unknown"
    published_source = None
    if view is None:
        publication_checks.append(
            {
                "name": "published-artifact-state",
                "status": "FAIL",
                "code": "PROJECT_STATE_INVALID",
            }
        )
    else:
        publication_path = view["published"]["artifactManifest"]
        try:
            manifest = publication.load_manifest(publication_path)
            projection = publication.publication_view(view, manifest)
            publication_data.update(projection)
            published_source = projection["sourceBranch"]
            publication_checks.append(
                {
                    "name": "published-artifact-state",
                    "status": "PASS",
                    "code": None,
                    "observedRelease": projection["release"],
                    "observedSourceBranch": projection["sourceBranch"],
                    "observedSourceBuildFingerprint": projection[
                        "sourceBuildFingerprint"
                    ],
                    "fingerprintKind": projection["fingerprintKind"],
                }
            )
        except RuntimeError as exc:
            publication_checks.append(
                {
                    "name": "published-artifact-state",
                    "status": "FAIL",
                    "code": str(exc).split(":", 1)[0],
                    "path": publication_path,
                }
            )
            publication_data["detail"] = str(exc)

    observed = agent.observed_git()
    git_checks = []
    if view is None:
        git_checks.append(
            {"name": "git-context", "status": "FAIL", "code": "PROJECT_STATE_INVALID"}
        )
    else:
        git_checks.append(
            agent.git_context_check(
                state, observed, published_source_branch=published_source
            )
        )

    all_checks = project_checks + publication_checks + repository_checks + git_checks
    verification = {
        **agent.verification_summary(all_checks),
        "checks": all_checks,
        "remote": None,
    }
    project_status, project_code = summarize_checks(project_checks)
    publication_status, publication_code = summarize_checks(publication_checks)
    git_status, git_code = summarize_checks(git_checks)
    repository_status, repository_code = summarize_checks(repository_checks)
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
            data=publication_data,
            authority={"kind": "repository", "path": publication_path},
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
            authority={
                "kind": "repository",
                "name": view["project"]["repository"] if view else None,
            },
        ),
    }
