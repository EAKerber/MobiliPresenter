#!/usr/bin/env python3
"""Read-only integration reconciliation planner for MobiliPresenter."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import project_ci_observation, project_state
from tools.canonical import stable_hash
from tools.semantics.branches import parse_branch_name

ERROR_EXIT = 2
SCHEMA_VERSION = "IntegrationReconcilePlan 0.2"
SHARED = (
    "viewer-next/src/api/",
    "viewer-next/src/bootstrap.ts",
    "viewer-next/index.html",
    "viewer-next/package.json",
    "viewer-next/tsconfig.json",
    ".github/workflows/",
)


def _branch_domain(head_ref):
    try:
        identity = parse_branch_name(head_ref)
    except RuntimeError:
        return None
    if (
        identity.get("grammar") == "canonical"
        and identity.get("declaredClass") not in {"work", "experiment"}
    ):
        return None
    return identity.get("semanticDomain")


def classify_path(path):
    prefixes = (
        ("viewer-next/src/api/", "viewer-api"),
        ("viewer-next/src/ui/", "viewer-ui"),
        ("viewer-next/src/presentation/", "viewer-presentation"),
        ("viewer-next/src/runtime/", "viewer-runtime"),
        ("viewer-next/src/renderer/", "viewer-renderer"),
        ("viewer-next/tests/", "viewer-tests"),
        ("scene-core/", "scene-core"),
        (".github/workflows/", "ci"),
        ("docs/", "docs"),
    )
    for prefix, domain in prefixes:
        if path.startswith(prefix):
            return domain
    if path.startswith(("ops/", "tools/")) or path == "AGENTS.md":
        return "operations"
    return "other"


def is_shared_resource(path):
    return any(
        path.startswith(value) if value.endswith("/") else path == value
        for value in SHARED
    )


def boundary_assessment(head_ref, changed_files):
    files = sorted(set(changed_files))
    violations = []
    reviews = []
    domain = _branch_domain(head_ref)
    if domain == "engine":
        for path in files:
            if path.startswith("viewer-next/src/ui/"):
                violations.append({"path": path, "code": "ENGINE_TOUCHED_UI"})
            elif path.startswith(("ops/", "tools/")) or path == "AGENTS.md":
                violations.append({"path": path, "code": "ENGINE_TOUCHED_GITOPS"})
            elif path.startswith("viewer-next/src/api/"):
                reviews.append({"path": path, "code": "SHARED_API_CONTRACT_REVIEW"})
    elif domain == "ui":
        for path in files:
            if path.startswith(
                (
                    "viewer-next/src/presentation/",
                    "viewer-next/src/runtime/",
                    "viewer-next/src/renderer/",
                    "viewer-next/src/fixtures/",
                    "scene-core/",
                )
            ):
                violations.append({"path": path, "code": "UI_TOUCHED_ENGINE_DOMAIN"})
            elif path.startswith("viewer-next/src/api/"):
                reviews.append({"path": path, "code": "SHARED_API_CONTRACT_REVIEW"})
            elif path.startswith(("ops/", "tools/")) or path == "AGENTS.md":
                violations.append({"path": path, "code": "UI_TOUCHED_GITOPS"})
    elif domain == "operations":
        for path in files:
            if path.startswith(("viewer-next/", "scene-core/")):
                violations.append({"path": path, "code": "GITOPS_TOUCHED_PRODUCT"})
    return {
        "sharedResourcesTouched": [path for path in files if is_shared_resource(path)],
        "boundaryReview": reviews,
        "boundaryViolations": violations,
    }


def _selected_runs(runs, head_ref):
    operations = _branch_domain(head_ref) == "operations"
    latest = {}
    for run in runs:
        if not isinstance(run, dict):
            continue
        name = str(run.get("name") or "")
        if not name or (name == "Agent Ops" and not operations):
            continue
        latest.setdefault(name, run)
    return list(latest.values())


def aggregate_ci(runs, head_sha, head_ref=""):
    operations = _branch_domain(head_ref) == "operations"
    try:
        status = project_ci_observation.classify_runs(
            runs, head_sha, include_agent_ops=operations
        )
    except RuntimeError:
        status = "unknown"
    selected = _selected_runs(runs, head_ref)
    return {
        "status": status,
        "validatedSha": head_sha,
        "runs": [
            {key: run.get(key) for key in ("name", "id", "status", "conclusion")}
            for run in selected
        ],
    }


def domain_summary(files):
    out = {}
    for path in files:
        domain = classify_path(path)
        out[domain] = out.get(domain, 0) + 1
    return dict(sorted(out.items()))


def recommendation(obs, boundary, ci):
    pr = obs["pr"]
    target = obs["target"]
    ancestry = obs["ancestry"]
    base_to_target = ancestry["declaredBaseToTarget"]
    target_to_head = ancestry["targetToHead"]
    if pr.get("merged"):
        action, reason = "already-merged", "pull-request-is-already-merged"
    elif pr.get("state") != "open":
        action, reason = "no-action", "pull-request-is-not-open"
    elif boundary["boundaryViolations"]:
        action, reason = "semantic-owner-review", "cross-boundary-paths-detected"
    elif pr.get("baseRef") != target.get("branch"):
        if base_to_target.get("status") in {"ahead", "identical"}:
            action, reason = (
                "retarget-to-control-and-revalidate",
                "declared-base-is-contained-in-control",
            )
        else:
            action, reason = (
                "manual-reconciliation",
                "declared-base-is-not-cleanly-contained-in-control",
            )
    elif target_to_head.get("status") == "behind":
        action, reason = "no-action", "head-is-already-contained-in-control"
    elif ci["status"] == "reentry_required":
        action, reason = "reenter-ci", "head-ci-reentry-required"
    elif ci["status"] == "failed":
        action, reason = "fix-ci-before-integration", "head-ci-is-failed"
    elif ci["status"] in {"pending", "unknown"}:
        action, reason = "wait-for-ci", "head-ci-is-not-proven-green"
    else:
        action, reason = "review-current-target", "base-is-control-and-ci-is-green"
    return {
        "action": action,
        "reason": reason,
        "safeToApply": False,
        "note": (
            "Read-only recommendation. Semantic approval, retargeting and merge "
            "remain separate operations."
        ),
    }


def build_plan(obs):
    pr = obs["pr"]
    files = sorted(set(obs.get("changedFiles") or []))
    boundary = boundary_assessment(str(pr.get("headRef") or ""), files)
    ci = aggregate_ci(
        obs.get("workflowRuns") or [],
        pr.get("headSha"),
        str(pr.get("headRef") or ""),
    )
    body = {
        "schemaVersion": SCHEMA_VERSION,
        "repository": obs["repository"],
        "pr": pr,
        "target": obs["target"],
        "ancestry": obs["ancestry"],
        "scope": {
            "changedFileCount": len(files),
            "changedFiles": files,
            "domains": domain_summary(files),
            **boundary,
        },
        "ci": ci,
        "recommendation": recommendation(obs, boundary, ci),
        "applyEligible": False,
        "note": "Read-only plan. Any PR head, target head, CI or path drift invalidates this plan.",
    }
    return {**body, "planHash": stable_hash(body)}


class GhObserver:
    def __init__(self, repository):
        self.repository = repository

    def _run(self, endpoint):
        if shutil.which("gh") is None:
            raise RuntimeError("GH_NOT_FOUND")
        proc = subprocess.run(
            ["gh", "api", endpoint],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode:
            raise RuntimeError(
                f"GH_API_FAILED:{endpoint}:{(proc.stderr or proc.stdout).strip()}"
            )
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"GH_JSON_INVALID:{endpoint}") from exc

    def _pages(self, endpoint):
        out = []
        page = 1
        while True:
            payload = self._run(
                f"{endpoint}{'&' if '?' in endpoint else '?'}per_page=100&page={page}"
            )
            if not isinstance(payload, list):
                raise RuntimeError(f"GH_PAGE_INVALID:{endpoint}")
            out.extend(payload)
            if len(payload) < 100:
                return out
            page += 1

    @staticmethod
    def _compare(value):
        if not isinstance(value, dict):
            return {
                "status": "unknown",
                "aheadBy": None,
                "behindBy": None,
                "mergeBaseSha": None,
            }
        merge_base = (
            value.get("merge_base_commit")
            if isinstance(value.get("merge_base_commit"), dict)
            else {}
        )
        return {
            "status": value.get("status"),
            "aheadBy": value.get("ahead_by"),
            "behindBy": value.get("behind_by"),
            "mergeBaseSha": merge_base.get("sha"),
        }

    def _workflow_runs(self, repo: str, head_sha: str) -> list[dict]:
        payload = self._run(f"repos/{repo}/actions/runs?head_sha={head_sha}&per_page=100")
        raw_runs = payload.get("workflow_runs", []) if isinstance(payload, dict) else []
        if not isinstance(raw_runs, list):
            raise RuntimeError("WORKFLOW_RUNS_INVALID")
        runs = []
        for raw in raw_runs:
            if not isinstance(raw, dict):
                continue
            jobs_observed = False
            job_count = None
            run_id = raw.get("id")
            if (
                str(raw.get("conclusion") or "").lower() == "action_required"
                and type(run_id) is int
                and run_id > 0
            ):
                try:
                    jobs_payload = self._run(
                        f"repos/{repo}/actions/runs/{run_id}/jobs?per_page=100"
                    )
                except RuntimeError:
                    jobs_payload = None
                if isinstance(jobs_payload, dict):
                    total = jobs_payload.get("total_count")
                    jobs = jobs_payload.get("jobs")
                    if type(total) is int and total >= 0 and isinstance(jobs, list):
                        jobs_observed = True
                        job_count = total
            try:
                runs.append(
                    project_ci_observation.normalize_run(
                        raw,
                        repository=repo,
                        jobs_observed=jobs_observed,
                        job_count=job_count,
                    )
                )
            except RuntimeError:
                continue
        return runs

    def observe(self, pr_number, target_branch):
        repo = self.repository
        pr = self._run(f"repos/{self.repository}/pulls/{pr_number}")
        if not isinstance(pr, dict):
            raise RuntimeError("PR_READ_INVALID")
        head = pr.get("head") or {}
        base = pr.get("base") or {}
        target_commit = self._run(f"repos/{repo}/commits/{quote(target_branch, safe='')}")
        target_sha = target_commit.get("sha")
        base_sha = base.get("sha")
        head_sha = head.get("sha")
        if not all(isinstance(value, str) for value in (target_sha, base_sha, head_sha)):
            raise RuntimeError("PR_IDENTITY_INCOMPLETE")
        workflows = self._workflow_runs(repo, head_sha)
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
                "declaredBaseToTarget": self._compare(
                    self._run(f"repos/{repo}/compare/{base_sha}...{target_sha}")
                ),
                "targetToHead": self._compare(
                    self._run(f"repos/{repo}/compare/{target_sha}...{head_sha}")
                ),
            },
            "changedFiles": [
                item.get("filename")
                for item in self._pages(f"repos/{repo}/pulls/{pr_number}/files")
                if isinstance(item, dict) and isinstance(item.get("filename"), str)
            ],
            "workflowRuns": workflows,
        }


def load_state():
    state = project_state.load_state()
    errors = project_state.validate_current(state)
    if errors:
        raise RuntimeError(f"STATE_SCHEMA_INVALID:{errors[0]['detail']}")
    return state


def render_text(plan):
    pr = plan["pr"]
    target = plan["target"]
    ancestry = plan["ancestry"]
    scope = plan["scope"]
    recommendation_value = plan["recommendation"]
    return "\n".join(
        (
            "INTEGRATION RECONCILE PLAN",
            f"  PR: #{pr['number']} {pr['headRef']} @ {pr['headSha']}",
            f"  declared base: {pr['baseRef']} @ {pr['baseSha']}",
            f"  target: {target['branch']} @ {target['sha']}",
            f"  base -> target: {ancestry['declaredBaseToTarget']['status']}",
            f"  target -> head: {ancestry['targetToHead']['status']}",
            f"  changed files: {scope['changedFileCount']}",
            f"  shared resources: {len(scope['sharedResourcesTouched'])}",
            f"  boundary violations: {len(scope['boundaryViolations'])}",
            f"  CI: {plan['ci']['status']}",
            f"  recommendation: {recommendation_value['action']} ({recommendation_value['reason']})",
            f"  apply eligible: {plan['applyEligible']}",
            f"  planHash: {plan['planHash']}",
        )
    )


def main():
    parser = argparse.ArgumentParser(
        description="Read-only MobiliPresenter integration reconciliation planner"
    )
    parser.add_argument("command", choices=("reconcile-plan",))
    parser.add_argument("pr", type=int)
    parser.add_argument("--target")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    try:
        state = load_state()
        view = project_state.operational_view(state)
        repository = view["project"]["repository"]
        target = args.target or view["git"]["controlBranch"]
        plan = build_plan(GhObserver(repository).observe(args.pr, target))
        print(
            json.dumps(plan, indent=2, ensure_ascii=False)
            if args.as_json
            else render_text(plan)
        )
        return 0
    except RuntimeError as exc:
        print(
            json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)
            if args.as_json
            else f"BLOCKED\n{exc}",
            file=sys.stdout if args.as_json else sys.stderr,
        )
        return ERROR_EXIT


if __name__ == "__main__":
    raise SystemExit(main())
