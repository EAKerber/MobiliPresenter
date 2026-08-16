#!/usr/bin/env python3
"""Deterministic operational toolbox for MobiliPresenter agents."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import project_state, publication
from tools import project_state_apply
from tools import project_state_transition
from tools import prune_plan as git_prune_plan
from tools.canonical import stable_hash
from tools.semantics.branches import parse_branch_name
from tools.semantics.observation import ObservationStatus

STATE_PATH = project_state.STATE_PATH
SCHEMA_PATH = project_state.CURRENT_SCHEMA_PATH
ERROR_EXIT = 2
TOOLBOX_COMMANDS = {"status", "doctor", "verify", "checkpoint", "handoff", "git prune-plan"}


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        try:
            rel = path.relative_to(ROOT)
        except ValueError:
            rel = path
        raise RuntimeError(f"STATE_FILE_MISSING: {rel}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"STATE_JSON_INVALID: {path}:{exc.lineno}:{exc.colno}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"STATE_ROOT_INVALID: {path} must contain an object")
    return value




def run_process(args: list[str]) -> tuple[bool, str]:
    proc = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout).strip()
    return True, proc.stdout.strip()


def run_git(*args: str) -> tuple[bool, str]:
    if shutil.which("git") is None:
        return False, "git executable not found"
    return run_process(["git", *args])


def run_gh_json(endpoint: str) -> tuple[bool, Any]:
    if shutil.which("gh") is None:
        return False, "gh executable not found"
    ok, output = run_process(["gh", "api", endpoint])
    if not ok:
        return False, output
    try:
        return True, json.loads(output)
    except json.JSONDecodeError:
        return False, "gh returned non-JSON output"


def ci_branch_name() -> str | None:
    head_ref = os.environ.get("GITHUB_HEAD_REF")
    if head_ref:
        return head_ref
    if os.environ.get("GITHUB_REF_TYPE") == "branch":
        return os.environ.get("GITHUB_REF_NAME") or None
    return None


def observed_git() -> dict[str, Any]:
    inside_ok, inside = run_git("rev-parse", "--is-inside-work-tree")
    if not inside_ok or inside != "true":
        return {"available": shutil.which("git") is not None, "worktree": False}
    branch_ok, branch = run_git("branch", "--show-current")
    observed_branch = branch if branch_ok and branch else ci_branch_name()
    head_ok, head = run_git("rev-parse", "HEAD")
    remote_ok, remote = run_git("remote", "get-url", "origin")
    dirty_ok, porcelain = run_git("status", "--porcelain")
    return {
        "available": True,
        "worktree": True,
        "branch": observed_branch,
        "head": head if head_ok else None,
        "origin": remote if remote_ok else None,
        "dirty": bool(porcelain) if dirty_ok else None,
    }


def _operations_work_branch(branch: Any) -> bool:
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


def git_context_check(state: dict[str, Any], observed: dict[str, Any], *, published_source_branch: str | None = None) -> dict[str, Any]:
    if not observed.get("worktree"):
        return {"name": "git-context", "status": "FAIL", "code": "NOT_A_GIT_WORKTREE"}
    view = project_state.operational_view(state)
    branch = observed.get("branch")
    git_state = view["git"]
    active = git_state.get("activeDevelopmentBranch")
    control = git_state["controlBranch"]
    protected = set(git_state.get("protectedBranches") or [])
    if active and branch == active:
        return {"name": "git-context", "status": "PASS", "code": None, "context": "active-development", "branch": branch}
    if branch == control or (published_source_branch is not None and branch == published_source_branch):
        return {"name": "git-context", "status": "PASS", "code": None, "context": "control", "branch": branch}
    if branch in protected:
        return {"name": "git-context", "status": "PASS", "code": None, "context": "protected-parallel", "branch": branch}
    if _operations_work_branch(branch):
        return {"name": "git-context", "status": "PASS", "code": None, "context": "operations", "branch": branch}
    return {"name": "git-context", "status": "FAIL", "code": "UNEXPECTED_BRANCH", "observed": branch, "expected": active}


def aggregate_ci(runs: list[dict[str, Any]]) -> str:
    if not runs:
        return "unknown"
    meaningful = [run for run in runs if run.get("name") != "Agent Ops"]
    if not meaningful:
        return "unknown"
    if any(str(run.get("status", "")).upper() != "COMPLETED" for run in meaningful):
        return "pending"
    conclusions = {str(run.get("conclusion") or "").upper() for run in meaningful}
    if conclusions <= {"SUCCESS", "NEUTRAL", "SKIPPED"}:
        return "green"
    if conclusions & {"FAILURE", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED", "STARTUP_FAILURE"}:
        return "failed"
    return "unknown"


def verification_summary(checks: list[dict[str, Any]]) -> dict[str, Any]:
    statuses: list[str] = []
    for check in checks:
        try:
            statuses.append(ObservationStatus.parse(str(check.get("status") or "UNKNOWN").upper()).value)
        except RuntimeError:
            statuses.append(ObservationStatus.FAIL.value)
    if ObservationStatus.FAIL.value in statuses:
        status = ObservationStatus.FAIL.value
    elif ObservationStatus.UNKNOWN.value in statuses:
        status = ObservationStatus.UNKNOWN.value
    else:
        status = ObservationStatus.PASS.value
    return {"status": status, "ok": status != ObservationStatus.FAIL.value, "complete": status == ObservationStatus.PASS.value}


def _state_and_publication() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    state = project_state.load_state()
    errors = project_state.validate_current(state)
    if errors:
        raise RuntimeError(f"STATE_SCHEMA_INVALID:{errors[0]['detail']}")
    view = project_state.operational_view(state)
    manifest = publication.load_manifest(view["published"]["artifactManifest"])
    return state, view, publication.publication_view(view, manifest)


def observe_remote(state: dict[str, Any], observed: dict[str, Any]) -> dict[str, Any]:
    view = project_state.operational_view(state)
    active = view["git"].get("activeDevelopmentBranch")
    pr_number = view["development"].get("prNumber")
    if active is None and pr_number is None:
        return {"available": True, "developmentActive": False, "reason": "NO_ACTIVE_DEVELOPMENT", "ci": "unknown"}
    if shutil.which("gh") is None:
        return {"available": False, "reason": "GH_NOT_FOUND", "ci": "unknown"}
    if not isinstance(pr_number, int):
        return {"available": False, "reason": "PR_NUMBER_MISSING", "ci": "unknown"}
    repo = view["project"]["repository"]
    pr_ok, pr = run_gh_json(f"repos/{repo}/pulls/{pr_number}")
    if not pr_ok or not isinstance(pr, dict):
        return {"available": False, "reason": "PR_READ_FAILED", "detail": pr, "ci": "unknown"}
    head_sha = pr.get("head", {}).get("sha") if isinstance(pr.get("head"), dict) else None
    runs: list[dict[str, Any]] = []
    if isinstance(head_sha, str):
        runs_ok, workflow_payload = run_gh_json(f"repos/{repo}/actions/runs?head_sha={head_sha}&per_page=100")
        if runs_ok and isinstance(workflow_payload, dict) and isinstance(workflow_payload.get("workflow_runs"), list):
            runs = [
                {"name": item.get("name"), "status": item.get("status"), "conclusion": item.get("conclusion"), "id": item.get("id")}
                for item in workflow_payload["workflow_runs"] if isinstance(item, dict)
            ]
    return {
        "available": True,
        "developmentActive": True,
        "pr": {
            "number": pr.get("number"), "state": pr.get("state"), "draft": pr.get("draft"),
            "headRef": pr.get("head", {}).get("ref") if isinstance(pr.get("head"), dict) else None,
            "headSha": head_sha,
            "baseRef": pr.get("base", {}).get("ref") if isinstance(pr.get("base"), dict) else None,
        },
        "workflows": runs,
        "ci": aggregate_ci(runs),
        "observedHeadMatchesPr": observed.get("head") == head_sha if observed.get("head") else None,
    }


def remote_verification_checks(state: dict[str, Any], remote: dict[str, Any]) -> list[dict[str, Any]]:
    view = project_state.operational_view(state)
    if remote.get("developmentActive") is False:
        return [{"name": "remote-development", "status": "PASS", "code": "NO_ACTIVE_DEVELOPMENT"}]
    if not remote.get("available"):
        return [{"name": "remote-observation", "status": "UNKNOWN", "code": "REMOTE_OBSERVATION_UNAVAILABLE", "observed": remote.get("reason")}]
    pr = remote.get("pr", {})
    identity_ok = (
        pr.get("number") == view["development"].get("prNumber")
        and pr.get("headRef") == view["git"].get("activeDevelopmentBranch")
        and pr.get("baseRef") == view["git"].get("controlBranch")
        and pr.get("state") == "open"
    )
    checks = [{"name": "remote-pr-identity", "status": "PASS" if identity_ok else "FAIL", "code": None if identity_ok else "REMOTE_PR_DIVERGENCE"}]
    ci = str(remote.get("ci") or "unknown")
    if ci == "green": ci_status, ci_code = "PASS", None
    elif ci == "failed": ci_status, ci_code = "FAIL", "REMOTE_CI_FAILED"
    elif ci == "pending": ci_status, ci_code = "UNKNOWN", "REMOTE_CI_PENDING"
    else: ci_status, ci_code = "UNKNOWN", "REMOTE_CI_UNKNOWN"
    checks.append({"name": "remote-ci", "status": ci_status, "code": ci_code, "observed": ci})
    return checks


def verify_state(include_remote: bool = False) -> dict[str, Any]:
    state = project_state.load_state()
    checks: list[dict[str, Any]] = []
    errors = project_state.validate_current(state)
    if errors:
        checks.extend({"name": "project-state", "status": "FAIL", **error} for error in errors)
        view = None
    else:
        checks.append({"name": "project-state", "status": "PASS", "code": None})
        view = project_state.operational_view(state)
    checks.append({"name": "project-state-schema", "status": "PASS" if SCHEMA_PATH.is_file() else "FAIL", "code": None if SCHEMA_PATH.is_file() else "SCHEMA_FILE_MISSING"})

    publication_projection: dict[str, Any] | None = None
    if view is None:
        checks.append({"name": "published-artifact-state", "status": "FAIL", "code": "PROJECT_STATE_INVALID"})
    else:
        manifest_rel = view["published"]["artifactManifest"]
        try:
            manifest = publication.load_manifest(manifest_rel)
            publication_projection = publication.publication_view(view, manifest)
            checks.append({
                "name": "published-artifact-state", "status": "PASS", "code": None,
                "observedRelease": publication_projection["release"],
                "observedSourceBranch": publication_projection["sourceBranch"],
                "observedSourceBuildFingerprint": publication_projection["sourceBuildFingerprint"],
                "fingerprintKind": publication_projection["fingerprintKind"],
            })
        except RuntimeError as exc:
            checks.append({"name": "published-artifact-state", "status": "FAIL", "code": str(exc).split(":", 1)[0], "path": manifest_rel})
    for rel in ("AGENTS.md", "README.md", "deploy.py"):
        exists = (ROOT / rel).is_file()
        checks.append({"name": f"required:{rel}", "status": "PASS" if exists else "FAIL", "code": None if exists else "REQUIRED_FILE_MISSING"})
    observed = observed_git()
    published_source = publication_projection.get("sourceBranch") if isinstance(publication_projection, dict) else None
    if view is not None:
        checks.append(git_context_check(state, observed, published_source_branch=published_source))
    remote: dict[str, Any] | None = None
    if include_remote and view is not None:
        remote = observe_remote(state, observed)
        checks.extend(remote_verification_checks(state, remote))
    return {**verification_summary(checks), "checks": checks, "remote": remote}


def command_status(as_json: bool, include_remote: bool) -> int:
    state, view, published = _state_and_publication()
    observed = observed_git()
    remote = observe_remote(state, observed) if include_remote else None
    payload = {
        "project": view["project"]["id"],
        "repository": view["project"]["repository"],
        "published": published,
        "development": view["development"],
        "gitPolicy": view["git"],
        "observedGit": observed,
        "remote": remote,
        "next": view["development"]["nextTransition"],
    }
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        active = payload["gitPolicy"].get("activeDevelopmentBranch") or "(none)"
        print(f"PROJECT\n  id: {payload['project']}\n  repository: {payload['repository']}")
        print(f"\nPUBLISHED\n  release: {published['release']}\n  branch: {published['sourceBranch']}\n  url: {published['url']}")
        print(f"\nDEVELOPMENT\n  initiative: {payload['development']['initiative']}\n  phase: {payload['development']['phase']}\n  checkpoint: {payload['development']['checkpoint']}\n  branch: {active}")
        blockers = payload["development"].get("blockers") or []
        print(f"\nBLOCKERS\n  {', '.join(blockers) if blockers else 'none'}")
        print(f"\nNEXT\n  {payload['next']}")
    return 0


def command_doctor(as_json: bool) -> int:
    checks: list[dict[str, Any]] = []
    checks.append({"name": "python", "status": "PASS" if sys.version_info >= (3, 10) else "FAIL", "observed": sys.version.split()[0], "code": None if sys.version_info >= (3, 10) else "PYTHON_TOO_OLD"})
    checks.append({"name": "git-executable", "status": "PASS" if shutil.which("git") else "FAIL", "code": None if shutil.which("git") else "GIT_NOT_FOUND"})
    checks.append({"name": "gh-executable", "status": "PASS" if shutil.which("gh") else "INFO", "code": None if shutil.which("gh") else "GH_NOT_FOUND"})
    try:
        state = project_state.load_state(); state_ok = not project_state.validate_current(state)
        checks.append({"name": "project-state", "status": "PASS" if state_ok else "FAIL", "code": None if state_ok else "STATE_SCHEMA_INVALID"})
    except RuntimeError as exc:
        checks.append({"name": "project-state", "status": "FAIL", "code": str(exc).split(":", 1)[0]})
    git = observed_git()
    if git.get("worktree"):
        origin = git.get("origin") or ""; origin_ok = "eakerber/mobilipresenter" in origin.lower()
        checks.append({"name": "git-origin", "status": "PASS" if origin_ok else "FAIL", "observed": origin, "code": None if origin_ok else "WRONG_REPOSITORY"})
    else:
        checks.append({"name": "git-worktree", "status": "FAIL", "code": "NOT_A_GIT_WORKTREE"})
    ok = all(c["status"] in {"PASS", "INFO"} for c in checks)
    payload = {"ok": ok, "checks": checks}
    print(json.dumps(payload, indent=2, ensure_ascii=False) if as_json else "\n".join(f"{c['status']:4} {c['name']}" for c in checks))
    return 0 if ok else ERROR_EXIT


def command_verify(as_json: bool, include_remote: bool) -> int:
    payload = verify_state(include_remote=include_remote)
    if as_json: print(json.dumps(payload, indent=2, ensure_ascii=False))
    else: print("\n".join(f"{c['status']:7} {c['name']}" for c in payload["checks"])); print(f"\n{payload['status']}")
    return 0 if payload["status"] == "PASS" else ERROR_EXIT


def command_checkpoint(as_json: bool, args: argparse.Namespace) -> int:
    state = project_state.load_state()
    plan = project_state_transition.checkpoint(state, args.checkpoint, args.next_transition, args.phase, validator=project_state.validate_current)
    payload = plan
    if args.apply:
        payload = project_state_apply.apply(
            plan, args.expected_plan, state_path=STATE_PATH, load_state=project_state.load_state,
            validator=project_state.validate_current, observe_git=observed_git,
        )
    print(json.dumps(payload, indent=2, ensure_ascii=False) if as_json else ("APPLIED" if args.apply else "PLAN"))
    return 0


def recent_commits(control_branch: str) -> dict[str, Any]:
    ok, output = run_git("log", "--oneline", "--decorate=no", f"{control_branch}..HEAD", "-n", "20")
    return {"available": True, "entries": [line for line in output.splitlines() if line]} if ok else {"available": False, "reason": output}


def command_handoff(as_json: bool, include_remote: bool) -> int:
    state, view, published = _state_and_publication()
    observed = observed_git()
    verify = verify_state(include_remote=include_remote)
    payload = {
        "schemaVersion": "AgentHandoff 2.0",
        "projectState": view,
        "projectStateHash": stable_hash(state),
        "publication": published,
        "observedGit": observed,
        "verification": verify,
        "recentCommits": recent_commits(view["git"]["controlBranch"]) if observed.get("worktree") else {"available": False},
        "nextTransition": view["development"]["nextTransition"],
        "note": "Derived snapshot; not a new source of truth.",
    }
    if as_json: print(json.dumps(payload, indent=2, ensure_ascii=False))
    else: print(f"HANDOFF\n  verify: {verify['status']}\n  next: {payload['nextTransition']}")
    return 0 if verify["status"] == "PASS" else ERROR_EXIT


def command_git_prune_plan(as_json: bool) -> int:
    return git_prune_plan.command(as_json)


def main() -> int:
    parser = argparse.ArgumentParser(prog="agent", description="MobiliPresenter deterministic operational toolbox")
    parser.add_argument("command", choices=("status", "doctor", "verify", "checkpoint", "handoff", "git"))
    parser.add_argument("subcommand", nargs="?")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--remote", action="store_true", help="Observe PR/CI through gh when available")
    parser.add_argument("--to", dest="checkpoint"); parser.add_argument("--next", dest="next_transition"); parser.add_argument("--phase"); parser.add_argument("--apply", action="store_true"); parser.add_argument("--expected-plan")
    args = parser.parse_args()
    try:
        if args.command == "status": return command_status(args.as_json, args.remote)
        if args.command == "doctor": return command_doctor(args.as_json)
        if args.command == "verify": return command_verify(args.as_json, args.remote)
        if args.command == "checkpoint":
            if not args.checkpoint or not args.next_transition: raise RuntimeError("CHECKPOINT_ARGS_REQUIRED: --to and --next")
            return command_checkpoint(args.as_json, args)
        if args.command == "git":
            if args.subcommand != "prune-plan": raise RuntimeError("GIT_SUBCOMMAND_REQUIRED: prune-plan")
            if args.apply: raise RuntimeError("UNSUPPORTED_TRANSITION: prune planning is read-only; destructive apply is a separately guarded operation")
            return command_git_prune_plan(args.as_json)
        if args.subcommand is not None: raise RuntimeError(f"UNEXPECTED_SUBCOMMAND:{args.subcommand}")
        return command_handoff(args.as_json, args.remote)
    except RuntimeError as exc:
        if args.as_json: print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        else: print(f"BLOCKED\n{exc}", file=sys.stderr)
        return ERROR_EXIT


if __name__ == "__main__":
    raise SystemExit(main())
