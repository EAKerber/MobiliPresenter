#!/usr/bin/env python3
"""Read-only integration reconciliation planner for MobiliPresenter.

The planner observes GitHub and ProjectState, then emits a deterministic plan.
It never mutates pull requests, refs, files, or canonical state.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "ops" / "state" / "project.json"
ERROR_EXIT = 2
SCHEMA_VERSION = "IntegrationReconcilePlan 0.1"

SHARED_RESOURCE_PATTERNS = (
    "viewer-next/src/api/",
    "viewer-next/src/bootstrap.ts",
    "viewer-next/index.html",
    "viewer-next/package.json",
    "viewer-next/tsconfig.json",
    ".github/workflows/",
)


def stable_plan_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def classify_path(path: str) -> str:
    if path.startswith("viewer-next/src/api/"):
        return "viewer-api"
    if path.startswith("viewer-next/src/ui/"):
        return "viewer-ui"
    if path.startswith("viewer-next/src/presentation/"):
        return "viewer-presentation"
    if path.startswith("viewer-next/src/runtime/"):
        return "viewer-runtime"
    if path.startswith("viewer-next/src/renderer/"):
        return "viewer-renderer"
    if path.startswith("viewer-next/tests/"):
        return "viewer-tests"
    if path.startswith("scene-core/"):
        return "scene-core"
    if path.startswith("ops/") or path.startswith("tools/") or path == "AGENTS.md":
        return "operations"
    if path.startswith(".github/workflows/"):
        return "ci"
    if path.startswith("docs/"):
        return "docs"
    return "other"


def is_shared_resource(path: str) -> bool:
    for pattern in SHARED_RESOURCE_PATTERNS:
        if pattern.endswith("/"):
            if path.startswith(pattern):
                return True
        elif path == pattern:
            return True
    return False


def boundary_assessment(head_ref: str, changed_files: Iterable[str]) -> dict[str, Any]:
    files = sorted(set(changed_files))
    shared = [path for path in files if is_shared_resource(path)]
    violations: list[dict[str, str]] = []
    reviews: list[dict[str, str]] = []

    if head_ref.startswith("engine/"):
        for path in files:
            if path.startswith("viewer-next/src/ui/"):
                violations.append({"path": path, "code": "ENGINE_TOUCHED_UI"})
            elif path.startswith("ops/") or path.startswith("tools/") or path == "AGENTS.md":
                violations.append({"path": path, "code": "ENGINE_TOUCHED_GITOPS"})
            elif path.startswith("viewer-next/src/api/"):
                reviews.append({"path": path, "code": "SHARED_API_CONTRACT_REVIEW"})
    elif head_ref.startswith("ui/"):
        forbidden = (
            "viewer-next/src/presentation/",
            "viewer-next/src/runtime/",
            "viewer-next/src/renderer/",
            "viewer-next/src/fixtures/",
            "scene-core/",
        )
        for path in files:
            if path.startswith(forbidden):
                violations.append({"path": path, "code": "UI_TOUCHED_ENGINE_DOMAIN"})
            elif path.startswith("viewer-next/src/api/"):
                reviews.append({"path": path, "code": "SHARED_API_CONTRACT_REVIEW"})
            elif path.startswith("ops/") or path.startswith("tools/") or path == "AGENTS.md":
                violations.append({"path": path, "code": "UI_TOUCHED_GITOPS"})
    elif head_ref.startswith("ops/"):
        for path in files:
            if path.startswith("viewer-next/") or path.startswith("scene-core/"):
                violations.append({"path": path, "code": "GITOPS_TOUCHED_PRODUCT"})

    return {
        "sharedResourcesTouched": shared,
        "boundaryReview": reviews,
        "boundaryViolations": violations,
    }


def aggregate_ci(runs: list[dict[str, Any]], head_sha: str | None) -> dict[str, Any]:
    latest_by_name: dict[str, dict[str, Any]] = {}
    for run in runs:
        name = str(run.get("name") or "")
        if not name or name == "Agent Ops":
            continue
        if name not in latest_by_name:
            latest_by_name[name] = run
    selected = list(latest_by_name.values())
    if not selected:
        status = "unknown"
    elif any(str(run.get("status", "")).lower() != "completed" for run in selected):
        status = "pending"
    else:
        conclusions = {str(run.get("conclusion") or "").lower() for run in selected}
        if conclusions <= {"success", "neutral", "skipped"}:
            status = "green"
        elif conclusions & {"failure", "cancelled", "timed_out", "action_required", "startup_failure"}:
            status = "failed"
        else:
            status = "unknown"
    normalized = [
        {"name": run.get("name"), "id": run.get("id"), "status": run.get("status"), "conclusion": run.get("conclusion")}
        for run in selected
    ]
    return {"status": status, "validatedSha": head_sha, "runs": normalized}


def domain_summary(changed_files: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for path in changed_files:
        domain = classify_path(path)
        counts[domain] = counts.get(domain, 0) + 1
    return dict(sorted(counts.items()))


def state_assessment(state: dict[str, Any], pr: dict[str, Any]) -> dict[str, Any]:
    git_state = state.get("git") if isinstance(state.get("git"), dict) else {}
    development = state.get("development") if isinstance(state.get("development"), dict) else {}
    active = git_state.get("activeDevelopmentBranch")
    active_pr = development.get("prNumber")
    pr_number = pr.get("number")
    head_ref = pr.get("headRef")
    if active == head_ref and active_pr == pr_number:
        alignment = "aligned-active-development"
    elif active is None and active_pr is None:
        alignment = "no-active-development"
    else:
        alignment = "development-identity-mismatch"

    likely_stale: list[str] = []
    if pr.get("merged") and active == head_ref:
        likely_stale.append("git.activeDevelopmentBranch")
    if pr.get("merged") and active_pr == pr_number:
        likely_stale.append("development.prNumber")

    return {
        "alignment": alignment,
        "activeDevelopmentBranch": active,
        "activePrNumber": active_pr,
        "phase": development.get("phase"),
        "checkpoint": development.get("checkpoint"),
        "nextTransition": development.get("nextTransition"),
        "blockers": development.get("blockers") or [],
        "likelyStaleFields": likely_stale,
        "postMergeReviewFields": [
            "git.activeDevelopmentBranch",
            "development.prNumber",
            "development.phase",
            "development.checkpoint",
            "development.nextTransition",
            "development.blockers",
        ],
    }


def recommendation(observation: dict[str, Any], boundary: dict[str, Any], ci: dict[str, Any]) -> dict[str, Any]:
    pr = observation["pr"]
    ancestry = observation["ancestry"]
    target = observation["target"]
    base_to_target = ancestry.get("declaredBaseToTarget") or {}
    target_to_head = ancestry.get("targetToHead") or {}

    if pr.get("merged"):
        action, reason = "already-merged", "pull-request-is-already-merged"
    elif pr.get("state") != "open":
        action, reason = "no-action", "pull-request-is-not-open"
    elif boundary["boundaryViolations"]:
        action, reason = "semantic-owner-review", "cross-boundary-paths-detected"
    elif pr.get("baseRef") != target.get("branch"):
        if base_to_target.get("status") in {"ahead", "identical"}:
            action, reason = "retarget-to-control-and-revalidate", "declared-base-is-contained-in-control"
        else:
            action, reason = "manual-reconciliation", "declared-base-is-not-cleanly-contained-in-control"
    elif target_to_head.get("status") == "behind":
        action, reason = "no-action", "head-is-already-contained-in-control"
    elif ci.get("status") == "failed":
        action, reason = "fix-ci-before-integration", "head-ci-is-failed"
    elif ci.get("status") in {"pending", "unknown"}:
        action, reason = "wait-for-ci", "head-ci-is-not-proven-green"
    else:
        action, reason = "review-current-target", "base-is-control-and-ci-is-green"

    return {
        "action": action,
        "reason": reason,
        "safeToApply": False,
        "note": "Read-only recommendation. Semantic approval, retargeting and merge remain separate operations.",
    }


def build_plan(observation: dict[str, Any]) -> dict[str, Any]:
    pr = observation["pr"]
    files = sorted(set(observation.get("changedFiles") or []))
    boundary = boundary_assessment(str(pr.get("headRef") or ""), files)
    ci = aggregate_ci(observation.get("workflowRuns") or [], pr.get("headSha"))
    body = {
        "schemaVersion": SCHEMA_VERSION,
        "repository": observation["repository"],
        "pr": pr,
        "target": observation["target"],
        "ancestry": observation["ancestry"],
        "scope": {
            "changedFileCount": len(files),
            "changedFiles": files,
            "domains": domain_summary(files),
            **boundary,
        },
        "ci": ci,
        "canonicalState": state_assessment(observation["projectState"], pr),
    }
    body["recommendation"] = recommendation(observation, boundary, ci)
    body["applyEligible"] = False
    body["note"] = "Read-only plan. Any PR head, target head, CI or path drift invalidates this plan."
    return {**body, "planHash": stable_plan_hash(body)}


@dataclass
class GhObserver:
    repository: str

    def _run(self, endpoint: str) -> Any:
        if shutil.which("gh") is None:
            raise RuntimeError("GH_NOT_FOUND")
        proc = subprocess.run(["gh", "api", endpoint], cwd=ROOT, text=True, capture_output=True, check=False)
        if proc.returncode != 0:
            raise RuntimeError(f"GH_API_FAILED:{endpoint}:{(proc.stderr or proc.stdout).strip()}")
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"GH_JSON_INVALID:{endpoint}") from exc

    def _pages(self, endpoint: str) -> list[Any]:
        values: list[Any] = []
        page = 1
        while True:
            separator = "&" if "?" in endpoint else "?"
            payload = self._run(f"{endpoint}{separator}per_page=100&page={page}")
            if not isinstance(payload, list):
                raise RuntimeError(f"GH_PAGE_INVALID:{endpoint}")
            values.extend(payload)
            if len(payload) < 100:
                return values
            page += 1

    def observe(self, pr_number: int, target_branch: str, project_state: dict[str, Any]) -> dict[str, Any]:
        repo = self.repository
        pr = self._run(f"repos/{repo}/pulls/{pr_number}")
        if not isinstance(pr, dict):
            raise RuntimeError("PR_READ_INVALID")
        head = pr.get("head") if isinstance(pr.get("head"), dict) else {}
        base = pr.get("base") if isinstance(pr.get("base"), dict) else {}
        target_commit = self._run(f"repos/{repo}/commits/{quote(target_branch, safe='')}")
        if not isinstance(target_commit, dict) or not isinstance(target_commit.get("sha"), str):
            raise RuntimeError("TARGET_HEAD_READ_INVALID")
        target_sha = target_commit["sha"]
        base_sha = base.get("sha")
        head_sha = head.get("sha")
        if not isinstance(base_sha, str) or not isinstance(head_sha, str):
            raise RuntimeError("PR_IDENTITY_INCOMPLETE")

        base_to_target = self._run(f"repos/{repo}/compare/{base_sha}...{target_sha}")
        target_to_head = self._run(f"repos/{repo}/compare/{target_sha}...{head_sha}")
        files = self._pages(f"repos/{repo}/pulls/{pr_number}/files")
        workflow_payload = self._run(f"repos/{repo}/actions/runs?head_sha={head_sha}&per_page=100")
        runs = workflow_payload.get("workflow_runs") if isinstance(workflow_payload, dict) else []

        def compare_summary(value: Any) -> dict[str, Any]:
            if not isinstance(value, dict):
                return {"status": "unknown", "aheadBy": None, "behindBy": None, "mergeBaseSha": None}
            return {
                "status": value.get("status"),
                "aheadBy": value.get("ahead_by"),
                "behindBy": value.get("behind_by"),
                "mergeBaseSha": (value.get("merge_base_commit") or {}).get("sha") if isinstance(value.get("merge_base_commit"), dict) else None,
            }

        return {
            "repository": repo,
            "pr": {
                "number": pr.get("number"),
                "state": pr.get("state"),
                "draft": pr.get("draft"),
                "merged": bool(pr.get("merged")),
                "mergeable": pr.get("mergeable"),
                "headRef": head.get("ref"),
                "headSha": head_sha,
                "baseRef": base.get("ref"),
                "baseSha": base_sha,
            },
            "target": {"branch": target_branch, "sha": target_sha},
            "ancestry": {
                "declaredBaseToTarget": compare_summary(base_to_target),
                "targetToHead": compare_summary(target_to_head),
            },
            "changedFiles": [item.get("filename") for item in files if isinstance(item, dict) and isinstance(item.get("filename"), str)],
            "workflowRuns": runs if isinstance(runs, list) else [],
            "projectState": project_state,
        }


def load_state(path: Path = STATE_PATH) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"STATE_FILE_MISSING:{path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"STATE_JSON_INVALID:{exc.lineno}:{exc.colno}") from exc
    if not isinstance(value, dict):
        raise RuntimeError("STATE_ROOT_INVALID")
    return value


def render_text(plan: dict[str, Any]) -> str:
    pr = plan["pr"]
    target = plan["target"]
    scope = plan["scope"]
    ancestry = plan["ancestry"]
    rec = plan["recommendation"]
    return "\n".join([
        "INTEGRATION RECONCILE PLAN",
        f"  PR: #{pr['number']} {pr['headRef']} @ {pr['headSha']}",
        f"  declared base: {pr['baseRef']} @ {pr['baseSha']}",
        f"  target: {target['branch']} @ {target['sha']}",
        f"  base -> target: {ancestry['declaredBaseToTarget']['status']} (ahead {ancestry['declaredBaseToTarget']['aheadBy']}, behind {ancestry['declaredBaseToTarget']['behindBy']})",
        f"  target -> head: {ancestry['targetToHead']['status']} (ahead {ancestry['targetToHead']['aheadBy']}, behind {ancestry['targetToHead']['behindBy']})",
        f"  changed files: {scope['changedFileCount']}",
        f"  shared resources: {len(scope['sharedResourcesTouched'])}",
        f"  boundary violations: {len(scope['boundaryViolations'])}",
        f"  CI: {plan['ci']['status']}",
        f"  recommendation: {rec['action']} ({rec['reason']})",
        f"  apply eligible: {plan['applyEligible']}",
        f"  planHash: {plan['planHash']}",
    ])


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only MobiliPresenter integration reconciliation planner")
    parser.add_argument("command", choices=("reconcile-plan",))
    parser.add_argument("pr", type=int)
    parser.add_argument("--target")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    try:
        state = load_state()
        repository = state.get("project", {}).get("repository")
        target = args.target or state.get("git", {}).get("controlBranch")
        if not isinstance(repository, str) or not repository:
            raise RuntimeError("REPOSITORY_STATE_INVALID")
        if not isinstance(target, str) or not target:
            raise RuntimeError("TARGET_BRANCH_INVALID")
        observation = GhObserver(repository).observe(args.pr, target, state)
        plan = build_plan(observation)
        print(json.dumps(plan, indent=2, ensure_ascii=False) if args.as_json else render_text(plan))
        return 0
    except RuntimeError as exc:
        if args.as_json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"BLOCKED\n{exc}", file=sys.stderr)
        return ERROR_EXIT


if __name__ == "__main__":
    raise SystemExit(main())
